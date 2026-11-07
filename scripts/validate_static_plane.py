"""Check a frozen plane on a new posed board; never refit or align test geometry."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cv2
import numpy as np
from scripts.fit_static_plane import observation


def fixed_plane_residuals(pixels, board_points, matrix, distortion, normal, offset):
    rays2 = cv2.undistortPoints(np.asarray(pixels, float).reshape(-1, 1, 2), matrix, distortion).reshape(-1, 2)
    rays = np.column_stack((rays2, np.ones(len(rays2))))
    denominator = rays @ normal
    if np.any(np.abs(denominator) < 1e-8):
        raise ValueError('Laser plane nearly parallel to camera ray')
    scale = -offset/denominator
    if np.any(scale <= 0):
        raise ValueError('Predicted laser intersection behind camera')
    predicted = rays*scale[:, None]
    depth_error = predicted[:, 2]-board_points[:, 2]
    plane_error = board_points @ normal+offset
    metrics = dict(rows=len(depth_error), signed_depth_bias_mm=float(depth_error.mean()),
                   depth_rmse_mm=float(np.sqrt(np.mean(depth_error**2))),
                   depth_median_error_mm=float(np.median(depth_error)),
                   depth_absolute_p95_mm=float(np.percentile(abs(depth_error), 95)),
                   signed_point_to_plane_bias_mm=float(plane_error.mean()),
                   point_to_plane_rmse_mm=float(np.sqrt(np.mean(plane_error**2))))
    return metrics, predicted, depth_error, plane_error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    frozen = json.loads((args.model.parent/'frozen_model.json').read_text())
    digest = hashlib.sha256(args.model.read_bytes()).hexdigest()
    if digest != frozen['plane_sha256']:
        raise ValueError('Frozen model hash changed')
    model = json.loads(args.model.read_text())
    config = json.loads(args.config.read_text())
    training_paths = {o['sources']['recording'] for o in model['observations']}
    if config['observation']['recording'] in training_paths:
        raise ValueError('Test recording was used in training')
    intr = json.loads(Path(model['config']['intrinsics']).read_text())['models']['primary_five_coefficient']
    matrix, distortion = np.array(intr['camera_matrix']), np.array(intr['distortion_coefficients'])
    measured, points = observation(config['observation'], matrix, distortion)
    metrics, predicted, depth_error, plane_error = fixed_plane_residuals(
        measured['pixels'], points, matrix, distortion, np.array(model['normal_camera']), model['offset_mm'])
    result = dict(status='HELD_OUT_GEOMETRY_CHECK_NOT_INDEPENDENT_ABSOLUTE_ACCURACY',
                  model=str(args.model), model_sha256=digest, model_modified=False, test_alignment_applied=False,
                  metrics=metrics, observation=measured, predicted_points_camera_mm=predicted.tolist(),
                  depth_errors_mm=depth_error.tolist(), point_to_plane_errors_mm=plane_error.tolist(),
                  lit_feedback_delta_from_training_means_raw=[measured['lit_feedback']['mean']-o['lit_feedback']['mean'] for o in model['observations']],
                  limitations='One held-out physical board pose; row points and APS frames are correlated. Posed-board reference shares intrinsics and user18mm scale with training. Not independent metric ground truth, repeated-sweep statistics, general servo calibration or physical synchronization. No predeclared numerical performance pass threshold.')
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output/'validation.json').write_text(json.dumps(result, indent=2))
    print(json.dumps({k:v for k,v in result.items() if k not in ('observation','predicted_points_camera_mm','depth_errors_mm','point_to_plane_errors_mm')}, indent=2))


if __name__ == '__main__':
    main()
