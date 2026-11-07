"""Display timestamp-windowed ON/OFF events; --duration allows bounded checks."""
import argparse
from collections import deque
from pathlib import Path
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cv2
import numpy as np
from event_camera.camera import open_davis, require_stream


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--serial'); p.add_argument('--window-us', type=int, default=10000)
    p.add_argument('--duration', type=float, default=None); p.add_argument('--no-display', action='store_true')
    a = p.parse_args()
    if a.window_us <= 0 or (a.duration is not None and a.duration <= 0): p.error('window and duration must be positive')
    try:
        c = open_davis(a.serial); require_stream(c, 'Event')
        width, height = c.getEventResolution(); print(f'Resolution: {width} x {height}')
        chunks = deque(); latest = None; latest_wall = None; total = 0; start = time.monotonic(); next_draw = start
        while a.duration is None or time.monotonic() - start < a.duration:
            if not c.isRunning(): raise RuntimeError('Camera stopped or disconnected')
            batch = c.getNextEventBatch()
            if batch is not None and len(batch):
                arr = batch.numpy().copy(); chunks.append(arr); total += len(arr)
                latest = int(arr['timestamp'][-1]); latest_wall = time.monotonic()
            now = time.monotonic()
            if now >= next_draw:
                if latest is not None:
                    cutoff = latest + int((now - latest_wall) * 1e6) - a.window_us
                    while chunks and int(chunks[0]['timestamp'][-1]) < cutoff: chunks.popleft()
                    if chunks:
                        chunks[0] = chunks[0][chunks[0]['timestamp'] >= cutoff]
                    data = np.concatenate(list(chunks)) if chunks else None
                else: data = None
                image = np.zeros((height, width, 3), np.uint8)
                on = off = 0
                if data is not None and len(data):
                    pos = data['polarity'] != 0; on = int(pos.sum()); off = len(data) - on
                    image[data['y'][~pos], data['x'][~pos], 0] = 255
                    image[data['y'][pos], data['x'][pos], 2] = 255
                if not a.no_display:
                    canvas = cv2.resize(image, (width * 3, height * 3), interpolation=cv2.INTER_NEAREST)
                    label = f'{c.getCameraName()} | {a.window_us} us | {((on+off)*1e6/a.window_us):.0f} events/s | ON {on} OFF {off}'
                    cv2.putText(canvas, label, (5, 20), cv2.FONT_HERSHEY_SIMPLEX, .45, (255,255,255), 1)
                    cv2.imshow('DAVIS events (ON red, OFF blue)', canvas)
                next_draw = now + .02
            if not a.no_display and (cv2.waitKey(1) & 255) in (27, ord('q')): break
            time.sleep(.001)
        elapsed = time.monotonic()-start
        print(f'Events received: {total}; duration: {elapsed:.2f} s; mean rate: {total/elapsed:.1f} events/s; clean exit')
        return 0 if total else 1
    except Exception as e:
        print(f'Event viewer error ({type(e).__name__}): {e}', file=sys.stderr); return 2
    finally:
        if not a.no_display: cv2.destroyAllWindows()

if __name__ == '__main__': sys.exit(main())
