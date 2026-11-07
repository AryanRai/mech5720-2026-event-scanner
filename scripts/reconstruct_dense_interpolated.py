"""Exploratory denser APS shoe reconstruction with unvalidated plane interpolation."""
import csv
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request
import cv2
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter
from scripts.reconstruct_sparse_shoe import detect

COMMANDS=[1569,1573,1577,1581,1585,1590,1594,1598,1602,1606,1610,1614,1618,1622,1626,1631,1635,1639,1643,1647,1651]


def interpolate(planes,command):
    keys=sorted(planes)
    if not keys[0]<=command<=keys[-1]:raise ValueError('Refusing angular extrapolation outside acquired knots')
    lo=max(x for x in keys if x<=command);hi=min(x for x in keys if x>=command)
    first=planes[lo];second=planes[hi]
    n0=np.array(first['normal_camera']);n1=np.array(second['normal_camera']);d0=first['offset_mm'];d1=second['offset_mm']
    if n0@n1<0:n1=-n1;d1=-d1
    weight=0. if lo==hi else (command-lo)/(hi-lo)
    n=(1-weight)*n0+weight*n1;d=(1-weight)*d0+weight*d1;length=np.linalg.norm(n)
    if length<1e-8:raise ValueError('Degenerate interpolated plane')
    return n/length,d/length,dict(lower_command_us=lo,upper_command_us=hi,upper_weight=weight,
                                  independently_fitted_knot=lo==hi,method='Linear unit-normal/offset coefficients, common renormalisation; not a calibrated kinematic model')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--sensitive',action='store_true');args=parser.parse_args()
    modeldir=Path('outputs/calibration/multiplane_ABDE2_20261103_01');modelpath=modeldir/'planes.json'
    digest=hashlib.sha256(modelpath.read_bytes()).hexdigest()
    if digest!=json.loads((modeldir/'frozen_model.json').read_text())['planes_sha256']:raise ValueError('Model hash changed')
    model=json.loads(modelpath.read_text());planes={p['command_us']:p for p in model['planes'] if p['status']=='FOUR_POSE_TRAINING_FIT' and p['command_us']>=1569}
    intr=json.loads(Path(model['intrinsics']).read_text())['models']['primary_five_coefficient'];k=np.array(intr['camera_matrix']);dist=np.array(intr['distortion_coefficients'])
    out=Path('outputs/reconstruction/dense_shoe_interpolated_20261103_'+('02_sensitive' if args.sensitive else '01'));out.mkdir(parents=True,exist_ok=False)
    points=[];observations=[]
    for command in COMMANDS:
        run=f'dense_shoe_{command}_20261103_'+('02' if command==1602 else '01')
        raw=Path('data/raw')/(run+'.aedat4');d=Path('outputs/static_checks')/run
        if not (d/'summary.json').exists():
            observations.append(dict(command_us=command,run_id=run,status='NOT_COMPLETED'));continue
        trace=json.loads((d/'summary.json').read_text())
        if trace['errors']:
            observations.append(dict(command_us=command,run_id=run,status='INVALID_TRACE_EXCLUDED',errors=trace['errors']));continue
        n,offset,interpolation=interpolate(planes,command)
        pixels,screen,peak=detect(raw,delta_threshold=20 if args.sensitive else 40,intensity_threshold=40 if args.sensitive else 80)
        cv2.imwrite(str(out/f'laser_on_{command}.png'),peak)
        observation=dict(command_us=command,run_id=run,raw=str(raw),sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),
                         status='NO_RETAINED_STRIPE',screen=screen,interpolation=interpolation,plane_normal=n.tolist(),plane_offset_mm=offset,
                         feedback_warning=trace['feedback_screen_warning'])
        if len(pixels):
            xy=cv2.undistortPoints(pixels.reshape(-1,1,2),k,dist).reshape(-1,2)
            rays=np.column_stack((xy,np.ones(len(xy))));den=rays@n
            valid=abs(den)>1e-8;scale=np.full(len(rays),np.nan);scale[valid]=-offset/den[valid];valid&=np.isfinite(scale)&(scale>0)
            xyz=rays[valid]*scale[valid,None]
            for pixel,p in zip(pixels[valid],xyz):points.append([command,float(pixel[0]),float(pixel[1]),*map(float,p)])
            observation.update(status='EXPLORATORY_RECONSTRUCTED',points=len(xyz),nonpositive_or_parallel_rays_rejected=int((~valid).sum()),
                               depth_range_mm=[float(xyz[:,2].min()),float(xyz[:,2].max())] if len(xyz) else None)
        observations.append(observation)
    array=np.array(points)
    if not len(array):raise ValueError('No reconstructedpoints; source acquisitions preserved')
    with (out/'points.csv').open('w',newline='') as f:
        writer=csv.writer(f);writer.writerow(['command_us','pixel_x','pixel_y','X_mm','Y_mm','Z_mm']);writer.writerows(points)
    with (out/'points.ply').open('w') as f:
        f.write('ply\nformat ascii 1.0\nelement vertex '+str(len(points))+'\nproperty float x\nproperty float y\nproperty float z\nend_header\n')
        for row in points:f.write(' '.join(map(str,row[3:]))+'\n')
    limitation='EXPLORATORY interpolated-plane APS reconstruction. Intermediate planes unvalidated; denserappearance does not establish betteraccuracy. Acquiredangles remain inside1569..1651knots, but shoedepth is outside330..439mm trainingboardrange. Camera scale fromreported18mm pitch. No independent shoe groundtruth, densecalibration, event3D result, completeness, mesh or interpolationerrorbound. Same objectdetector as sparse; correlatedrows/frames not independentrepeat trials. No testalignment, biascorrection or calibrationrefit.'
    if args.sensitive:
        limitation=limitation.replace('Same objectdetector as sparse;','Postpilot lower-threshold sensitivity analysis; original sparse detector result retained separately. Dark pixel candidates are not detectorprecision/recall validation;')
    result=dict(status='EXPLORATORY_DENSER_INTERPOLATED_PLANE_RECONSTRUCTION',model=str(modelpath),model_sha256=digest,
                detector_mode='Sensitive postpilot screen delta>20 APS>40, darkcontrols retained, same row/frame support and clipping exclusions' if args.sensitive else 'Original sparse detector delta>40 APS>80',
                commands=COMMANDS,exposure_us=3000,points=len(points),contributing_positions=len(set(array[:,0])),
                original_sparse_points=379,original_sparse_positions=5,comparison_note='Exposure changed10ms to3ms after pilot; densitycomparison is descriptive, not controlledaccuracycomparison.',
                observations=observations,limitations=limitation)
    (out/'reconstruction.json').write_text(json.dumps(result,indent=2))
    fig=plt.figure(figsize=(11,5.8));ax=fig.add_subplot(121,projection='3d');side=fig.add_subplot(122)
    sc=ax.scatter(array[:,3],array[:,5],-array[:,4],c=array[:,0],cmap='viridis',s=5)
    side.scatter(array[:,5],-array[:,4],c=array[:,0],cmap='viridis',s=5)
    ax.set(xlabel='Camera X (mm)',ylabel='Camera Z / depth (mm)',zlabel='−Camera Y (mm)');ax.view_init(elev=24,azim=-62)
    side.set(xlabel='Camera Z / depth (mm)',ylabel='−Camera Y (mm)',title='Retained stripe profiles')
    fig.colorbar(sc,ax=[ax,side],shrink=.6,pad=.06,label='Servo command (µs)')
    fig.suptitle('Exploratory denser shoe point cloud — interpolated laser planes',fontsize=14)
    fig.text(.5,.02,f'{len(points)} points / {len(set(array[:,0]))} positions • 3 ms APS • unvalidated intermediate planes and object accuracy',ha='center',fontsize=9)
    fig.subplots_adjust(top=.87,bottom=.15,left=.03,right=.83,wspace=.2);fig.savefig(out/'point_cloud.png',dpi=180)
    plt.close(fig)
    fig=plt.figure(figsize=(6.4,5.6));ax=fig.add_subplot(111,projection='3d')
    ax.scatter(array[:,3],array[:,5],-array[:,4],c=array[:,0],cmap='viridis',s=7)
    ax.set(xlabel='X (mm)',ylabel='Z / depth (mm)',zlabel='−Y (mm)',title='Exploratory interpolated-plane shoe scan')
    fig.text(.5,.025,'Measured stripe points • unvalidated depth / interpolation',ha='center',fontsize=9)
    def update(frame):ax.view_init(elev=24,azim=-62+frame*10);return []
    animation=FuncAnimation(fig,update,frames=36,interval=100);animation.save(out/'rotating_point_cloud.gif',writer=PillowWriter(fps=10),dpi=90)
    plt.close(fig)
    lines=['# Exploratory denser shoe scan','',f'{len(points)} retained points from {len(set(array[:,0]))} positions, compared with379points/fivepositions in the sparse capture. Exposurechanged, so this is a descriptive densitycount only.','',limitation,'',
           'Planes are linearly interpolated in unit-normal/offset coefficients with sign consistency and renormalisation. No angular extrapolation outside the fitted range; objectdistance does extrapolate beyond observed calibrationdistance. Saturated/ambiguous rows excluded. The original screen is retained separately from optional postpilot sensitivityanalysis; each records darkcontrols, thresholds and exclusions. 3ms pilot and refused5ms capture are retained separately.',result['detector_mode'],'',
           '| Command (µs) | Points | Outcome |','|---|---|---|']
    for obs in observations:lines.append(f"| {obs['command_us']} | {obs.get('points',0)} | {obs['status']} |")
    (out/'REVIEW.md').write_text('\n'.join(lines),encoding='utf-8')
    register=Path('EXPERIMENT_RUN_REGISTER.csv')
    with register.open(newline='',encoding='utf-8-sig') as f:
        reader=csv.DictReader(f);fields=reader.fieldnames;existing={r['run_id'] for r in reader}
    rows=[]
    for obs in observations:
        run=obs['run_id'];d=Path('outputs/static_checks')/run;row=dict.fromkeys(fields,'')
        row.update(run_id=run,block='P6',status=obs['status'],condition_id='shoe_interpolated_positions3ms',firmware_version='1.7',actual_exposure_ms=3,
                   servo_min_us=obs['command_us'],servo_max_us=obs['command_us'],raw_aedat4_path=obs.get('raw',''),feedback_log_path=str(d/'samples.csv'),
                   status_log_path=str(d/'operation.json'),processed_output_path=str(out),notes='Unvalidatedplaneinterpolation; outsidecalibrateddepthrange; noaccuracyclaim; finaloff/disarm/release')
        if run not in existing:rows.append(row)
    with register.open('a',newline='',encoding='utf-8') as f:csv.DictWriter(f,fields).writerows(rows)
    controller=json.load(urllib.request.urlopen('http://127.0.0.1:8933/rig/status'))['controller'];camera=json.load(urllib.request.urlopen('http://127.0.0.1:8931/status'))
    (out/'final_status.json').write_text(json.dumps(dict(controller=controller,camera={key:camera[key] for key in ('recording','actual_exposure_us','stale')}),indent=2))
    h=Path('PROJECT_HANDOFF_CURRENT.md');prior=h.read_text(encoding='utf-8')
    h.write_text(f'NEWEST exploratoryDENSERshoe {len(points)}points/{len(set(array[:,0]))}positions viaUNVALIDATEDplaneinterpolation1569..1651us, 3msAPS. {out} withREVIEW,JSON,CSV,PLY,PNG,rotatingGIF. Detector: '+result['detector_mode']+'. Noaccuracy/fullobject/event3Dclaim; shoecloserthantrainingboard330..439mm. Sparse379points preserved; exposure/detectormaychanged so notcontrolledcomparison. Allrunmanifests/registerretained. Finaloff/disarm/release35msrestored. UserwantsdensecheckerboardcalibrationNEXT; needboardposes physically atshoe workingdistances, rigfixed.\n\n'+prior,encoding='utf-8')
    print(json.dumps(dict(points=len(points),positions=len(set(array[:,0])),per_position=[dict(command=obs['command_us'],points=obs.get('points',0),status=obs['status']) for obs in observations]),indent=2))


if __name__=='__main__':main()
