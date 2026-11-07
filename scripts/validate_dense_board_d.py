"""Evaluate frozen dense A/B/C planes on reserved D, without refitting/alignment."""
import hashlib
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scripts.validate_static_plane import fixed_plane_residuals


def main():
    modelpath=Path('outputs/calibration/dense_planes_ABC_20261103_01/planes.json')
    digest=hashlib.sha256(modelpath.read_bytes()).hexdigest()
    assert digest==json.loads((modelpath.parent/'frozen_model.json').read_text())['planes_sha256'],'Frozen model changed'
    before=json.loads(Path('outputs/agent_control/dense_board_D_ref_20261103_01/board_check.json').read_text())
    assert digest==before['frozen_model_sha256_before_capture'],'Model changed after D capture began'
    model=json.loads(modelpath.read_text())
    reviewpath=Path('outputs/calibration/dense_board_D_review_20261103_03/observations.json')
    review=json.loads(reviewpath.read_text());index={o['command_us']:o for o in review['observations']}
    intr=json.loads(Path(model['intrinsics']).read_text())['models']['primary_five_coefficient'];k=np.array(intr['camera_matrix']);dist=np.array(intr['distortion_coefficients'])
    out=Path('outputs/calibration/dense_planes_D_validation_20261103_01');out.mkdir(parents=True,exist_ok=False)
    results=[]
    for p in model['planes']:
        command=p['command_us'];o=index[command]
        if 'normal_camera' not in p:
            results.append(dict(command_us=command,status='NO_FROZEN_PLANE',pose_count=p['pose_count']));continue
        if 'observation' not in o:
            results.append(dict(command_us=command,status='TEST_INPUT_REJECTED',reason=o['reason']));continue
        obs=o['observation']
        assert all(a['recording']!=obs['recording'] for a in p['observations']),'Test used in training'
        try:
            metrics,predicted,depth,orthogonal=fixed_plane_residuals(obs['pixels'],np.array(obs['points_camera_mm']),k,dist,np.array(p['normal_camera']),p['offset_mm'])
            results.append(dict(command_us=command,status='RESERVED_POSE_METRICS_NO_PREDECLARED_PASS_THRESHOLD',training_pose_count=p['pose_count'],metrics=metrics,observation=obs,
                                predicted_points_camera_mm=predicted.tolist(),depth_errors_mm=depth.tolist(),orthogonal_errors_mm=orthogonal.tolist()))
        except ValueError as exc:results.append(dict(command_us=command,status='GEOMETRIC_FAILURE',reason=str(exc)))
    limits=('D was excluded from fitting, and frozen model hash verified before/after capture. No test alignment, refit or bias correction. '
            'One reserved physical pose, not independent absolute ground truth: shared candidate camera intrinsics and reported18mm scale/flatness. '
            'Rows/frames correlated, not independent repeats. No predeclared numeric pass threshold. '
            'Two-pose and three-pose planes separately labelled; feedback warnings retained. No event/APS comparison, timing or continuous scan claim.')
    result=dict(model=str(modelpath),model_sha256=digest,model_modified=False,test_alignment_applied=False,results=results,
                review=dict(path=str(reviewpath),sha256=hashlib.sha256(reviewpath.read_bytes()).hexdigest()),limitations=limits)
    assert hashlib.sha256(modelpath.read_bytes()).hexdigest()==digest
    (out/'validation.json').write_text(json.dumps(result,indent=2))
    good=[r for r in results if 'metrics'in r]
    if good:
        fig,ax=plt.subplots(figsize=(9,4.8));x=[r['command_us'] for r in good]
        ax.plot(x,[r['metrics']['depth_rmse_mm'] for r in good],'o-',label='Depth RMSE');ax.plot(x,[r['metrics']['signed_depth_bias_mm'] for r in good],'s-',label='Signed depth bias')
        ax.axhline(0,color='k',lw=.6);ax.set(xlabel='Servo command (µs)',ylabel='Depth error against posed board (mm)',title='Frozen dense planes: reserved board pose D');ax.legend();ax.grid(alpha=.2)
        fig.text(.5,.01,'One board pose; shared K / reported18mm scale. No test refit/alignment; rows correlated.',ha='center',fontsize=8);fig.tight_layout(rect=[0,.04,1,1]);fig.savefig(out/'depth_errors.png',dpi=180)
    lines=['# Reserved dense board-pose D validation','',limits,'','| Command (µs) | Training poses | Rows | Depth RMSE (mm) | Signed bias (mm) | Outcome |','|---|---|---|---|---|---|']
    for r in results:
        m=r.get('metrics',{});lines.append(f"| {r['command_us']} | {r.get('training_pose_count','—')} | {m.get('rows','—')} | {m.get('depth_rmse_mm','—')} | {m.get('signed_depth_bias_mm','—')} | {r.get('reason',r['status'])} |")
    (out/'REVIEW.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(dict(output=str(out),measured_commands=len(good),results=[dict(command_us=r['command_us'],metrics=r.get('metrics'),status=r['status'],reason=r.get('reason')) for r in results]),indent=2))


if __name__=='__main__':main()
