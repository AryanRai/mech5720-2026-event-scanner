"""Test frozen ABD on new E, then add E to training and compare diagnostic C."""
import csv
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scripts.fit_multiplane import extract
from scripts.fit_static_plane import fit_plane
from scripts.validate_static_plane import fixed_plane_residuals


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pose',default='E',choices=['E','E2'])
    args=parser.parse_args();pose=args.pose
    base=Path('outputs/calibration/multiplane_ABD_20261103_01');source=base/'planes.json'
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    if digest!=json.loads((base/'frozen_model.json').read_text())['planes_sha256']:raise ValueError('ABD hash changed')
    model=json.loads(source.read_text())
    intr=json.loads(Path(model['intrinsics']).read_text())['models']['primary_five_coefficient']
    k=np.array(intr['camera_matrix']);dist=np.array(intr['distortion_coefficients'])
    cpath=Path('outputs/calibration/multiplane_C_validation_20261103_01/validation.json')
    cdata=json.loads(cpath.read_text());ctest={r['command_us']:r for r in cdata['results'] if 'metrics' in r}
    previous=json.loads((base/'C_comparison.json').read_text())
    previous={r['command_us']:r['new_metrics'] for r in previous['comparisons']}
    out=Path(f'outputs/calibration/multiplane_ABD{pose}_20261103_01');out.mkdir(parents=True,exist_ok=False)
    tests=[];planes=[];comparisons=[]
    for plane in model['planes']:
        command=plane['command_us']
        if plane['status']!='THREE_POSE_TRAINING_FIT':continue
        try:
            obs,points=extract(pose,command,k,dist)
            metrics,predicted,depth,orthogonal=fixed_plane_residuals(obs['pixels'],points,k,dist,np.array(plane['normal_camera']),plane['offset_mm'])
            tests.append(dict(command_us=command,status='FROZEN_ABD_TEST_ON_E',metrics=metrics,observation=obs,
                              predicted_points_camera_mm=predicted.tolist(),depth_errors_mm=depth.tolist()))
            observations=plane['observations']+[obs];groups=[np.array(o['points_camera_mm']) for o in observations]
            n,offset,spread=fit_plane(groups)
            planes.append(dict(command_us=command,status='FOUR_POSE_TRAINING_FIT',normal_camera=n.tolist(),offset_mm=offset,
                               weighted_spread_mm=spread.tolist(),observations=observations,
                               training_orthogonal_rms_mm=[float(np.sqrt(np.mean((g@n+offset)**2))) for g in groups]))
            if command in ctest:
                reference=ctest[command]['observation']
                new,_,_,_=fixed_plane_residuals(reference['pixels'],np.array(reference['points_camera_mm']),k,dist,n,offset)
                comparisons.append(dict(command_us=command,ABD_metrics=previous[command],ABDE_metrics=new,C_in_fit=False))
        except Exception as exc:
            tests.append(dict(command_us=command,status='E_INPUT_REJECTED',reason=str(exc)))
            planes.append(dict(command_us=command,status='E_INPUT_REJECTED',reason=str(exc)))
    # Save the model-fixed E test separately before publishing the extended fit.
    limitation='E first tested against unchanged ABD model, then added to training. It ceases to be a test set for ABDE. C excluded allfits but previouslyinspected repeatedly: diagnosticcomparison only. SharedcandidateK/reported18mmscale, onepose each, correlatedrows. No absoluteaccuracy, independentrepeatreliability or continuoussweep validation.'
    (out/'E_test_frozen_ABD.json').write_text(json.dumps(dict(source_ABD_sha256=digest,model_modified=False,results=tests,limitations=limitation),indent=2))
    result=dict(intrinsics=model['intrinsics'],training_poses=['A2','B','D',pose],C_in_fit=False,planes=planes,limitations=limitation)
    path=out/'planes.json';path.write_text(json.dumps(result,indent=2))
    (out/'frozen_model.json').write_text(json.dumps(dict(planes_sha256=hashlib.sha256(path.read_bytes()).hexdigest()),indent=2))
    (out/'C_comparison.json').write_text(json.dumps(dict(comparisons=comparisons,limitations=limitation),indent=2))
    good=[r for r in tests if 'metrics' in r]
    fig,axes=plt.subplots(1,2,figsize=(11,4.8))
    if good:
        axes[0].plot([r['command_us'] for r in good],[r['metrics']['depth_rmse_mm'] for r in good],'o-',label='RMSE')
        axes[0].plot([r['command_us'] for r in good],[r['metrics']['signed_depth_bias_mm'] for r in good],'s-',label='Bias')
    axes[0].set(title='New E pose: frozen ABD model',xlabel='Servo command (µs)',ylabel='Depth error (mm)');axes[0].legend()
    if comparisons:
        x=np.arange(len(comparisons));axes[1].bar(x-.18,[r['ABD_metrics']['depth_rmse_mm'] for r in comparisons],.36,label='ABD')
        axes[1].bar(x+.18,[r['ABDE_metrics']['depth_rmse_mm'] for r in comparisons],.36,label='ABDE')
        axes[1].set_xticks(x,[str(r['command_us']) for r in comparisons])
    axes[1].set(title='Diagnostic C: adding E to training',xlabel='Servo command (µs)',ylabel='Depth RMSE (mm)');axes[1].legend()
    fig.text(.5,.01,'Shared K / reported18mm scale. C inspected previously; E becomes training data only after left-panel test.',ha='center',fontsize=8)
    fig.tight_layout(rect=[0,.03,1,1]);fig.savefig(out/'pose_E_comparison.png',dpi=180)
    lines=['# Further-distance pose E','',limitation,'','## New E pose tested against frozen ABD','',
           '| Command (µs) | Depth RMSE (mm) | Bias (mm) |','|---|---|---|']
    for r in tests:
        m=r.get('metrics')
        lines.append(f"| {r['command_us']} | {m['depth_rmse_mm']:.3f} | {m['signed_depth_bias_mm']:.3f} |" if m else f"| {r['command_us']} | Rejected | {r['reason']} |")
    lines+=['','## Adding E: same diagnostic C data excluded from fits','','| Command (µs) | ABD RMSE (mm) | ABDE RMSE (mm) |','|---|---|---|']
    for r in comparisons:lines.append(f"| {r['command_us']} | {r['ABD_metrics']['depth_rmse_mm']:.3f} | {r['ABDE_metrics']['depth_rmse_mm']:.3f} |")
    lines+=['','No earlier source/model overwritten. No constant biascorrection or per-test alignment. All retained warnings and input exclusions must accompany reconstruction claims.']
    (out/'REVIEW.md').write_text('\n'.join(lines),encoding='utf-8')
    register=Path('EXPERIMENT_RUN_REGISTER.csv')
    with register.open(newline='',encoding='utf-8-sig') as f:
        reader=csv.DictReader(f);fields=reader.fieldnames;existing={r['run_id'] for r in reader}
    rows=[]
    for test in tests:
        command=test['command_us'];run=f'multiplane_{pose}_{command}_20261103_'+('02' if pose=='E2' and command==1602 else '01');d=Path('outputs/static_checks')/run
        row=dict.fromkeys(fields,'');row.update(run_id=run,block='P3',status=test['status'],condition_id='further_distance_poseE',
            firmware_version='1.7',actual_exposure_ms=10,servo_min_us=command,servo_max_us=command,
            raw_aedat4_path=f'data/raw/{run}.aedat4',feedback_log_path=str(d/'samples.csv'),status_log_path=str(d/'operation.json'),
            processed_output_path=str(out),notes='EtestedonfrozenABD then addedfit; Cdiagnosticexcludedfit; no independentaccuracyclaim; finaloff/disarm/release')
        if run not in existing:rows.append(row)
    with register.open('a',newline='',encoding='utf-8') as f:csv.DictWriter(f,fields).writerows(rows)
    controller=json.load(urllib.request.urlopen('http://127.0.0.1:8933/rig/status'))['controller']
    camera=json.load(urllib.request.urlopen('http://127.0.0.1:8931/status'))
    (out/'final_status.json').write_text(json.dumps(dict(controller=controller,camera={key:camera[key] for key in ('recording','actual_exposure_us','stale')}),indent=2))
    h=Path('PROJECT_HANDOFF_CURRENT.md');prior=h.read_text(encoding='utf-8')
    h.write_text(f'NEWEST pose{pose} fartherdistance captured, testedfrozenABD then extendedfit; {out}/REVIEW.md + E_test_frozen_ABD.json + planes.json + C_comparison.json. Read outcomes beforeclaims. Cexcludedfits but repeatedlyinspected diagnostic only. Newposeceasestotestextendedmodel afteraddedtraining. Allraw/manifests/registerretained. Finaloff/disarm/release35ms. No fullobjectresultyet.\n\n'+prior,encoding='utf-8')
    print(json.dumps(dict(E_tests=[dict(command=r['command_us'],metrics=r.get('metrics'),reason=r.get('reason')) for r in tests],C_comparison=comparisons),indent=2))


if __name__=='__main__':main()
