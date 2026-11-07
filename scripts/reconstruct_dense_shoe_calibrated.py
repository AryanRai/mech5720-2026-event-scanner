"""Reconstruct a partial APS shoe scan using frozen independently fitted planes."""
import csv
import argparse
import hashlib
import json
from pathlib import Path
import cv2
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter
from scripts.reconstruct_sparse_shoe import detect


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prefix',default='dense_shoe_calibrated')
    parser.add_argument('--output',default='outputs/reconstruction/dense_shoe_calibrated_20261103_01')
    parser.add_argument('--last-row',type=int,default=110)
    parser.add_argument('--first-row',type=int,default=5)
    parser.add_argument('--roi-note',default='Photo ROI chosen after pilot before remaining captures.')
    parser.add_argument('--exposure-us',type=int,default=10000)
    parser.add_argument('--run-map',type=Path)
    args=parser.parse_args()
    run_map=json.loads(args.run_map.read_text()) if args.run_map else {}
    modelpath=Path('outputs/calibration/dense_planes_ABC_20261103_01/planes.json')
    digest=hashlib.sha256(modelpath.read_bytes()).hexdigest()
    assert digest==json.loads((modelpath.parent/'frozen_model.json').read_text())['planes_sha256']
    model=json.loads(modelpath.read_text())
    intr=json.loads(Path(model['intrinsics']).read_text())['models']['primary_five_coefficient'];k=np.array(intr['camera_matrix']);dist=np.array(intr['distortion_coefficients'])
    out=Path(args.output);out.mkdir(parents=True,exist_ok=False)
    before=Path(f'outputs/agent_control/{args.prefix}_ref_20261103_01/aps.png')
    after=Path(f'outputs/agent_control/{args.prefix}_after_20261103_01/aps.png')
    photo=Path(f'outputs/agent_control/{args.prefix}_photo_20261103_01/aps.png')
    first=cv2.imread(str(before),0).astype(np.float32);last=cv2.imread(str(after),0).astype(np.float32)
    shift,response=cv2.phaseCorrelate(first,last)
    stability=dict(phase_correlation_shift_xy_px=list(shift),response=response,mean_absolute_difference_levels=float(abs(first-last).mean()),alignment_applied=False,
                   note='Same35ms image stability diagnostic, not independent rigid-body measurement; no image registration applied.')
    observations=[];points=[]
    for plane in model['planes']:
        if 'normal_camera' not in plane:continue
        command=plane['command_us'];suffix='01'
        run=f'{args.prefix}_{command}_20261103_'+suffix
        run=run_map.get(str(command),run)
        raw=Path('data/raw')/(run+'.aedat4');tracepath=Path('outputs/static_checks')/run/'summary.json'
        obs=dict(command_us=command,run_id=run,raw=str(raw),training_pose_count=plane['pose_count'])
        if not tracepath.exists():obs.update(status='NOT_COMPLETED');observations.append(obs);continue
        trace=json.loads(tracepath.read_text())
        if trace['errors']:obs.update(status='INVALID_TRACE',errors=trace['errors']);observations.append(obs);continue
        try:pixels,screen,peak=detect(raw,delta_threshold=20,intensity_threshold=40)
        except ValueError as exc:obs.update(status='NO_RETAINED_STRIPE',reason=str(exc));observations.append(obs);continue
        cv2.imwrite(str(out/f'laser_on_{command}.png'),peak)
        # Shoe silhouette in laser-off photo occupies upper image; exclude lower platform.
        screen['rows_excluded_by_photo_roi']=int(np.sum((pixels[:,1]<args.first_row)|(pixels[:,1]>args.last_row))) if len(pixels) else 0
        if len(pixels):pixels=pixels[(pixels[:,1]>=args.first_row)&(pixels[:,1]<=args.last_row)]
        obs.update(raw_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),screen=screen,feedback_warning=trace['feedback_screen_warning'],status='NO_RETAINED_STRIPE',points=0)
        if len(pixels):
            xy=cv2.undistortPoints(pixels.reshape(-1,1,2),k,dist).reshape(-1,2);rays=np.column_stack((xy,np.ones(len(xy))))
            n=np.array(plane['normal_camera']);den=rays@n;valid=abs(den)>1e-8
            scale=np.full(len(rays),np.nan);scale[valid]=-plane['offset_mm']/den[valid];valid&=np.isfinite(scale)&(scale>0)
            xyz=rays[valid]*scale[valid,None]
            train=np.concatenate([np.array(o['points_camera_mm']) for o in plane['observations']]);lo,hi=float(train[:,2].min()),float(train[:,2].max())
            for pixel,p in zip(pixels[valid],xyz):points.append([command,float(pixel[0]),float(pixel[1]),*map(float,p)])
            obs.update(status='PRELIMINARY_RECONSTRUCTED',points=len(xyz),invalid_rays_excluded=int((~valid).sum()),training_stripe_Z_range_mm=[lo,hi],
                       reconstructed_points_outside_training_Z_range=int(np.sum((xyz[:,2]<lo)|(xyz[:,2]>hi))),
                       depth_range_mm=[float(xyz[:,2].min()),float(xyz[:,2].max())] if len(xyz) else None)
        observations.append(obs)
    with (out/'points.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['command_us','pixel_x','pixel_y','X_mm','Y_mm','Z_mm']);w.writerows(points)
    limitations=('Partial APS stripe reconstruction using frozen per-command planes; no plane interpolation, test alignment, refit, bias correction or generated surface. '
                 'Reserved boardD per-command depthRMSE0.88..17.03mm, equal-commandRMS8.63mm on one sharedK/reported18mm-scale posed board; not independent shoe accuracy. '
                 'No shoe groundtruth, full-object completeness, event3D, continuous timing or speed/ND comparison. Correlated points/frames are not independent repeats. '
                 f'Photo ROI rows{args.first_row}..{args.last_row}; background/occlusion/stripe identity remain possible failure sources. '+args.roi_note+' '
                 'Photo overlay uses original measured pixels and is not independent depth validation. Depth-range extrapolation is disclosed without deleting points.')
    result=dict(model=str(modelpath),model_sha256=digest,points=len(points),contributing_positions=len({p[0] for p in points}),exposure_us=args.exposure_us,
                detector=f'Existing sensitive shoe detector delta>20 APS>40, width1..12 strongestcontiguousrowgroup, runnerup>.67 rejected, any>=250 excluded, medianrow supported>=halflitframes; photoROI y{args.first_row}..{args.last_row}. '+args.roi_note,
                observations=observations,photo=str(photo),stability=stability,limitations=limitations)
    (out/'reconstruction.json').write_text(json.dumps(result,indent=2))
    if not points:raise ValueError('No reconstructed points; diagnostics and sources preserved')
    a=np.array(points)
    with (out/'points.ply').open('w') as f:
        f.write('ply\nformat ascii 1.0\nelement vertex '+str(len(points))+'\nproperty float x\nproperty float y\nproperty float z\nend_header\n')
        for row in points:f.write(' '.join(map(str,row[3:]))+'\n')
    fig=plt.figure(figsize=(10,5));ax=fig.add_subplot(121,projection='3d');side=fig.add_subplot(122)
    ax.scatter(a[:,3],a[:,5],-a[:,4],c=a[:,0],cmap='viridis',s=5);side.scatter(a[:,5],-a[:,4],c=a[:,0],cmap='viridis',s=5)
    ax.set(xlabel='Camera X (mm)',ylabel='Camera Z (mm)',zlabel='−Camera Y (mm)');ax.set_box_aspect(np.maximum(np.ptp(a[:,[3,5,4]],axis=0),1));ax.view_init(elev=24,azim=-62)
    side.set(xlabel='Camera Z / depth (mm)',ylabel='−Camera Y (mm)',title='Measured stripe profiles')
    fig.suptitle('Partial shoe scan — independently fitted static laser planes');fig.text(.5,.015,f'{len(points)} points / {result["contributing_positions"]} positions • APS{args.exposure_us/1000:g}ms • position-dependent calibration errors; shoe accuracy unverified',ha='center',fontsize=8)
    fig.tight_layout(rect=[0,.05,1,.94]);fig.savefig(out/'point_cloud.png',dpi=180);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(10,4.5));im=cv2.imread(str(photo),0)
    for ax in axes:ax.imshow(im,cmap='gray',vmin=0,vmax=255);ax.axis('off')
    axes[0].set_title('Laser-off DAVIS photograph (100ms)');sc=axes[1].scatter(a[:,1],a[:,2],c=a[:,5],cmap='turbo',s=5);axes[1].set_title('Measured pixels coloured by estimated depth')
    fig.colorbar(sc,ax=axes[1],label='Estimated Z (mm)',shrink=.65);fig.suptitle('Partial shoe scan: photograph and native-pixel overlay')
    fig.text(.5,.025,'No image warp or depth alignment • overlay is provenance, not independent accuracy validation',ha='center',fontsize=8);fig.savefig(out/'shoe_photo_and_overlay.png',dpi=180);plt.close(fig)
    fig=plt.figure(figsize=(6.4,5.6));ax=fig.add_subplot(111,projection='3d');ax.scatter(a[:,3],a[:,5],-a[:,4],c=a[:,0],cmap='viridis',s=6)
    ax.set(xlabel='X (mm)',ylabel='Z (mm)',zlabel='−Y (mm)',title='Partial measured shoe point cloud');ax.set_box_aspect(np.maximum(np.ptp(a[:,[3,5,4]],axis=0),1))
    fig.text(.5,.02,'Static fitted planes • known calibration error • no mesh / object groundtruth',ha='center',fontsize=8)
    def update(i):ax.view_init(elev=24,azim=-62+i*10);return []
    FuncAnimation(fig,update,frames=36,interval=100).save(out/'rotating_point_cloud.gif',writer=PillowWriter(fps=10),dpi=90);plt.close(fig)
    lines=['# Partial shoe scan with dense fitted planes','',f'{len(points)} retained points from {result["contributing_positions"]} fitted positions.','',limitations,'',result['detector'],'','| Command (µs) | Points | Outcome | Outside training Z range |','|---|---|---|---|']
    for o in observations:lines.append(f"| {o['command_us']} | {o.get('points',0)} | {o['status']} | {o.get('reconstructed_points_outside_training_Z_range','—')} |")
    (out/'REVIEW.md').write_text('\n'.join(lines),encoding='utf-8')
    register=Path('EXPERIMENT_RUN_REGISTER.csv')
    with register.open(newline='',encoding='utf-8-sig') as f:rd=csv.DictReader(f);fields=rd.fieldnames;existing={r['run_id'] for r in rd}
    rows=[]
    for o in observations:
        if not Path(o['raw']).exists() or o['run_id'] in existing:continue
        row=dict.fromkeys(fields,'');d=Path('outputs/static_checks')/o['run_id'];row.update(run_id=o['run_id'],block='P6',status=o['status'],condition_id=f'shoe_dense_fitted_planes{args.exposure_us/1000:g}ms',firmware_version='1.7',actual_exposure_ms=args.exposure_us/1000,servo_min_us=o['command_us'],servo_max_us=o['command_us'],raw_aedat4_path=o['raw'],feedback_log_path=str(d/'samples.csv'),status_log_path=str(d/'operation.json'),processed_output_path=str(out),notes='FrozenABC no interpolation/refit/alignment; knownDerrors; partialAPS/objectaccuracyunverified; finaloff/disarm/release');rows.append(row)
    with register.open('a',newline='',encoding='utf-8') as f:csv.DictWriter(f,fields).writerows(rows)
    print(json.dumps(dict(output=str(out),points=len(points),positions=result['contributing_positions'],stability=stability)))


if __name__=='__main__':main()
