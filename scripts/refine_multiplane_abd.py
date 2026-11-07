"""Add board pose D to A/B training, compare on unchanged diagnostic pose C."""
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
from scripts.fit_static_plane import fit_plane
from scripts.validate_static_plane import fixed_plane_residuals


def main():
    base=Path('outputs/calibration/multiplane_AB_20261103_01')
    modelpath=base/'planes.json';digest=hashlib.sha256(modelpath.read_bytes()).hexdigest()
    if digest!=json.loads((base/'frozen_model.json').read_text())['planes_sha256']:raise ValueError('AB model changed')
    old=json.loads(modelpath.read_text())
    cpath=Path('outputs/calibration/multiplane_C_validation_20261103_01/validation.json')
    ctest=json.loads(cpath.read_text());cdigest=hashlib.sha256(cpath.read_bytes()).hexdigest()
    bycommand={r['command_us']:r for r in ctest['results'] if 'metrics' in r}
    intr=json.loads(Path(old['intrinsics']).read_text())['models']['primary_five_coefficient']
    k=np.array(intr['camera_matrix']);dist=np.array(intr['distortion_coefficients'])
    out=Path('outputs/calibration/multiplane_ABD_20261103_01');out.mkdir(parents=True,exist_ok=False)
    planes=[];comparisons=[]
    for plane in old['planes']:
        command=plane['command_us']
        if plane['status']=='REJECTED':continue
        try:
            d,pd=extract('D',command,k,dist)
            observations=plane['observations']+[d]
            groups=[np.array(o['points_camera_mm']) for o in observations]
            n,offset,spread=fit_plane(groups)
            fit=dict(command_us=command,status='THREE_POSE_TRAINING_FIT',normal_camera=n.tolist(),offset_mm=offset,
                     weighted_spread_mm=spread.tolist(),observations=observations,
                     training_orthogonal_rms_mm=[float(np.sqrt(np.mean((g@n+offset)**2))) for g in groups])
            planes.append(fit)
            if command in bycommand:
                reserved=bycommand[command];o=reserved['observation'];points=np.array(o['points_camera_mm'])
                metrics,predicted,depth,orthogonal=fixed_plane_residuals(o['pixels'],points,k,dist,n,offset)
                comparisons.append(dict(command_us=command,old_metrics=reserved['metrics'],new_metrics=metrics,
                                        c_pixels_unchanged=True,predicted_points_camera_mm=predicted.tolist(),
                                        depth_errors_mm=depth.tolist()))
        except Exception as exc:planes.append(dict(command_us=command,status='D_INPUT_REJECTED',reason=str(exc)))
    result=dict(intrinsics=old['intrinsics'],training_poses=['A2','B','D'],C_in_fit=False,
                source_AB_sha256=digest,source_C_validation_sha256=cdigest,planes=planes,
                limitations='PoseD added after inspecting diagnosticC errors. C remains excluded from fit but is no longer an untouched final test. SameC stripe coordinates/K/reported18mmscale, no testalignment or biascorrection. OneC physicalpose, correlatedrows, unresolvedmechanicalrepeatability/targetflatness, no absoluteaccuracy or continuousscan claim.')
    path=out/'planes.json';path.write_text(json.dumps(result,indent=2))
    (out/'frozen_model.json').write_text(json.dumps(dict(planes_sha256=hashlib.sha256(path.read_bytes()).hexdigest()),indent=2))
    (out/'C_comparison.json').write_text(json.dumps(dict(model_modified_old=False,C_in_fit=False,comparisons=comparisons,limitations=result['limitations']),indent=2))
    if comparisons:
        x=np.arange(len(comparisons));fig,ax=plt.subplots(figsize=(9,4.8))
        ax.bar(x-.18,[r['old_metrics']['depth_rmse_mm'] for r in comparisons],.36,label='A/B fit')
        ax.bar(x+.18,[r['new_metrics']['depth_rmse_mm'] for r in comparisons],.36,label='A/B/D fit')
        ax.set_xticks(x,[str(r['command_us']) for r in comparisons]);ax.set(xlabel='Servo command (µs)',ylabel='Depth RMSE on diagnostic pose C (mm)',title='Adding a third training pose: same C data excluded from both fits')
        ax.legend();fig.text(.5,.01,'C had already been inspected; diagnostic comparison, not untouched final test. Shared K / reported18mm scale.',ha='center',fontsize=8)
        fig.tight_layout(rect=[0,.03,1,1]);fig.savefig(out/'C_comparison.png',dpi=180)
    lines=['# Added opposite-tilt board pose D','',result['limitations'],'',
           '| Command (µs) | A/B C-RMSE (mm) | A/B/D C-RMSE (mm) | New C bias (mm) |','|---|---|---|---|']
    for r in comparisons:
        lines.append(f"| {r['command_us']} | {r['old_metrics']['depth_rmse_mm']:.3f} | {r['new_metrics']['depth_rmse_mm']:.3f} | {r['new_metrics']['signed_depth_bias_mm']:.3f} |")
    lines+=['','Per-command input outcomes:']+[f"- {r['command_us']}: {r['status']} {r.get('reason','')}" for r in planes]
    lines+=['','No source data or earlier model overwritten. All D acquisitions retained, including feedback warnings. Training residuals are not independent depth accuracy. Reproduce with scripts/refine_multiplane_abd.py into a new output directory.']
    (out/'REVIEW.md').write_text('\n'.join(lines),encoding='utf-8')
    p=Path('EXPERIMENT_RUN_REGISTER.csv')
    with p.open(newline='',encoding='utf-8-sig') as f:
        rd=csv.DictReader(f);fields=rd.fieldnames;existing={r['run_id'] for r in rd}
    rows=[]
    for plane in planes:
        command=plane['command_us'];run=f'multiplane_D_{command}_20261103_01';d=Path('outputs/static_checks')/run
        row=dict.fromkeys(fields,'');row.update(run_id=run,block='P3',status=plane['status'],condition_id='opposite_tilt_poseD',
            firmware_version='1.7',actual_exposure_ms=10,servo_min_us=command,servo_max_us=command,
            raw_aedat4_path=f'data/raw/{run}.aedat4',feedback_log_path=str(d/'samples.csv'),status_log_path=str(d/'operation.json'),
            processed_output_path=str(out),notes='DaddedafterCinspection; Cexcludedfit; warningsretained; finaloff/disarm/release')
        if run not in existing:rows.append(row)
    with p.open('a',newline='',encoding='utf-8') as f:csv.DictWriter(f,fields).writerows(rows)
    controller=json.load(urllib.request.urlopen('http://127.0.0.1:8933/rig/status'))['controller']
    camera=json.load(urllib.request.urlopen('http://127.0.0.1:8931/status'))
    (out/'final_status.json').write_text(json.dumps(dict(controller=controller,camera={key:camera[key] for key in ('recording','actual_exposure_us','stale')}),indent=2))
    h=Path('PROJECT_HANDOFF_CURRENT.md');prior=h.read_text(encoding='utf-8')
    h.write_text('NEWEST opposite-tiltD captured8positions, fitABD version in outputs/calibration/multiplane_ABD_20261103_01/planes.json+REVIEW.md+C_comparison.json. Read percommandoutcomes/errorsbeforeclaims. OldAB unchanged, Cexcludedbothfits/samecoords/noalignment; DaddedafterCinspection so diagnosticcomparison notpristinefinaltest. D_ref01 hadmanuallaserON and failedcorners; STOP then D_ref02full54 used, D_after01motioncheck. Allraw/manifests/registersaved. No accuratefullobjectclaimyet. Finaloff/disarm/release35msrestored.\n\n'+prior,encoding='utf-8')
    print(json.dumps([dict(command_us=r['command_us'],old_rmse=r['old_metrics']['depth_rmse_mm'],new_rmse=r['new_metrics']['depth_rmse_mm'],new_bias=r['new_metrics']['signed_depth_bias_mm']) for r in comparisons],indent=2))


if __name__=='__main__':main()
