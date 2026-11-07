"""Review one dense calibration pose with frozen compact-board extraction."""
import argparse
import csv
import json
from pathlib import Path
import urllib.request
import numpy as np
import cv2
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scripts.fit_multiplane import extract
from scripts.reconstruct_dense_interpolated import COMMANDS


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--pose',required=True);parser.add_argument('--version',default='02');args=parser.parse_args()
    prefix='dense_board_'+args.pose
    out=Path('outputs/calibration')/(prefix+'_review_20261103_'+args.version);out.mkdir(parents=True,exist_ok=False)
    intrpath=Path('outputs/calibration/take06_refined_20261102/refined_intrinsics.json')
    intr=json.loads(intrpath.read_text())['models']['primary_five_coefficient'];k=np.array(intr['camera_matrix']);dist=np.array(intr['distortion_coefficients'])
    observations=[]
    for command in COMMANDS:
        try:
            observation,xyz=extract(prefix,command,k,dist)
            observations.append(dict(command_us=command,status='ONE_POSE_GEOMETRY_CANDIDATE',observation=observation,
                                     rows=len(xyz),Z_range_mm=[float(xyz[:,2].min()),float(xyz[:,2].max())]))
        except Exception as exc:observations.append(dict(command_us=command,status='INPUT_REJECTED',reason=str(exc)))
    result=dict(pose=args.pose,intrinsics=str(intrpath),commands=COMMANDS,observations=observations,
                detector='Unchanged compactboard extraction: delta>40 APS>60; innercornerhull expanded13px; dominantcolumn+/-8; >=15rows span>=40px; >=5frames; <=1%clipping; board-motion<=0.5px; reprojection<=0.5px; physicalboardextent. Sourcecode scripts/fit_multiplane.py.',
                limitations='One boardpose only; no denseplanes fitted yet. Reported18mm targetscale/flatness unverified. CameraK reused with unchangedoptics. ADCwarnings retained, not physicalstabilitycertification. No degrees, denseinterpolationerrorbound, independentdepthaccuracy or events-vs-APS performance claim.')
    (out/'observations.json').write_text(json.dumps(result,indent=2))
    good=[o for o in observations if o['status']=='ONE_POSE_GEOMETRY_CANDIDATE']
    if good:
        fig,ax=plt.subplots(figsize=(8,5))
        ax.imshow(cv2.imread(good[0]['observation']['board_before'],0),cmap='gray',vmin=0,vmax=255)
        for obs in good:
            pixels=np.array(obs['observation']['pixels'])
            ax.scatter(pixels[:,0],pixels[:,1],c=np.full(len(pixels),obs['command_us']),cmap='viridis',vmin=min(COMMANDS),vmax=max(COMMANDS),s=5)
        ax.set(title=f'Dense board pose {args.pose}: retained measured stripe pixels',xlabel='Native image x (px)',ylabel='Native image y (px)')
        fig.text(.5,.015,'One board pose only; these observations do not define complete laser planes.',ha='center',fontsize=9)
        fig.tight_layout(rect=[0,.04,1,1]);fig.savefig(out/'board_stripes.png',dpi=180)
    lines=[f'# Dense checkerboard pose {args.pose}','',f'{len(good)} of {len(COMMANDS)} commands produced candidate board-stripe geometry. No plane fit from this pose alone.','',
           '| Command (µs) | Rows | Outcome | Feedback warning |','|---|---|---|---|']
    for obs in observations:
        lines.append(f"| {obs['command_us']} | {obs.get('rows',0)} | {obs.get('reason',obs['status'])} | {obs.get('observation',{}).get('feedback_warning','—')} |")
    lines+=['',result['detector'],'',result['limitations']]
    (out/'REVIEW.md').write_text('\n'.join(lines),encoding='utf-8')
    register=Path('EXPERIMENT_RUN_REGISTER.csv')
    with register.open(newline='',encoding='utf-8-sig') as f:
        reader=csv.DictReader(f);fields=reader.fieldnames;existing={r['run_id'] for r in reader}
    rows=[]
    for obs in observations:
        command=obs['command_us'];suffix='02' if args.pose=='A' and command in (1594,1602) else '03' if args.pose=='A' and command==1606 else '01';run=f'{prefix}_{command}_20261103_'+suffix;d=Path('outputs/static_checks')/run
        if args.pose=='B' and command in (1631,1610):
            run=f'{prefix}_{command}_20261103_02';d=Path('outputs/static_checks')/run
        if args.pose=='C' and command==1635:
            run=f'{prefix}_{command}_20261103_02';d=Path('outputs/static_checks')/run
        if args.pose=='D' and command==1631:
            run=f'{prefix}_{command}_20261103_02';d=Path('outputs/static_checks')/run
        raw=Path(f'data/raw/{run}.aedat4')
        if not raw.exists():continue
        row=dict.fromkeys(fields,'');row.update(run_id=run,block='P3',status=obs['status'],condition_id=prefix,firmware_version='1.7',
            actual_exposure_ms=10,servo_min_us=command,servo_max_us=command,raw_aedat4_path=f'data/raw/{run}.aedat4',
            feedback_log_path=str(d/'samples.csv'),status_log_path=str(d/'operation.json'),processed_output_path=str(out),
            rejection_reason=obs.get('reason',''),notes='One denseboardpose only; no planefit. AllADCwarningsretained; finaloff/disarm/release. See review for incompletecommands/refusals.')
        if run not in existing:rows.append(row)
    with register.open('a',newline='',encoding='utf-8') as f:csv.DictWriter(f,fields).writerows(rows)
    controller=json.load(urllib.request.urlopen('http://127.0.0.1:8933/rig/status'))['controller'];camera=json.load(urllib.request.urlopen('http://127.0.0.1:8931/status'))
    (out/'final_status.json').write_text(json.dumps(dict(controller=controller,camera={key:camera[key] for key in ('recording','actual_exposure_us','stale')}),indent=2))
    handoff=Path('PROJECT_HANDOFF_CURRENT.md');prior=handoff.read_text(encoding='utf-8')
    handoff.write_text(f'NEWEST DENSEcheckerboard pose{args.pose} review {out}/REVIEW.md+observations.json: {len(good)}/21candidatecommands1569..1651,10msAPS/1sboundedobserveeach. Read inputrejections andADCwarnings; no denseplanes fitted fromonepose. Boardref/aftersnapshots saved, allraw/manifests/registerretained. Camera35msrestored,finaloff/disarm/release. Nextphysical BOARDonly opposite-tilt pose whilekeepingrigfixed; then thirdtrainingdistancepose and separatereservedtestpose planned. UserintendsmoveSHOEback toboardworkingdistance ratherthannewsmallerboard; leavecamera/laserfocusunchanged initially. ExistingdenseSHOEresultusesunvalidatedinterpolatedplanes, separate fromthisnewcalibration.\n\n'+prior,encoding='utf-8')
    print(json.dumps(dict(pose=args.pose,usable=len(good),total=len(COMMANDS),results=[{key:obs.get(key) for key in ('command_us','status','rows','reason')} for obs in observations]),indent=2))


if __name__=='__main__':main()
