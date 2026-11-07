"""Refine an existing saved calibration selection. Offline only; no hardware.

Preserves the original split, input images and first fit. Detector quality gates
are evaluated before calibration, never by deleting high fitted-error views.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2
import numpy as np
from event_camera.calibration import detect, object_points, reprojection_errors
from scripts.calibrate_recording import montage


def sb_native(gray, scale, pattern):
    enlarged=cv2.resize(gray,None,fx=scale,fy=scale,interpolation=cv2.INTER_CUBIC)
    ok,points=cv2.findChessboardCornersSB(enlarged,pattern,
        cv2.CALIB_CB_NORMALIZE_IMAGE|cv2.CALIB_CB_EXHAUSTIVE|cv2.CALIB_CB_ACCURACY)
    return ((points+.5)/scale-.5).astype(np.float32) if ok else None


def align_grid(reference, candidate, pattern):
    a=reference.reshape(-1,2); p=candidate.reshape(pattern[1],pattern[0],2)
    options=[p,p[::-1],p[:,::-1],p[::-1,::-1]]
    best=min(options,key=lambda x:np.mean(np.linalg.norm(a-x.reshape(-1,2),axis=1)))
    return best.reshape(-1,1,2).copy()


def grid_residual(points, pattern):
    grid=object_points(*pattern,1)[:,:2]
    xy=np.asarray(points).reshape(-1,2)
    H,_=cv2.findHomography(grid,xy,0)
    if H is None:
        return None
    pred=cv2.perspectiveTransform(grid.reshape(-1,1,2),H).reshape(-1,2)
    return np.linalg.norm(pred-xy,axis=1)


def fit_model(train, validation, pattern, square, size, flags):
    obj=object_points(*pattern,square)
    rms,K,dist,rv,tv=cv2.calibrateCamera([obj]*len(train),[x['corners'] for x in train],size,None,None,flags=flags)
    per=reprojection_errors([obj]*len(train),[x['corners'] for x in train],rv,tv,K,dist)
    held=[]
    for x in validation:
        ok,r,t=cv2.solvePnP(obj,x['corners'],K,dist)
        held.append(reprojection_errors([obj],[x['corners']],[r],[t],K,dist)[0] if ok else None)
    return {'camera_matrix':K.tolist(),'distortion_coefficients':dist.ravel().tolist(),
            'training_rms_px':float(rms),'training_frame_indices':[x['index'] for x in train],
            'training_per_view_rms_px':per,'reserved_frame_indices':[x['index'] for x in validation],
            'reserved_per_view_rms_px':held,'flags':int(flags)}


def jackknife(train, pattern, square, size, flags):
    """Leave one training view out; describes sensitivity, not a confidence interval."""
    values=[]; failures=[]
    for i in range(len(train)):
        try:
            f=fit_model(train[:i]+train[i+1:],[],pattern,square,size,flags)
            K=np.asarray(f['camera_matrix']); values.append([K[0,0],K[1,1],K[0,2],K[1,2]])
        except cv2.error as error:
            failures.append({'omitted_frame':train[i]['index'],'error':str(error)})
    v=np.asarray(values)
    return {'description':'Leave-one-training-view-out min/max, not calibrated confidence intervals.',
            'columns':['fx','fy','cx','cy'],'fits':len(values),'failures':failures,
            'min':v.min(0).tolist() if len(v) else None,'max':v.max(0).tolist() if len(v) else None,
            'std':v.std(0).tolist() if len(v) else None}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(); a.output.mkdir(parents=True,exist_ok=False)
    original=json.loads((a.source/'provisional_intrinsics.json').read_text())
    summary=json.loads((a.source/'summary.json').read_text())
    pattern=tuple(summary['pattern_inner_corners']); square=summary['square_size_mm_user_reported']
    size=tuple(original['resolution'])
    training_ids=set(original['training_frame_indices']); reserved_ids=set(original['validation_frame_indices'])
    ids=sorted(training_ids|reserved_ids)
    records={int(x['index']):x for x in csv.DictReader((a.source/'frames.csv').open(newline=''))}
    rows=[]
    for idx in ids:
        record=records[idx]; path=a.source/'images'/record['filename']
        gray=cv2.imread(str(path),cv2.IMREAD_GRAYSCALE)
        if gray is None or (gray.shape[1],gray.shape[0])!=size:
            raise ValueError(f'Invalid source image: {path}')
        old=detect(gray,pattern); fine=sb_native(gray,4,pattern); coarse=sb_native(gray,2,pattern)
        reasons=[]; diagnostics={}
        if fine is None or coarse is None:
            reasons.append('SB detection failed at one or both scales')
        else:
            coarse=align_grid(fine,coarse,pattern)
            delta=np.linalg.norm(fine.reshape(-1,2)-coarse.reshape(-1,2),axis=1)
            residual=grid_residual(fine,pattern)
            diagnostics.update(multiscale_p95_px=float(np.percentile(delta,95)),multiscale_max_px=float(delta.max()),
                homography_p95_px=float(np.percentile(residual,95)) if residual is not None else None,
                homography_max_px=float(residual.max()) if residual is not None else None)
            if np.percentile(delta,95)>.5 or delta.max()>1:
                reasons.append('detectors disagree across scales')
            if residual is None or np.percentile(residual,95)>1 or residual.max()>2:
                reasons.append('non-projective grid or corner anomaly')
            if old is not None:
                old=align_grid(fine,old,pattern)
                change=np.linalg.norm(old.reshape(-1,2)-fine.reshape(-1,2),axis=1)
                diagnostics.update(old_to_refined_median_px=float(np.median(change)),old_to_refined_max_px=float(change.max()))
        row={'index':idx,'seconds':float(record['seconds']),'path':path,'corners':fine,
             'method':'SB4x/native','split':'training' if idx in training_ids else 'reserved',
             'exclusion_reasons':reasons,'detector_diagnostics':diagnostics,
             'image_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
        rows.append(row)
        print(f'Frame {idx}: '+('PASS' if not reasons else '; '.join(reasons)),flush=True)
    train=[x for x in rows if x['split']=='training' and not x['exclusion_reasons']]
    validation=[x for x in rows if x['split']=='reserved' and not x['exclusion_reasons']]
    audit=[]
    for r in rows:
        x={k:v for k,v in r.items() if k!='corners'}; x['path']=str(r['path'].resolve())
        x['corrected_corners_native_px']=None if r['corners'] is None else r['corners'].reshape(-1,2).tolist()
        audit.append(x)
    (a.output/'corner_audit.json').write_text(json.dumps(audit,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    montage(rows,a.output/'refined_corner_contact_sheet.png',pattern,'Existing take6: SB4x native-coordinate corner redetection, original split preserved')
    if len(train)<10:
        raise ValueError('Insufficient training views after pre-fit detector screening; audit preserved')
    models={}
    # Primary maintains the original five-coefficient model for a fair detector comparison.
    for label,flags in [('primary_five_coefficient',0),('sensitivity_fixed_k3',cv2.CALIB_FIX_K3)]:
        models[label]=fit_model(train,validation,pattern,square,size,flags)
        models[label]['jackknife']=jackknife(train,pattern,square,size,flags)
    result={'status':'REFINED_PROVISIONAL_NOT_PROMOTED','source_audit_directory':str(a.source.resolve()),
            'source_recording_sha256':summary['source_sha256'],'camera':summary['camera'],
            'resolution':list(size),'pattern_inner_corners':list(pattern),'square_size_mm_user_reported':square,
            'original_training_count':len(training_ids),'original_reserved_count':len(reserved_ids),
            'retained_training_count':len(train),'retained_reserved_count':len(validation),
            'exclusions':[{'frame':x['index'],'split':x['split'],'reason':x['exclusion_reasons']} for x in rows if x['exclusion_reasons']],
            'pre_fit_detector_policy':{'primary':'SB 4x cubic resize, then map pixel centres to native coordinates',
                'cross_check':'SB 2x; symmetry-aligned grid','multiscale_max_px':1,'multiscale_p95_px':.5,
                'grid_homography_max_px':2,'grid_homography_p95_px':1,
                'note':'Heuristics set before refitting. Homography residual also includes lens distortion.'},
            'models':models,'original_training_rms_px':original['training_rms_px'],
            'original_reserved_per_view_rms_px':original['validation_per_view_rms_px'],
            'limitations':['No model installed into live/default settings.','Reserved images already inspected during earlier diagnosis; not an untouched final test set.',
                'Reserved board poses estimated with fixed intrinsics; not independent metric depth accuracy.',
                'Absolute scale uses user-reported18mm pitch; physical print scale unverified.',
                'Jackknife and model comparisons diagnose sensitivity, not independently calibrated uncertainty.',
                'No frames were hand-painted or synthetic corner positions inserted; corrections are image-based redetections.']}
    (a.output/'refined_intrinsics.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(10,4))
    primary=models['primary_five_coefficient']
    axes[0].plot(original['training_frame_indices'],original['training_per_view_rms_px'],'o',label='Original detector')
    axes[0].plot(primary['training_frame_indices'],primary['training_per_view_rms_px'],'x',label='Refined detector')
    axes[1].plot(original['validation_frame_indices'],original['validation_per_view_rms_px'],'o',label='Original detector')
    axes[1].plot(primary['reserved_frame_indices'],primary['reserved_per_view_rms_px'],'x',label='Refined detector')
    for ax,title in zip(axes,['Training views','Same reserved views; pose fitted, not depth validation']):
        ax.set(xlabel='Original frame index',ylabel='RMS reprojection error (native pixels)',title=title); ax.legend()
    fig.tight_layout(); fig.savefig(a.output/'reprojection_comparison.png',dpi=150); plt.close(fig)
    print(json.dumps(result,indent=2),flush=True)


if __name__=='__main__':
    main()
