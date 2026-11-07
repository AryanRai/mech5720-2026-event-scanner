"""Print DAVIS IMU values in m/s² and rad/s."""
import argparse
from pathlib import Path
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from event_camera.camera import open_davis, require_stream, imu_values


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--serial'); p.add_argument('--duration',type=float); a=p.parse_args()
    if a.duration is not None and a.duration <= 0: p.error('duration must be positive')
    try:
        c=open_davis(a.serial); require_stream(c,'Imu'); start=time.monotonic(); count=0; next_print=start+.25
        while a.duration is None or time.monotonic()-start < a.duration:
            if not c.isRunning(): raise RuntimeError('Camera stopped or disconnected')
            batch=c.getNextImuBatch()
            if batch:
                count+=len(batch); now=time.monotonic()
                if now >= next_print:
                    s=batch[-1]; acc,gyro=imu_values(s)
                    print(f't={s.timestamp} us | a(m/s²)={acc} | g(rad/s)={gyro} | rate={count/(now-start):.1f} samples/s',flush=True)
                    next_print=now+.25
            time.sleep(.001)
        elapsed=time.monotonic()-start
        print(f'Samples received: {count}; duration: {elapsed:.2f} s; mean sample rate: {count/elapsed:.1f} samples/s; clean exit')
        return 0 if count else 1
    except KeyboardInterrupt:
        elapsed=time.monotonic()-start
        print(f'\nSamples received: {count}; duration: {elapsed:.2f} s; mean sample rate: {count/elapsed:.1f} samples/s; clean exit'); return 0
    except Exception as e:
        print(f'IMU viewer error ({type(e).__name__}): {e}',file=sys.stderr); return 2

if __name__=='__main__': sys.exit(main())

