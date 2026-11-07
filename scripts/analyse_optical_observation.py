"""Exploratory APS stripe motion screen; requires visual review, not depth validation."""
import argparse
import json
from pathlib import Path
import numpy as np


def stripe_measurement(image, reference, first_row=35, last_row=120):
    """Fixed positive-change screen and dominant-column neighbourhood, no clipping removal."""
    delta = image.astype(float) - reference
    mask = (delta > 60) & (image > 100)
    mask[:first_row] = False
    mask[last_row + 1:] = False
    column = int(np.argmax(mask.sum(axis=0)))
    if mask[:, column].sum() < 10:
        return None
    mask[:, :max(0, column-8)] = False
    mask[:, column+9:] = False
    points = []
    for row in range(first_row, last_row+1):
        x = np.flatnonzero(mask[row])
        if len(x):
            # Midpoint of threshold edges; retain clipping as an explicit limitation.
            points.append((row, (float(x[0])+float(x[-1]))/2))
    if len(points) < 30 or points[-1][0]-points[0][0] < 60:
        return None
    points = np.array(points)
    slope, intercept = np.polyfit(points[:, 0], points[:, 1], 1)
    residual = points[:, 1] - (slope*points[:, 0]+intercept)
    return dict(rows=len(points), x_at_row70=float(slope*70+intercept),
                slope=float(slope), line_residual_rms_px=float(np.sqrt(np.mean(residual**2))),
                screened_pixels=int(mask.sum()), clipped_fraction=float((image[mask]>=250).mean()))


def main():
    import dv_processing as dv
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recording', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    reader = dv.io.MonoCameraRecording(str(args.recording))
    frames, timestamps = [], []
    while True:
        frame = reader.getNextFrame()
        if frame is None:
            break
        frames.append(frame.image.copy())
        timestamps.append(int(frame.timestamp))
    if len(frames) < 3:
        raise ValueError('Need at least three dark reference frames')
    reference = np.median(np.stack(frames[:3]), axis=0)
    measurements = []
    for i, frame in enumerate(frames):
        measurement = stripe_measurement(frame, reference)
        if measurement:
            measurements.append(dict(frame=i, timestamp_us=timestamps[i], **measurement))
    x = [m['x_at_row70'] for m in measurements]
    result = dict(source=str(args.recording), measurements=measurements,
                  x70_range_px=[min(x), max(x)] if x else None,
                  x70_population_sd_px=float(np.std(x)) if x else None,
                  method='Delta>60, APS>100; rows35..120; dominant column +/-8; >=30 lit rows spanning>=60 rows; row threshold-edge midpoints fitted x(y). First3 APS median reference.',
                  limitations='Exploratory post-development screen, visually inspect stripe identity/board interception. Clipping and threshold quantisation can hide physical motion. Correlated frames are not independent repeats. No calibrated plane, shaft angle, depth or physical clock alignment.')
    (args.output/'summary.json').write_text(json.dumps(result, indent=2))
    print(json.dumps({k:v for k,v in result.items() if k != 'measurements'}, indent=2))


if __name__ == '__main__':
    main()
