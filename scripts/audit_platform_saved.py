"""Offline exploratory lower-platform audit; no device access or CAD pose assumed."""
import csv
import argparse
import hashlib
import json
from pathlib import Path
import cv2
import dv_processing as dv
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset',choices=['video5','dense20','original_sparse','original_dense','early_calibrated'],required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    OUT=args.output
    OUT.mkdir(parents=True, exist_ok=False)
    old_model=args.dataset in ['original_sparse','original_dense']
    modelpath = ROOT / ('outputs/calibration/multiplane_ABDE2_20261103_01/planes.json' if old_model else 'outputs/calibration/dense_planes_ABC_20261103_01/planes.json')
    model = json.loads(modelpath.read_text())
    planes = {p['command_us']: p for p in model['planes']}
    intr = json.loads((ROOT / Path(model['intrinsics'])).read_text())['models']['primary_five_coefficient']
    k = np.asarray(intr['camera_matrix']); dist = np.asarray(intr['distortion_coefficients'])
    rows, records = [], []
    display=[1569,1590,1602,1626,1647]
    if args.dataset=='original_sparse': display=[1569,1602,1618,1634,1651]
    if args.dataset=='original_dense': display=[1569,1602,1618,1651]
    fig, axes = plt.subplots(3, len(display), figsize=(3*len(display), 8),squeeze=False)
    source_reports={'dense20':'shoe_further2_20261103_02_roi','original_sparse':'sparse_shoe_20261103_01','original_dense':'dense_shoe_interpolated_20261103_01','early_calibrated':'dense_shoe_calibrated_20261103_01'}
    observations=(json.loads((ROOT/f'outputs/reconstruction/{source_reports[args.dataset]}/reconstruction.json').read_text())['observations'] if args.dataset in source_reports else [dict(command_us=c,raw=f'data/raw/recorded_video5_20261103_132551_fd9496_{c}.aedat4') for c in display])
    observations=[o for o in observations if 'raw' in o and o['command_us'] in planes and 'normal_camera' in planes[o['command_us']]]
    if args.dataset=='original_dense':
        # Only acquired calibration knots; do not use interpolated planes here.
        observations=[o for o in observations if o.get('interpolation',{}).get('independently_fitted_knot',False)]
    for observation in observations:
        command=observation['command_us']; raw=ROOT/observation['raw']
        reader = dv.io.MonoCameraRecording(str(raw)); frames = []; times=[]
        while True:
            f = reader.getNextFrame()
            if f is None: break
            frames.append(f.image.copy())
            times.append(int(f.timestamp))
        a = np.stack(frames); ref = np.median(a[:3],axis=0)
        delta = a.astype(float)-ref
        # Select lit frames by the historical whole-scene signal; extend only
        # row search, not thresholds, into previously excluded lower image.
        signal = np.maximum(delta[:,5:146],0).sum(axis=(1,2))
        relative=(np.asarray(times)-times[0])/1e6
        window=(relative>=2)&(relative<=6)
        peak=int(np.argmax(np.where(window,signal,-1)))
        qualifies=window&(signal>.5*signal[peak])
        # Keep the connected optical bright interval containing the peak.
        # Later recording-tail lighting changes are not pulse frames.
        lo=peak; hi=peak
        while lo>0 and qualifies[lo-1]: lo-=1
        while hi+1<len(a) and qualifies[hi+1]: hi+=1
        selected=np.arange(lo,hi+1)
        byrow = {}; clipping = 0; ambiguity = 0
        for i in selected:
            for y in range(120,180):
                x = np.flatnonzero((delta[i,y]>20)&(a[i,y]>40))
                if not len(x): continue
                groups = np.split(x,np.flatnonzero(np.diff(x)>1)+1)
                groups = [g for g in groups if 1<=len(g)<=12]
                groups.sort(key=lambda g:delta[i,y,g].sum(),reverse=True)
                if not groups: continue
                g = groups[0]
                if len(groups)>1 and delta[i,y,groups[1]].sum()>.67*delta[i,y,g].sum():
                    ambiguity += 1; continue
                if (a[i,y,g]>=250).any(): clipping+=1; continue
                byrow.setdefault(y,[]).append(float(np.average(g,weights=delta[i,y,g])))
        pixels=np.asarray([(np.median(v),y,len(v)) for y,v in sorted(byrow.items()) if len(v)>=max(5,len(selected)/2)],float).reshape(-1,3)
        if len(pixels):
            rays2=cv2.undistortPoints(pixels[:,:2].reshape(-1,1,2),k,dist).reshape(-1,2)
            rays=np.column_stack([rays2,np.ones(len(rays2))]); p=planes[command]
            denom=rays@np.asarray(p['normal_camera']); scale=-p['offset_mm']/denom
            xyz=rays*scale[:,None]
            for pix,point,s in zip(pixels,xyz,scale):
                rows.append([command,*pix,*point,bool(np.isfinite(s) and s>0)])
        if command in display:
            col=display.index(command)
            axes[0,col].imshow(ref,cmap='gray',vmin=0,vmax=255)
            axes[0,col].axhspan(120,179,alpha=.12,color='cyan')
            axes[1,col].imshow(a[peak],cmap='gray',vmin=0,vmax=255)
            axes[2,col].imshow(np.maximum(delta[peak],0),cmap='inferno',vmin=0,vmax=100)
            for ax in axes[:,col]:
                ax.set_xlim(0,239); ax.set_ylim(179,0)
            if len(pixels):
                axes[1,col].scatter(pixels[:,0],pixels[:,1],s=10,facecolors='none',edgecolors='cyan')
                axes[2,col].scatter(pixels[:,0],pixels[:,1],s=10,facecolors='none',edgecolors='cyan')
            axes[0,col].set_title(f'{command} us\n{len(pixels)} lower-row candidates')
        records.append(dict(command_us=command,raw=str(raw.relative_to(ROOT)),sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),frames=len(a),selected_frames=selected.tolist(),lower_candidate_rows=len(pixels),clipped_row_frames=clipping,ambiguous_row_frames=ambiguity))
    axes[0,0].set_ylabel('Laser-off reference / pixel y')
    axes[1,0].set_ylabel('Peak APS / pixel y')
    axes[2,0].set_ylabel('Positive change / pixel y')
    fig.suptitle(f'Saved {args.dataset} scan: lower-platform feasibility audit ({len(display)} displayed commands)\nCyan circles are screened image-change candidates, not confirmed platform detections')
    fig.tight_layout(); fig.savefig(OUT/'platform_audit.png',dpi=160); plt.close(fig)
    with (OUT/'lower_candidates.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['command_us','pixel_x','pixel_y','support_frames','X_mm','Y_mm','Z_mm','positive_finite_depth']);w.writerows(rows)
    result=dict(status='EXPLORATORY_PLATFORM_FEASIBILITY_ONLY',dataset=args.dataset,frame_selection='Connected half-peak optical bright interval with peak restricted to 2..6 seconds; not a physical clock alignment.',model_sha256=hashlib.sha256(modelpath.read_bytes()).hexdigest(),search_rows=[120,179],observations=records,candidate_points=len(rows),limitations=['Post-hoc region and exploratory extended row search; no confirmed stripe labels.','Frozen planes extrapolated below original board/row support; 3D candidates are not validated platform geometry.','Two-hole remount supplied by user; actual camera-to-CAD transform not established.','CAD dimensions are nominal; no physical completeness percentage or independent accuracy established.'])
    (OUT/'summary.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(dict(dataset=args.dataset,candidate_points=len(rows),observations=[dict(command_us=r['command_us'],lower_candidate_rows=r['lower_candidate_rows'],selected_frames=len(r['selected_frames'])) for r in records]),indent=2))


if __name__=='__main__': main()
