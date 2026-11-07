"""Check frozen per-command planes on a separate physical board pose."""
import csv
import hashlib
import json
from pathlib import Path
import urllib.request
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scripts.fit_multiplane import extract
from scripts.validate_static_plane import fixed_plane_residuals


def main():
    modeldir=Path('outputs/calibration/multiplane_AB_20261103_01')
    modelpath=modeldir/'planes.json'
    digest=hashlib.sha256(modelpath.read_bytes()).hexdigest()
    if digest!=json.loads((modeldir/'frozen_model.json').read_text())['planes_sha256']:
        raise ValueError('Frozen model changed')
    model=json.loads(modelpath.read_text())
    intr=json.loads(Path(model['intrinsics']).read_text())['models']['primary_five_coefficient']
    k=np.array(intr['camera_matrix']);dist=np.array(intr['distortion_coefficients'])
    out=Path('outputs/calibration/multiplane_C_validation_20261103_01');out.mkdir(parents=True,exist_ok=False)
    results=[]
    for plane in model['planes']:
        command=plane['command_us']
        if plane['status']=='REJECTED':continue
        try:
            obs,points=extract('C',command,k,dist)
            metrics,predicted,depth,orthogonal=fixed_plane_residuals(obs['pixels'],points,k,dist,
                                                        np.array(plane['normal_camera']),plane['offset_mm'])
            results.append(dict(command_us=command,status='HELD_OUT_METRICS_NO_PREREGISTERED_PASS_THRESHOLD',
                                metrics=metrics,observation=obs,predicted_points_camera_mm=predicted.tolist(),
                                depth_errors_mm=depth.tolist(),point_to_plane_errors_mm=orthogonal.tolist()))
        except Exception as exc:results.append(dict(command_us=command,status='INPUT_SCREEN_REJECTED',reason=str(exc)))
    result=dict(model=str(modelpath),model_sha256=digest,model_modified=False,test_alignment_applied=False,
                results=results,limitations='One held-out boardpose, not independentabsolutegroundtruth: sharedcandidateK andreported18mmscale. Pixels/APSframes correlated. No refit or testalignment. No numericpass criterion predeclared. ADCwarnings retained. Percommandplanes only; not continuousfeedbackplane model or sweptdepthvalidation.')
    (out/'validation.json').write_text(json.dumps(result,indent=2))
    good=[r for r in results if 'metrics' in r]
    if good:
        x=[r['command_us'] for r in good]
        fig,ax=plt.subplots(figsize=(9,4.8))
        ax.plot(x,[r['metrics']['depth_rmse_mm'] for r in good],'o-',label='Depth RMSE')
        ax.plot(x,[r['metrics']['signed_depth_bias_mm'] for r in good],'s-',label='Signed depth bias')
        ax.axhline(0,color='k',linewidth=.7);ax.set(xlabel='Servo command (µs)',ylabel='Depth error (mm)',title='Frozen planes tested on one new board pose')
        ax.legend();ax.grid(alpha=.15)
        fig.text(.5,.01,'Shared camera model and reported 18 mm target scale; row points correlated; no model refit or test alignment.',ha='center',fontsize=8)
        fig.tight_layout(rect=[0,.03,1,1]);fig.savefig(out/'depth_errors.png',dpi=180)
    lines=['# Frozen multicommand plane validation','',
           'The camera/servo/laser/base remained fixed while the user changed the board pose. Eight candidate planes were frozen after A/B; this C pose was excluded from fitting. No numerical success threshold was preregistered.','',
           '| Command (µs) | Rows | Depth RMSE (mm) | Signed depth bias (mm) | Outcome |','|---|---|---|---|---|']
    for r in results:
        m=r.get('metrics')
        if m:lines.append(f"| {r['command_us']} | {m['rows']} | {m['depth_rmse_mm']:.3f} | {m['signed_depth_bias_mm']:.3f} | Measured |")
        else:lines.append(f"| {r['command_us']} | — | — | — | {r['reason']} |")
    lines+=['',result['limitations'],'',
            'These are preliminary discrepancies against a camera-posed checkerboard, not an independently measured absolute accuracy guarantee. Small training residuals do not override held-out errors. Do not apply a constant correction derived from this test. Repeat a relevant test condition before reporting repeatability across these new planes.','',
            'All eight source recordings and traces retained. Final service state saved separately. Reproduce with scripts/validate_multiplane.py into a new output directory.']
    (out/'REVIEW.md').write_text('\n'.join(lines),encoding='utf-8')
    p=Path('EXPERIMENT_RUN_REGISTER.csv')
    with p.open(newline='',encoding='utf-8-sig') as f:
        rd=csv.DictReader(f);fields=rd.fieldnames;existing={r['run_id'] for r in rd}
    rows=[]
    for r in results:
        command=r['command_us'];run=f'multiplane_C_{command}_20261103_01';d=Path('outputs/static_checks')/run
        row=dict.fromkeys(fields,'');row.update(run_id=run,block='P3',status=r['status'],condition_id='multiplane_heldoutC',
                  firmware_version='1.7',actual_exposure_ms=10,servo_min_us=command,servo_max_us=command,
                  raw_aedat4_path=f'data/raw/{run}.aedat4',feedback_log_path=str(d/'samples.csv'),
                  status_log_path=str(d/'operation.json'),processed_output_path=str(out),
                  notes='FrozenAB unchanged; no testalignment; sharedK/user18mmscale; finaloff/disarm/release')
        if run not in existing:rows.append(row)
    with p.open('a',newline='',encoding='utf-8') as f:csv.DictWriter(f,fields).writerows(rows)
    controller=json.load(urllib.request.urlopen('http://127.0.0.1:8933/rig/status'))['controller']
    camera=json.load(urllib.request.urlopen('http://127.0.0.1:8931/status'))
    (out/'final_status.json').write_text(json.dumps(dict(controller=controller,camera={key:camera[key] for key in ('recording','actual_exposure_us','stale')}),indent=2))
    handoff=Path('PROJECT_HANDOFF_CURRENT.md');prior=handoff.read_text(encoding='utf-8')
    handoff.write_text('NEWEST Nov3 multicommand heldoutC eightcaptures complete, frozenAB model unchanged/norefit/noalignment. Read outputs/calibration/multiplane_C_validation_20261103_01/REVIEW.md+validation.json for percommanderrors/inputrejections BEFOREclaims or objects. One testboardpose sharedK/18mmscale not independentabsoluteaccuracy. C_ref/after snapshots, allraw/manifests/registerretained. Finaloff/disarm/release35msrestored.\n\n'+prior,encoding='utf-8')
    print(json.dumps([dict(command_us=r['command_us'],metrics=r.get('metrics'),reason=r.get('reason')) for r in results],indent=2))


if __name__=='__main__':main()
