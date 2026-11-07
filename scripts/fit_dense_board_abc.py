"""Fit retained dense A/B/C lines; report omitted-pose diagnostics separately."""
import hashlib
import json
from pathlib import Path
import numpy as np
from scripts.fit_static_plane import fit_plane
from scripts.validate_static_plane import fixed_plane_residuals


def main():
    paths=[Path(f'outputs/calibration/dense_board_{pose}_review_20261103_{version}/observations.json')
           for pose,version in (('A','02'),('B','03'),('C','03'))]
    reviews=[json.loads(p.read_text()) for p in paths]
    indexed=[{o['command_us']:o for o in r['observations']} for r in reviews]
    intr=json.loads(Path(reviews[0]['intrinsics']).read_text())['models']['primary_five_coefficient']
    k=np.array(intr['camera_matrix']);dist=np.array(intr['distortion_coefficients'])
    out=Path('outputs/calibration/dense_planes_ABC_20261103_01');out.mkdir(parents=True,exist_ok=False)
    planes=[];diagnostics=[]
    for command in reviews[0]['commands']:
        candidates=[idx[command] for idx in indexed]
        obs=[o['observation'] for o in candidates if o['status']=='ONE_POSE_GEOMETRY_CANDIDATE']
        if len(obs)<2:
            planes.append(dict(command_us=command,status='INSUFFICIENT_VALID_POSES',pose_count=len(obs)));continue
        groups=[np.array(o['points_camera_mm']) for o in obs]
        n,d,spread=fit_plane(groups)
        planes.append(dict(command_us=command,status='PRELIMINARY_THREE_POSE_FIT' if len(obs)==3 else 'PRELIMINARY_TWO_POSE_FIT',
                           pose_count=len(obs),normal_camera=n.tolist(),offset_mm=d,weighted_spread_mm=spread.tolist(),
                           observations=obs,training_orthogonal_rms_mm=[float(np.sqrt(np.mean((g@n+d)**2))) for g in groups]))
        if len(obs)==3:
            for held in range(3):
                try:
                    fn,fd,_=fit_plane([g for i,g in enumerate(groups) if i!=held])
                    metrics,_,_,_=fixed_plane_residuals(obs[held]['pixels'],groups[held],k,dist,fn,fd)
                    diagnostics.append(dict(command_us=command,omitted_pose=obs[held]['pose'],metrics=metrics))
                except ValueError as exc:
                    diagnostics.append(dict(command_us=command,omitted_pose=obs[held]['pose'],reason=str(exc)))
    limits=('Training fits and omitted-pose diagnostics share candidate intrinsics and reported18mm target scale. '
            'All three poses are training data; these diagnostics are not an untouched final test or independent absolute ground truth. '
            'No test alignment or bias correction. Rows/frames correlated; ADC warnings retained. '
            'Commands with only two valid poses remain explicitly labelled. Separate reserved poseD remains required. '
            'No continuous-sweep, physical timing, angle calibration or event-versus-APS performance claim.')
    result=dict(intrinsics=reviews[0]['intrinsics'],training_poses=['dense_board_A','dense_board_B','dense_board_C'],
                planes=planes,source_reviews=[dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in paths],limitations=limits)
    p=out/'planes.json';p.write_text(json.dumps(result,indent=2))
    (out/'frozen_model.json').write_text(json.dumps(dict(planes_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),purpose='Frozen before reserved poseD'),indent=2))
    (out/'omitted_pose_diagnostics.json').write_text(json.dumps(dict(results=diagnostics,limitations=limits),indent=2))
    lines=['# Preliminary dense A/B/C planes','',limits,'','| Command (µs) | Valid poses | Training orthogonal RMS (mm) |','|---|---|---|']
    for plane in planes:lines.append(f"| {plane['command_us']} | {plane['pose_count']} | {plane.get('training_orthogonal_rms_mm',plane['status'])} |")
    lines+=['','## Omitted-pose diagnostics','','| Command (µs) | Omitted pose | Depth RMSE (mm) | Signed bias (mm) |','|---|---|---|---|']
    for row in diagnostics:
        m=row.get('metrics',{});lines.append(f"| {row['command_us']} | {row['omitted_pose']} | {m.get('depth_rmse_mm',row.get('reason'))} | {m.get('signed_depth_bias_mm','—')} |")
    (out/'REVIEW.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(dict(output=str(out),three_pose=sum(p['pose_count']==3 for p in planes),two_pose=sum(p['pose_count']==2 for p in planes),diagnostics=diagnostics),indent=2))


if __name__=='__main__':main()
