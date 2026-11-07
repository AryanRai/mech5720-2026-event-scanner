"""Offline APS visibility review; image-change scores are not stripe labels."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

import cv2
import dv_processing as dv
import numpy as np


def main():
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
        raise ValueError('Need at least three APS frames')
    stack = np.stack(frames)
    reference = np.median(stack[:3], axis=0).astype(np.uint8)
    changes = np.maximum(stack.astype(float) - reference, 0)
    # Fixed screen: count brightening >20 levels; does not label laser pixels.
    counts = (changes > 20).reshape(len(frames), -1).sum(axis=1)
    peak = int(np.argmax(counts))
    cv2.imwrite(str(args.output / 'reference.png'), reference)
    cv2.imwrite(str(args.output / 'peak_change.png'), frames[peak])
    cv2.imwrite(str(args.output / 'positive_difference.png'), changes[peak].clip(0, 255).astype(np.uint8))
    with (args.output / 'frame_metrics.csv').open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['index', 'camera_timestamp_us', 'relative_s', 'pixels_brightening_gt20', 'bright_pixels_ge250'])
        for i, timestamp in enumerate(timestamps):
            writer.writerow([i, timestamp, (timestamp-timestamps[0])/1e6, int(counts[i]), int((frames[i] >= 250).sum())])
    selected = sorted(set(np.linspace(0, len(frames)-1, 12).astype(int).tolist() + [peak]))
    width, height = 480, 395
    canvas = np.full((((len(selected)+3)//4)*height, width*4, 3), 25, np.uint8)
    for panel, index in enumerate(selected):
        image = cv2.cvtColor(frames[index], cv2.COLOR_GRAY2BGR)
        image = cv2.resize(image, (480, 360), interpolation=cv2.INTER_NEAREST)
        x, y = (panel % 4)*width, (panel // 4)*height
        canvas[y:y+360, x:x+480] = image
        label = f'#{index} {(timestamps[index]-timestamps[0])/1e6:.3f}s change={counts[index]}'
        cv2.putText(canvas, label, (x+8, y+383), cv2.FONT_HERSHEY_SIMPLEX, .6, (255,255,255), 1)
    cv2.imwrite(str(args.output / 'aps_montage.png'), canvas)
    summary = dict(source=str(args.recording), source_sha256=hashlib.file_digest(args.recording.open('rb'), 'sha256').hexdigest(),
                   frames=len(frames), peak_index=peak, peak_relative_s=(timestamps[peak]-timestamps[0])/1e6,
                   peak_pixels_brightening_gt20=int(counts[peak]),
                   reference='Median of first three APS frames; inspect visually for motion/illumination changes',
                   limitation='Image change is not confirmed laser detection. No controller-camera alignment or geometry calibration.')
    (args.output / 'summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
