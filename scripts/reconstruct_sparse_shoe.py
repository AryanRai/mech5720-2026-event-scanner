"""Exploratory APS stripe point cloud using frozen ABDE2 planes, no alignment."""
import csv
import hashlib
import json
from pathlib import Path
import urllib.request
import cv2
import dv_processing as dv
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def detect(raw, delta_threshold=40, intensity_threshold=80):
    reader=dv.io.MonoCameraRecording(str(raw));frames=[]
    while True:
        frame=reader.getNextFrame()
        if frame is None:break
        frames.append(frame.image.copy())
    a=np.stack(frames);ref=np.median(a[:3],axis=0);delta=a.astype(float)-ref
    signal=np.maximum(delta[:,5:146],0).sum(axis=(1,2))
    selected=np.flatnonzero(signal>signal.max()*.5)
    if len(selected)<5:raise ValueError('Insufficient bright frames')
    byrow={};clipped=0;ambiguous=0
    for index in selected:
        for y in range(5,146):
            x=np.flatnonzero((delta[index,y]>delta_threshold)&(a[index,y]>intensity_threshold))
            if not len(x):continue
            clusters=np.split(x,np.flatnonzero(np.diff(x)>1)+1)
            candidates=[g for g in clusters if 1<=len(g)<=12]
            candidates.sort(key=lambda g:float(delta[index,y,g].sum()),reverse=True)
            if not candidates:continue
            g=candidates[0]
            if len(candidates)>1 and delta[index,y,candidates[1]].sum()>.67*delta[index,y,g].sum():
                ambiguous+=1;continue
            if np.any(a[index,y,g]>=250):clipped+=1;continue
            byrow.setdefault(y,[]).append(float(np.average(g,weights=delta[index,y,g])))
    pixels=np.array([(np.median(v),y) for y,v in sorted(byrow.items()) if len(v)>=len(selected)/2])
    dark=np.flatnonzero(signal<signal.max()*.1)
    dark_candidates=(delta[dark,5:146]>delta_threshold)&(a[dark,5:146]>intensity_threshold)
    return pixels,dict(frames=len(frames),selected_frames=selected.tolist(),clipped_row_frame_candidates=clipped,
                       delta_threshold=delta_threshold,intensity_threshold=intensity_threshold,
                       dark_control_frames=len(dark),dark_control_max_pixel_candidates_per_frame=int(dark_candidates.sum(axis=(1,2)).max()) if len(dark) else None,
                       dark_control_max_positive_change=float(delta[dark,5:146].max()) if len(dark) else None,
                       ambiguous_row_frame_candidates=ambiguous,retained_rows=len(pixels)),a[int(signal.argmax())]


def main():
    modeldir=Path('outputs/calibration/multiplane_ABDE2_20261103_01');modelpath=modeldir/'planes.json'
    digest=hashlib.sha256(modelpath.read_bytes()).hexdigest()
    if digest!=json.loads((modeldir/'frozen_model.json').read_text())['planes_sha256']:raise ValueError('Model changed')
    model=json.loads(modelpath.read_text());intr=json.loads(Path(model['intrinsics']).read_text())['models']['primary_five_coefficient']
    k=np.array(intr['camera_matrix']);dist=np.array(intr['distortion_coefficients'])
    out=Path('outputs/reconstruction/sparse_shoe_20261103_01');out.mkdir(parents=True,exist_ok=False)
    points=[];observations=[];peaks=[]
    for plane in model['planes']:
        if plane['status']!='FOUR_POSE_TRAINING_FIT':continue
        command=plane['command_us'];run=f'sparse_shoe_{command}_20261103_'+('02' if command==1602 else '01')
        raw=Path('data/raw')/(run+'.aedat4');trace=json.loads((Path('outputs/static_checks')/run/'summary.json').read_text())
        if trace['errors']:raise ValueError('Invalid object trace '+run)
        pixels,screen,peak=detect(raw);peaks.append((command,peak))
        if not len(pixels):
            observations.append(dict(command_us=command,status='NO_UNSATURATED_ROWS',screen=screen));continue
        xy=cv2.undistortPoints(pixels.reshape(-1,1,2),k,dist).reshape(-1,2)
        rays=np.column_stack((xy,np.ones(len(xy))));n=np.array(plane['normal_camera']);den=rays@n
        valid=abs(den)>1e-8;scale=np.full(len(rays),np.nan);scale[valid]=-plane['offset_mm']/den[valid]
        valid&=np.isfinite(scale)&(scale>0)
        xyz=rays[valid]*scale[valid,None]
        for pixel,p in zip(pixels[valid],xyz):points.append([command,float(pixel[0]),float(pixel[1]),*map(float,p)])
        observations.append(dict(command_us=command,run_id=run,raw=str(raw),sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),
            screen=screen,points=len(xyz),nonpositive_or_parallel_rays_rejected=int((~valid).sum()),
            feedback_warning=trace['feedback_screen_warning'],depth_range_mm=[float(xyz[:,2].min()),float(xyz[:,2].max())] if len(xyz) else None))
    array=np.array(points)
    if not len(array):raise ValueError('No reconstructable points; raw acquisitions preserved')
    with (out/'points.csv').open('w',newline='') as f:
        writer=csv.writer(f);writer.writerow(['command_us','pixel_x','pixel_y','X_mm','Y_mm','Z_mm']);writer.writerows(points)
    with (out/'points.ply').open('w') as f:
        f.write('ply\nformat ascii 1.0\nelement vertex '+str(len(points))+'\nproperty float x\nproperty float y\nproperty float z\nend_header\n')
        for row in points:f.write(' '.join(map(str,row[3:]))+'\n')
    limitation='PRELIMINARY APS point cloud from six static stripe positions, not a dense surface, eventbased3D result or independently validated shoe accuracy. FrozenABDE2 model, no alignment/refit/biascorrection. Calibration diagnosticC errors and separateE2 errors remain positiondependent. No completeness claim; rows/frames correlated. Cropped image rows5..145 chosen from shoeview; possiblebackground/occlusion contamination. Saturated/ambiguous rowframes excluded, leaving gaps. No mesh/interpolated shape generated.'
    result=dict(status='PRELIMINARY_SPARSE_APS_RECONSTRUCTION',model=str(modelpath),model_sha256=digest,points=len(points),
                observations=observations,alignment_applied=False,model_refitted=False,
                detector='Object-specific exploratory screen: first3APSmedian; rows5..145 delta>40 APS>80; contiguousrowgroups width1..12 strongestenergy; rejectrunnerup>0.67strongest; rejectanypixel>=250; medianx perrow present in>=halflitframes. Litframes globalpositivechange>halfpeak,>=5. No physicaldepth filtering beyond positive/nonparallelrays.',
                limitations=limitation)
    (out/'reconstruction.json').write_text(json.dumps(result,indent=2))
    fig=plt.figure(figsize=(11,5.6));ax=fig.add_subplot(121,projection='3d');side=fig.add_subplot(122)
    for command in sorted(set(array[:,0])):
        group=array[array[:,0]==command]
        ax.scatter(group[:,3],group[:,5],-group[:,4],s=10,label=str(int(command))+' µs')
        side.scatter(group[:,5],-group[:,4],s=12)
    ax.set(xlabel='Camera X (mm)',ylabel='Camera Z / depth (mm)',zlabel='−Camera Y (mm)')
    ax.view_init(elev=24,azim=-62);ax.legend(fontsize=7)
    side.set(xlabel='Camera Z / depth (mm)',ylabel='−Camera Y (mm)',title='Side profile: retained measured points')
    fig.suptitle('Preliminary sparse shoe reconstruction — actual APS laser stripes',fontsize=14)
    fig.text(.5,.02,'Frozen calibration; known position-dependent errors • no object ground truth • gaps include clipping exclusions',ha='center',fontsize=9)
    fig.tight_layout(rect=[0,.06,1,.94]);fig.savefig(out/'point_cloud.png',dpi=180)
    fig,axes=plt.subplots(2,3,figsize=(9,5.6))
    for ax,(command,peak) in zip(axes.ravel(),peaks):ax.imshow(peak,cmap='gray',vmin=0,vmax=255);ax.set_title(str(command)+' µs');ax.axis('off')
    fig.suptitle('Actual laser-on APS images: sparse shoe capture');fig.tight_layout();fig.savefig(out/'stripe_montage.png',dpi=180)
    (out/'REVIEW.md').write_text('# Preliminary sparse shoe reconstruction\n\n'+str(len(points))+' retained 3D points.\n\n'+limitation+'\n\n'+result['detector']+'\n\nSource model and perrun rawhashes/feedbackwarnings/exclusions are in reconstruction.json. CSV and ASCII PLY retain measured points in camera coordinates and mm under reported18mm calibration scale. Regenerate using scripts/reconstruct_sparse_shoe.py into a newoutputfolder.\n',encoding='utf-8')
    register=Path('EXPERIMENT_RUN_REGISTER.csv')
    with register.open(newline='',encoding='utf-8-sig') as f:
        reader=csv.DictReader(f);fields=reader.fieldnames;existing={r['run_id'] for r in reader}
    rows=[]
    for obs in observations:
        run=obs.get('run_id')
        if not run:continue
        d=Path('outputs/static_checks')/run;row=dict.fromkeys(fields,'')
        row.update(run_id=run,block='P6',status='preliminary_sparse_object_APS',condition_id='shoe_static_positions',firmware_version='1.7',
                   actual_exposure_ms=10,servo_min_us=obs['command_us'],servo_max_us=obs['command_us'],raw_aedat4_path=obs['raw'],
                   feedback_log_path=str(d/'samples.csv'),status_log_path=str(d/'operation.json'),processed_output_path=str(out),
                   notes='FrozenABDE2; no independentobjectaccuracy; clippingexclusions; ADCwarningsretained; finaloff/disarm/release')
        if run not in existing:rows.append(row)
    with register.open('a',newline='',encoding='utf-8') as f:csv.DictWriter(f,fields).writerows(rows)
    controller=json.load(urllib.request.urlopen('http://127.0.0.1:8933/rig/status'))['controller'];camera=json.load(urllib.request.urlopen('http://127.0.0.1:8931/status'))
    (out/'final_status.json').write_text(json.dumps(dict(controller=controller,camera={key:camera[key] for key in ('recording','actual_exposure_us','stale')}),indent=2))
    handoff=Path('PROJECT_HANDOFF_CURRENT.md');prior=handoff.read_text(encoding='utf-8')
    handoff.write_text('NEWEST sparseSHOE actualAPSreconstruction in outputs/reconstruction/sparse_shoe_20261103_01/{REVIEW.md,reconstruction.json,points.csv,points.ply,point_cloud.png,stripe_montage.png}. FrozenABDE2, sixstaticpositions, noalignment/refit. Readpointcounts/exclusions; calibratedmm provisional, noindependentobjectaccuracy/fullsurface/event3Dclaim. Someclippedrowsremoved. First1602movebadackfreshstatusconfirmed1602/offrelease; separate1602capture02valid no repeatedmove. Allraw/manifests/registersaved. Finaloff/disarm/release35msrestored.\n\n'+prior,encoding='utf-8')
    print(json.dumps(dict(points=len(points),observations=observations),indent=2))


if __name__=='__main__':main()
