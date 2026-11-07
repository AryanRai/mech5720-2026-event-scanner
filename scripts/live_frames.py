"""View DAVIS APS frames, optionally with session-relative focus diagnostics."""
import argparse
from datetime import datetime
from pathlib import Path
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cv2
import dv_processing as dv
import numpy as np
from event_camera.camera import open_davis, require_stream
from event_camera.focus import FocusMonitor


def focus_preview(gray, result, pattern, timestamp, fps):
    image = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    if result['detected']:
        cv2.drawChessboardCorners(image, pattern, result['corners'], True)
    image = cv2.resize(image, (480, 360), interpolation=cv2.INTER_NEAREST)
    panel = np.zeros((max(360, 420), 480, 3), dtype=np.uint8)
    h = panel.shape[0]
    canvas = np.zeros((h, 960, 3), dtype=np.uint8)
    canvas[:360, :480] = image
    count = len(result['corners']) if result['detected'] else 0
    expected = pattern[0]*pattern[1] if pattern else 0
    lines = [f'APS t={timestamp}  FPS={fps:.1f}',
             f'Sharpness: {result["score"]:.1f}   Best: {result["best"]:.1f}',
             f'Relative: {result["ratio"]*100:.1f}%   Median: {result["median"]:.1f}',
             f'Stability: {"STABLE" if result["stable"] else "NOT STABLE"}  variation: {result["variation"]*100:.1f}%',
             f'History: {result["samples"]}/25 frames',
             f'Checkerboard: {"YES" if result["detected"] else "NO" if pattern else "NOT CONFIGURED"}',
             f'Corners: {count} / {expected}   detection rate: {result["rate"]*100:.0f}%',
             f'Board span: {result["span"][0]:.0f}% width, {result["span"][1]:.0f}% height',
             f'Clipped dark: {result["dark"]:.1f}%   bright: {result["bright"]:.1f}%',
             'STATUS: ' + result['status']]
    if result['status'] == 'GOOD ENOUGH FOR CALIBRATION': lines.append('HOLD FOCUS HERE')
    if result['past_best']: lines.append('PAST BEST - try rotating back')
    if result['dark'] >= 20: lines.append('WARNING: IMAGE TOO DARK')
    if result['bright'] >= 20: lines.append('WARNING: IMAGE SATURATED')
    if result['small']: lines.append('CHECKERBOARD TOO SMALL')
    if result['partial']: lines.append('CHECKERBOARD NEAR FRAME EDGE')
    if pattern and not result['detected']: lines.append('Board missing or partially out of frame')
    lines.append('q/Esc quit | s save raw | r reset')
    for i, line in enumerate(lines):
        cv2.putText(canvas, line, (490, 22 + i*24), cv2.FONT_HERSHEY_SIMPLEX, .44, (0,255,0) if 'GOOD ENOUGH' in line or 'HOLD FOCUS' in line else (255,255,255), 1, cv2.LINE_AA)
    return canvas


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--serial'); p.add_argument('--duration',type=float); p.add_argument('--no-display',action='store_true')
    p.add_argument('--focus-monitor',action='store_true'); p.add_argument('--checkerboard-cols',type=int); p.add_argument('--checkerboard-rows',type=int)
    a=p.parse_args()
    if a.duration is not None and a.duration <= 0: p.error('duration must be positive')
    if (a.checkerboard_cols is None) != (a.checkerboard_rows is None): p.error('specify both checkerboard dimensions')
    if a.checkerboard_cols is not None and (a.checkerboard_cols < 2 or a.checkerboard_rows < 2): p.error('checkerboard dimensions must be at least 2')
    if a.checkerboard_cols is not None and not a.focus_monitor: p.error('checkerboard dimensions require --focus-monitor')
    pattern = (a.checkerboard_cols, a.checkerboard_rows) if a.checkerboard_cols else None
    monitor = FocusMonitor(pattern) if a.focus_monitor else None
    start=time.monotonic(); count=0; frame=None; result=None
    try:
        c=open_davis(a.serial); require_stream(c,'Frame'); c.setColorMode(dv.io.camera.DAVIS.ColorMode.GRAYSCALE)
        print(f'Frame resolution: {c.getFrameResolution()}')
        while a.duration is None or time.monotonic()-start < a.duration:
            if not c.isRunning(): raise RuntimeError('Camera stopped or disconnected')
            f=c.getNextFrame()
            if f is not None:
                if f.image.ndim != 2: raise RuntimeError(f'Expected grayscale image, got shape {f.image.shape}')
                frame=f; count+=1
                if monitor: result=monitor.process(f.image)
                if not a.no_display:
                    if monitor: preview=focus_preview(f.image,result,pattern,f.timestamp,count/(time.monotonic()-start))
                    else:
                        preview=cv2.cvtColor(f.image,cv2.COLOR_GRAY2BGR)
                        cv2.putText(preview,f't={f.timestamp} FPS={count/(time.monotonic()-start):.1f}',(3,15),cv2.FONT_HERSHEY_SIMPLEX,.35,(0,0,255),1)
                        preview=cv2.resize(preview,None,fx=2,fy=2,interpolation=cv2.INTER_NEAREST)
                    cv2.imshow('DAVIS grayscale APS',preview)
            if not a.no_display:
                key=cv2.waitKey(1)&255
                if key in (27,ord('q')): break
                if key == ord('r') and monitor: monitor.reset(); print('Focus history and best reset')
                if key == ord('s') and frame is not None:
                    out=Path(__file__).resolve().parents[1]/'outputs'/('focus' if monitor else 'frames'); out.mkdir(parents=True,exist_ok=True)
                    path=out/f'{"raw" if monitor else "frame"}_{datetime.now():%Y%m%d_%H%M%S_%f}_{frame.timestamp}.png'
                    if not cv2.imwrite(str(path),frame.image): raise RuntimeError(f'Failed to save {path}')
                    print(f'Saved raw grayscale: {path}')
            time.sleep(.001)
    except KeyboardInterrupt:
        print('\nInterrupted by user')
    except Exception as e:
        print(f'Frame viewer error ({type(e).__name__}): {e}',file=sys.stderr); return 2
    finally:
        if not a.no_display: cv2.destroyAllWindows()
    elapsed=time.monotonic()-start
    print(f'Frames received: {count}; duration: {elapsed:.2f} s; mean FPS: {count/elapsed:.1f}; clean exit')
    if result: print(f'Last focus: {result["score"]:.1f}; best: {result["best"]:.1f}; status: {result["status"]}; checkerboard detected: {result["detected"]}')
    return 0 if count else 1

if __name__=='__main__': sys.exit(main())
