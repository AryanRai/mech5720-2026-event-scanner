"""Offline APS checkerboard audit and provisional intrinsics; never opens hardware.

Creates a new output directory, preserves all source frames, and does not install
the resulting calibration as the live/default camera model.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cv2
import dv_processing as dv
import numpy as np
from event_camera.calibration import detect, features, novelty, object_points, quality, reprojection_errors


def board_photometry(gray, corners):
    """Inspect inner-board hull; intended black squares are not a reject reason.

    Thresholds are transparent screening heuristics, not a calibration guarantee.
    Preserve the legacy global flags separately for audit/comparison.
    """
    if corners is None:
        return None, []
    mask = np.zeros(gray.shape, np.uint8)
    hull = cv2.convexHull(np.rint(corners.reshape(-1,2)).astype(np.int32))
    cv2.fillConvexPoly(mask,hull,1)
    values = gray[mask.astype(bool)]
    if not len(values):
        return None, ['empty board ROI']
    lo,hi = np.percentile(values,[10,90])
    bright = float(np.mean(values>=250))
    result = {'pixels':int(len(values)), 'p10':float(lo), 'p90':float(hi),
              'contrast_p90_p10':float(hi-lo),'bright_fraction':bright}
    reasons = []
    if bright >= .2:
        reasons.append('board ROI bright clipping')
    if hi-lo < 30:
        reasons.append('low board ROI contrast')
    return result,reasons


def select_diverse(candidates, limit=25, minimum_distance=.8):
    """Quality first, then farthest-point coverage; independent of fitted error."""
    if not candidates:
        return []
    selected = [max(candidates, key=lambda x: x['sharpness'])]
    remaining = [x for x in candidates if x is not selected[0]]
    while remaining and len(selected) < limit:
        best = max(remaining, key=lambda x: novelty(x['feature'], [y['feature'] for y in selected]))
        if novelty(best['feature'], [y['feature'] for y in selected]) < minimum_distance:
            break
        selected.append(best)
        remaining = [x for x in remaining if x is not best]
    return sorted(selected, key=lambda x: x['index'])


def montage(items, output, pattern, title):
    if not items:
        return
    tw, th = 360, 295
    canvas = np.full((int(np.ceil(len(items)/4))*th + 35, 4*tw, 3), 25, np.uint8)
    cv2.putText(canvas, title, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, .55, (255,255,255), 1)
    for i, row in enumerate(items):
        image = cv2.imread(str(row['path']))
        if row['corners'] is not None:
            cv2.drawChessboardCorners(image, pattern, row['corners'], True)
        image = cv2.resize(image, (360,270), interpolation=cv2.INTER_NEAREST)
        y, x = 35+(i//4)*th, (i%4)*tw
        canvas[y:y+270, x:x+360] = image
        label = f"#{row['index']} t={row['seconds']:.1f}s {row['method']}"
        cv2.putText(canvas, label, (x+5,y+287), cv2.FONT_HERSHEY_SIMPLEX, .43, (255,255,255), 1)
    cv2.imwrite(str(output), canvas)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recording', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cols', type=int, default=9)
    parser.add_argument('--rows', type=int, default=6)
    parser.add_argument('--square-mm', type=float, default=18)
    parser.add_argument('--quality-mode', choices=['legacy','board'], default='legacy',
                        help='board replaces global clipping rejection with inner-board brightness/contrast checks; logs both')
    args = parser.parse_args()
    if min(args.cols,args.rows) < 2 or args.square_mm <= 0:
        parser.error('Invalid board geometry')
    args.output.mkdir(parents=True, exist_ok=False)
    raw = args.output/'images'; raw.mkdir()
    pattern = (args.cols,args.rows)
    recording = dv.io.MonoCameraRecording(str(args.recording))
    if not recording.isFrameStreamAvailable():
        raise RuntimeError('Recording has no APS frame stream')
    rows = []; origin = None
    while True:
        frame = recording.getNextFrame()
        if frame is None:
            break
        gray = np.asarray(frame.image)
        if gray.ndim != 2:
            raise RuntimeError('Expected unmodified grayscale APS images')
        index = len(rows); timestamp = int(frame.timestamp)
        if origin is None:
            origin = timestamp
        path = raw/f'frame_{index:04d}_{timestamp}.png'
        if not cv2.imwrite(str(path),gray):
            raise RuntimeError(f'Could not write {path}')
        corners = detect(gray,pattern); method = 'classic' if corners is not None else 'none'
        if corners is None:
            # Upscaling aids detection only; returned coordinates are native pixels.
            scaled = cv2.resize(gray,None,fx=2,fy=2,interpolation=cv2.INTER_CUBIC)
            ok, found = cv2.findChessboardCornersSB(scaled,pattern,cv2.CALIB_CB_NORMALIZE_IMAGE)
            if ok:
                # OpenCV resize: dst centre = (src centre + .5) * scale - .5.
                corners = (found+.5)/2-.5; method = 'SB_2x_to_native'
        sharpness,reasons = quality(gray,corners,pattern)
        legacy_reasons = list(reasons)
        photometry,board_reasons = board_photometry(gray,corners)
        if args.quality_mode == 'board':
            reasons = [r for r in reasons if r != 'excess clipping'] + board_reasons
        row = {'index':index,'timestamp_us':timestamp,'seconds':(timestamp-origin)/1e6,
               'path':path,'corners':corners,'method':method,'sharpness':sharpness,
               'dark_pct':float(np.mean(gray<=5)*100),'bright_pct':float(np.mean(gray>=250)*100),
               'reasons':reasons,'legacy_reasons':legacy_reasons,'board_photometry':photometry,
               'feature':None if corners is None else features(corners,(gray.shape[1],gray.shape[0]),pattern)}
        rows.append(row)
        if index % 50 == 0:
            print(f'Inspected {index+1} APS frames; detections {sum(x["corners"] is not None for x in rows)}',flush=True)
    if not rows:
        raise RuntimeError('No APS frames read')
    candidates = [r for r in rows if not r['reasons']]
    selected = select_diverse(candidates)
    for row in rows:
        row['selection'] = 'selected' if any(row is x for x in selected) else 'not_selected'
    fields=['index','timestamp_us','seconds','filename','method','sharpness','dark_pct','bright_pct','reasons','legacy_reasons','board_photometry','selection','feature']
    with (args.output/'frames.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=fields); writer.writeheader()
        for row in rows:
            out={k:row[k] for k in fields if k not in ('filename','feature','reasons','legacy_reasons','board_photometry')}
            out.update(filename=row['path'].name,reasons='; '.join(row['reasons']),legacy_reasons='; '.join(row['legacy_reasons']),board_photometry=json.dumps(row['board_photometry']),feature=json.dumps(None if row['feature'] is None else row['feature'].tolist()))
            writer.writerow(out)
    overview=[rows[i] for i in np.linspace(0,len(rows)-1,16,dtype=int)]
    montage(overview,args.output/'timeline_contact_sheet.png',pattern,'Take timeline: native APS images enlarged, detected corners overlaid')
    montage(sorted([r for r in rows if r['corners'] is not None],key=lambda x:x['sharpness'],reverse=True)[:16],args.output/'detected_contact_sheet.png',pattern,'Highest sharpness detections (may still fail quality gates)')
    montage(selected,args.output/'selected_contact_sheet.png',pattern,'Diverse quality-passing views, selected before calibration fitting')
    with args.recording.open('rb') as source_file:
        source_hash = hashlib.file_digest(source_file,'sha256').hexdigest()
    summary={'source':str(args.recording.resolve()),'source_sha256':source_hash,
             'camera':recording.getCameraName(),'pattern_inner_corners':list(pattern),'square_size_mm_user_reported':args.square_mm,
             'print_scale_independently_verified':False,'frames':len(rows),'full_board_detections':sum(r['corners'] is not None for r in rows),
             'quality_passing_frames':len(candidates),'diverse_selected_frames':len(selected),
             'selection_policy':{'quality_mode':args.quality_mode,'sharpness_min':20,'global_clipping_max_fraction':.2 if args.quality_mode=='legacy' else None,'board_bright_max_fraction':.2 if args.quality_mode=='board' else None,'board_min_p90_p10_contrast':30 if args.quality_mode=='board' else None,'novelty_min':.8,'max_views':25},
             'quality_rejection_counts':{reason:sum(reason in r['reasons'] for r in rows) for reason in sorted(set(x for r in rows for x in r['reasons']))},
             'status':'INSUFFICIENT_DIVERSE_VIEWS','limitations':['Global clipping/sharpness and pose novelty are heuristics, not physical calibration guarantees.','Moving-board frames may contain motion blur.','No calibration promoted to active settings.','Print scale and current lens configuration require physical confirmation.']}
    # Keep separate pose-diverse views for validation; fit only if enough survive.
    if len(selected)>=20:
        validation=[selected[i] for i in np.linspace(0,len(selected)-1,5,dtype=int)]
        train=[x for x in selected if not any(x is y for y in validation)]
        obj=object_points(*pattern,args.square_mm)
        gray=cv2.imread(str(rows[0]['path']),cv2.IMREAD_GRAYSCALE)
        rms,K,dist,rv,tv=cv2.calibrateCamera([obj]*len(train),[x['corners'] for x in train],(gray.shape[1],gray.shape[0]),None,None)
        train_errors=reprojection_errors([obj]*len(train),[x['corners'] for x in train],rv,tv,K,dist)
        validation_errors=[]
        for x in validation:
            ok,r,t=cv2.solvePnP(obj,x['corners'],K,dist)
            validation_errors.append(reprojection_errors([obj],[x['corners']],[r],[t],K,dist)[0] if ok else None)
        model={'status':'PROVISIONAL_NOT_PROMOTED','camera_matrix':K.tolist(),'distortion':dist.ravel().tolist(),
               'training_rms_px':float(rms),'training_frame_indices':[x['index'] for x in train],
               'training_per_view_rms_px':train_errors,'validation_frame_indices':[x['index'] for x in validation],
               'validation_per_view_rms_px':validation_errors,'resolution':[gray.shape[1],gray.shape[0]],
               'square_size_mm_user_reported':args.square_mm,'validation_note':'Board pose fitted per held-out view; checks intrinsics, not independent depth accuracy.'}
        (args.output/'provisional_intrinsics.json').write_text(json.dumps(model,indent=2,allow_nan=False)+'\n',encoding='utf-8')
        summary['status']='PROVISIONAL_FIT_REQUIRES_REVIEW'; summary['calibration']=model
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__':
    main()
