"""Preserve pose-C diagnostics without changing the frozen A/B calibration."""
import csv
import hashlib
import json
from pathlib import Path
import cv2
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scripts.fit_static_plane import intersect_board


def main():
    root = Path('outputs/calibration/static_plane1500_C_validation_20261102_01')
    result = json.loads((root/'validation.json').read_text())
    model_path = Path(result['model'])
    model = json.loads(model_path.read_text())
    intr = json.loads(Path(model['config']['intrinsics']).read_text())['models']['primary_five_coefficient']
    matrix, distortion = np.array(intr['camera_matrix']), np.array(intr['distortion_coefficients'])
    obs = result['observation']
    rotation = cv2.Rodrigues(np.array(obs['board_rvec']))[0]
    translation = np.array(obs['board_t_mm'])
    normal = np.array(model['normal_camera'])
    pixels = np.array(obs['pixels'])
    expected = []
    for x, y in pixels:
        def residual(u):
            point = intersect_board([[u, y]], matrix, distortion, rotation, translation)[0]
            return point @ normal + model['offset_mm']
        lo, hi = x-15, x+15
        if residual(lo)*residual(hi) >= 0:
            raise ValueError('Expected stripe not bracketed')
        for _ in range(50):
            mid = (lo+hi)/2
            if residual(lo)*residual(mid) <= 0: hi = mid
            else: lo = mid
        expected.append((lo+hi)/2)
    delta = pixels[:, 0]-expected
    diagnostic = dict(observed_minus_predicted_x_mean_px=float(delta.mean()),
                      observed_minus_predicted_x_range_px=[float(delta.min()), float(delta.max())],
                      expected_x_px=expected, observed_pixels=pixels.tolist(),
                      interpretation='Image-space discrepancy for frozen model at the same rows; does not identify cause.')
    (root/'image_space_diagnostic.json').write_text(json.dumps(diagnostic, indent=2))
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.8))
    axes[0].plot(expected, pixels[:, 1], label='Frozen A/B prediction')
    axes[0].plot(pixels[:, 0], pixels[:, 1], '.', label='Observed C stripe')
    axes[0].invert_yaxis(); axes[0].set(xlabel='Image x (px)', ylabel='Image row (px)')
    axes[0].legend(fontsize=8)
    axes[1].plot(pixels[:, 1], result['depth_errors_mm'], '.')
    axes[1].axhline(0, color='k', linewidth=.7)
    axes[1].set(xlabel='Image row (px)', ylabel='Predicted minus board Z (mm)')
    fig.suptitle('Held-out pose C: one pose, correlated rows; shared K and reported 18 mm scale', fontsize=10)
    fig.tight_layout(); fig.savefig(root/'held_out_diagnostics.png', dpi=180); plt.close(fig)
    register = Path('EXPERIMENT_RUN_REGISTER.csv')
    with register.open(newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f); fields = reader.fieldnames; existing = {r['run_id'] for r in reader}
    for number, exposure in [(1, 8), (2, 10)]:
        run = f'p3_poseC_20261102_{number:02d}'
        directory = Path('outputs/static_checks')/run
        raw = Path(f'data/raw/p3_poseC_board_20261102_{number:02d}.aedat4')
        sidecar = raw.with_suffix('.json')
        optical = Path('outputs/visibility')/(run+'_optical')/'summary.json'
        manifest = dict(run_id=run, exposure_ms=exposure, firmware='1.7', raw=str(raw),
                        raw_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),
                        camera_sidecar=json.loads(sidecar.read_text()),
                        trace_summary=json.loads((directory/'summary.json').read_text()),
                        optical_summary=json.loads(optical.read_text()),
                        fit_use='held_out_only_never_training',
                        validation=str(root) if number == 2 else None,
                        outcome='too_faint_for_fixed_screen' if number == 1 else result['metrics'],
                        final='off/disarm/release confirmed; camera restored35ms')
        target = directory/'manifest.json'
        if not target.exists(): target.write_text(json.dumps(manifest, indent=2))
        if run not in existing:
            row = dict.fromkeys(fields, '')
            row.update(run_id=run, block='P3', status='rejected_faint_stripe' if number == 1 else 'held_out_bias_observed',
                       condition_id=f'poseC_held1500_exp{exposure}ms', firmware_version='1.7',
                       actual_exposure_ms=exposure, servo_min_us=1500, servo_max_us=1500,
                       feedback_log_path=str(directory/'samples.csv'), raw_aedat4_path=str(raw),
                       status_log_path=str(directory/'operation.json'), processed_output_path=str(directory),
                       rejection_reason='fixed optical screen: insufficient stripe rows' if number == 1 else '',
                       notes='User moved rigid assembly ~5cm farther; not independently measured. FrozenAB model unchanged. C2 Zbias+10.9145mm RMSE11.0247mm against shared-intrinsics posed board; one pose not independent accuracy. Finaloff/disarm/release.')
            with register.open('a', newline='', encoding='utf-8') as f: csv.DictWriter(f, fields).writerow(row)
    review = f'''# Frozen-model held-out pose C

The first held-out geometry check shows a systematic discrepancy: signed depth bias **+10.9145 mm**, RMSE **11.0247 mm**, absolute P95 **13.4677 mm**. This is one board pose with 39 correlated stripe rows, using the same candidate camera intrinsics and user-reported 18 mm target pitch as training. It is not independent absolute depth accuracy.

The A/B plane was frozen before C and its SHA256 remains `{result['model_sha256']}`. No model refit or test alignment was applied. No numerical performance pass threshold was preregistered.

The 8 ms C01 capture was complete but too faint for the existing optical screen and is retained. C02 changed only exposure to 10 ms: 21 qualifying APS frames, 0% screened clipping, full 54 corners, board reprojection RMS 0.2567 px, before/after maximum corner motion 0.0677 px. Both controller traces completed with no feedback-screen warning and off/disarm/release confirmation.

At corresponding rows, observed stripe x minus frozen-model prediction averages **{delta.mean():.3f} px**, range **{delta.min():.3f} to {delta.max():.3f} px**. This is a systematic image-space discrepancy, not merely an inflated depth statistic. Lit feedback differs from A/B means by +0.0563/-0.1256 raw counts; these readings cannot certify identical physical laser planes.

Possible causes include movement of internal mounts during whole-rig repositioning, servo mechanical repeatability, board flatness/pose or camera-model systematics. Existing data do not distinguish them. Do not add C to training and call the resulting training residual held-out validation. The next useful experiment is one independent C repeat without touching the assembly, using the frozen model and unchanged detector, to separate repeatability from between-placement change. No broad camera-intrinsic retake is justified by this result.

Camera exposure restored to 35 ms. Fresh service status confirmed laser off, disarmed, no active operation or recording. `held_out_diagnostics.png` and `image_space_diagnostic.json` preserve the diagnostic. Reproduce validation using `scripts/validate_static_plane.py` with the retained validation_config.json and a new output directory.
'''
    (root/'REVIEW.md').write_text(review)
    handoff = Path('PROJECT_HANDOFF_CURRENT.md')
    marker = 'NEWEST held-out pose C completed'
    prior = handoff.read_text(encoding='utf-8')
    if not prior.startswith(marker):
        handoff.write_text(marker+'; frozen A/B model unchanged SHA6a81b10b...e06f. C8ms too faint retained; C10ms opticalscreen passed (21APS,0clipping,54corners,motionmax0.0677px), but Zbias+10.9145mm/RMSE11.0247mm on39correlatedrows ONEpose. SharedK/user18mmscale NOTindependentabsoluteaccuracy. No refit/testalignment. See outputs/calibration/static_plane1500_C_validation_20261102_01/REVIEW.md. Both C manifests/register retained. Off/disarmed/released, camera35ms, servicesfresh. Next useful one independent same-poseC repeat before any physical move, then diagnose rigidity vs systematicmodelerror; no broadcamera retakes.\n\n'+prior, encoding='utf-8')
    print(json.dumps(diagnostic, indent=2))


if __name__ == '__main__':
    main()
