"""Versioned exploratory fixed-command plane fit from APS stripes on posed boards."""
import argparse
import hashlib
import json
from pathlib import Path
import cv2
import numpy as np


def intersect_board(pixels, matrix, distortion, rotation, translation):
    rays2 = cv2.undistortPoints(np.asarray(pixels, float).reshape(-1, 1, 2), matrix, distortion).reshape(-1, 2)
    rays = np.column_stack((rays2, np.ones(len(rays2))))
    normal = rotation[:, 2]
    denominator = rays @ normal
    if np.any(np.abs(denominator) < 1e-8):
        raise ValueError('Ray nearly parallel to board')
    scale = float(normal @ translation.ravel()) / denominator
    if np.any(scale <= 0):
        raise ValueError('Board intersection behind camera')
    return rays * scale[:, None]


def fit_plane(groups):
    if len(groups) < 2 or any(len(g) < 3 for g in groups):
        raise ValueError('Need at least two observed board lines')
    points = np.concatenate(groups)
    weights = np.concatenate([np.full(len(g), 1/len(g)/len(groups)) for g in groups])
    centre = np.sum(points * weights[:, None], axis=0)
    _, singular, vt = np.linalg.svd((points-centre)*np.sqrt(weights[:, None]), full_matrices=False)
    if singular[1] < 1e-6:
        raise ValueError('Plane not identifiable from collinear points')
    normal = vt[-1]
    if normal[0] < 0:
        normal = -normal
    return normal, -float(normal @ centre), singular


def corners(image):
    found = []
    for scale in (4, 2):
        resized = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        ok, points = cv2.findChessboardCornersSB(resized, (9, 6), cv2.CALIB_CB_NORMALIZE_IMAGE | cv2.CALIB_CB_EXHAUSTIVE)
        if not ok:
            raise ValueError('Missing full54 corners')
        found.append(((points+.5)/scale-.5).reshape(-1, 2))
    a, b = found
    if np.mean(np.linalg.norm(a-b[::-1], axis=1)) < np.mean(np.linalg.norm(a-b, axis=1)):
        b = b[::-1]
    disagreement = np.linalg.norm(a-b, axis=1)
    if disagreement.max() > 1:
        raise ValueError('Corner cross-scale disagreement >1 native pixel')
    return a, dict(cross_scale_rms_px=float(np.sqrt(np.mean(disagreement**2))), cross_scale_max_px=float(disagreement.max()))


def observation(config, matrix, distortion):
    import dv_processing as dv
    from scripts.analyse_optical_observation import stripe_measurement
    image = cv2.imread(config['board_image'], cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError('Missing board image')
    c, diagnostics = corners(image)
    after, _ = corners(cv2.imread(config['board_after'], cv2.IMREAD_GRAYSCALE))
    if np.mean(np.linalg.norm(c-after[::-1], axis=1)) < np.mean(np.linalg.norm(c-after, axis=1)):
        after = after[::-1]
    motion = np.linalg.norm(c-after, axis=1)
    if motion.max() > .5:
        raise ValueError('Board image changed >0.5px during observation')
    obj = np.zeros((54, 3), float)
    obj[:, :2] = np.mgrid[0:9, 0:6].T.reshape(-1, 2)*18
    ok, rv, tv = cv2.solvePnP(obj, c.astype(float), matrix, distortion)
    if not ok:
        raise ValueError('Board pose failed')
    rotation = cv2.Rodrigues(rv)[0]
    projected = cv2.projectPoints(obj, rv, tv, matrix, distortion)[0].reshape(-1, 2)
    reprojection = float(np.sqrt(np.mean(np.sum((projected-c)**2, axis=1))))
    if reprojection > .5:
        raise ValueError('Board pose reprojection RMS >0.5px')
    reader = dv.io.MonoCameraRecording(config['recording'])
    frames = []
    while True:
        f = reader.getNextFrame()
        if f is None:
            break
        frames.append(f.image.copy())
    reference = np.median(np.stack(frames[:3]), axis=0)
    by_row = {}
    used_frames, clipping = [], []
    for i, frame in enumerate(frames):
        measured = stripe_measurement(frame, reference)
        if measured is None:
            continue
        if measured['clipped_fraction'] > .01:
            raise ValueError('Qualifying stripe frame has >1% screened clipping')
        used_frames.append(i); clipping.append(measured['clipped_fraction'])
        delta = frame.astype(float)-reference
        mask = (delta > 60) & (frame > 100)
        mask[:35] = False; mask[121:] = False
        column = int(np.argmax(mask.sum(axis=0)))
        mask[:, :max(0, column-8)] = False; mask[:, column+9:] = False
        for row in range(35, 121):
            x = np.flatnonzero(mask[row])
            if len(x):
                by_row.setdefault(row, []).append(float(np.average(x, weights=delta[row, x])))
    if len(used_frames) < 5:
        raise ValueError('Need five qualifying lit APS frames')
    # One median coordinate per illuminated row; frames are not independent repeats.
    pixels = np.array([(np.median(values), row) for row, values in sorted(by_row.items()) if len(values) >= len(used_frames)/2])
    xyz = intersect_board(pixels, matrix, distortion, rotation, tv)
    board_xyz = (xyz-tv.ravel()) @ rotation
    inside = (board_xyz[:, 0] >= -18) & (board_xyz[:, 0] <= 162) & (board_xyz[:, 1] >= -18) & (board_xyz[:, 1] <= 108)
    if inside.sum() < 20:
        raise ValueError('Insufficient stripe points within physical10x7-square board extent')
    trace = json.loads(Path(config['trace_summary']).read_text())
    if trace['errors'] or trace['status'] != 'OBSERVATION_TRACE_REQUIRES_OPTICAL_REVIEW':
        raise ValueError('Invalid controller observation trace')
    result = dict(id=config['id'], sources=config, corners=c.tolist(), diagnostics=diagnostics,
                  board_rvec=rv.ravel().tolist(), board_t_mm=tv.ravel().tolist(), board_normal=rotation[:, 2].tolist(),
                  board_reprojection_rms_px=reprojection, board_motion_max_px=float(motion.max()),
                  qualifying_frames=used_frames, clipped_fraction_max=max(clipping), pixels=pixels[inside].tolist(),
                  points_camera_mm=xyz[inside].tolist(), outside_board_points=int((~inside).sum()),
                  lit_feedback=trace['phase_statistics']['lit_hold'], feedback_screen_warning=trace['feedback_screen_warning'],
                  hashes={key:hashlib.sha256(Path(config[key]).read_bytes()).hexdigest() for key in ('board_image','board_after','recording','trace_summary')})
    return result, xyz[inside]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    intr = json.loads(Path(config['intrinsics']).read_text())['models']['primary_five_coefficient']
    matrix, distortion = np.array(intr['camera_matrix']), np.array(intr['distortion_coefficients'])
    results, groups = [], []
    for spec in config['observations']:
        result, points = observation(spec, matrix, distortion)
        results.append(result); groups.append(points)
    normal, offset, singular = fit_plane(groups)
    residuals = [g @ normal + offset for g in groups]
    summary = dict(status='PRELIMINARY_FIT_NOT_INDEPENDENTLY_VALIDATED', command_us=1500,
                   normal_camera=normal.tolist(), offset_mm=offset, units='mm using user18mm pitch',
                   weighted_spread_singular_mm=singular.tolist(), per_pose_fit_rms_mm=[float(np.sqrt(np.mean(r*r))) for r in residuals],
                   observations=results, config=config,
                   limitations='Two training board poses at one command only. Training residuals are not depth accuracy. User18mm pitch/flatness and rigid internal geometry unverified independently. No servo-angle/function or physical timing calibration. Detector/pose screening developed on this session; needs held-out geometry.')
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output/'plane_fit.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps({k:v for k,v in summary.items() if k not in ('observations','config')}, indent=2))


if __name__ == '__main__':
    # Support running both as a script and as a module from the repository root.
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    main()
