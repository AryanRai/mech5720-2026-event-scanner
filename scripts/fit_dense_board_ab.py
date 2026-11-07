"""Freeze preliminary dense per-command planes from reviewed A/B observations."""
import hashlib
import json
from pathlib import Path
import numpy as np
from scripts.fit_static_plane import fit_plane


def main():
    paths=[Path(f'outputs/calibration/dense_board_{pose}_review_20261103_{version}/observations.json') for pose,version in (('A','02'),('B','03'))]
    reviews=[json.loads(p.read_text()) for p in paths]
    indexed=[{o['command_us']:o for o in review['observations']} for review in reviews]
    output=Path('outputs/calibration/dense_planes_AB_20261103_02');output.mkdir(parents=True,exist_ok=False)
    planes=[]
    for command in reviews[0]['commands']:
        candidates=[idx[command] for idx in indexed]
        if any(o['status']!='ONE_POSE_GEOMETRY_CANDIDATE' for o in candidates):
            planes.append(dict(command_us=command,status='INSUFFICIENT_VALID_POSES',pose_statuses=[o['status'] for o in candidates]));continue
        observations=[o['observation'] for o in candidates]
        groups=[np.array(o['points_camera_mm']) for o in observations]
        normal,offset,spread=fit_plane(groups)
        planes.append(dict(command_us=command,status='PRELIMINARY_TWO_POSE_PLANE_NOT_VALIDATED',normal_camera=normal.tolist(),
                           offset_mm=offset,weighted_spread_mm=spread.tolist(),observations=observations,
                           training_orthogonal_rms_mm=[float(np.sqrt(np.mean((g@normal+offset)**2))) for g in groups]))
    result=dict(status='PRELIMINARY_DENSE_CALIBRATION_NOT_VALIDATED',intrinsics=reviews[0]['intrinsics'],planes=planes,
                source_reviews=[dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in paths],
                limitations='Two board poses only. Dense commands independently fitted, not interpolated, but small trainingresiduals are not depthaccuracy. Near-collinearboardlines can poorlyconditionplanes. Need distinctthirdtrainingdistancepose and separatelyreservedtestpose. Reported18mmscale/flatness and ADC-to-angle physicalcalibration unverified. Correlatedrows/frames not repeats. No eventvsAPS or continuousdepthvalidation.')
    p=output/'planes.json';p.write_text(json.dumps(result,indent=2))
    (output/'frozen_model.json').write_text(json.dumps(dict(planes_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),purpose='PreliminaryAB model retained before additional training/validation'),indent=2))
    good=[p for p in planes if p['status']=='PRELIMINARY_TWO_POSE_PLANE_NOT_VALIDATED']
    lines=['# Preliminary dense planes from A/B','',f'{len(good)} independently fitted command planes. These are training fits, not validated accuracy.','',result['limitations'],'',
           '| Command (µs) | A/B orthogonal RMS (mm) | Second spatial spread (mm) |','|---|---|---|']
    for p in planes:
        lines.append(f"| {p['command_us']} | {p.get('training_orthogonal_rms_mm',p['status'])} | {p.get('weighted_spread_mm',[None,None])[1]} |")
    (output/'REVIEW.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(dict(fitted=len(good),total=len(planes),output=str(output))))


if __name__=='__main__':main()
