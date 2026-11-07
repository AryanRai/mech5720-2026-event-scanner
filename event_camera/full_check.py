"""Bounded acquisition report used by check_camera --full."""
import time
import dv_processing as dv
from event_camera.camera import imu_values


def run_full(capture, duration):
    capture.setColorMode(dv.io.camera.DAVIS.ColorMode.GRAYSCALE)
    available = (capture.isEventStreamAvailable(), capture.isFrameStreamAvailable(), capture.isImuStreamAvailable())
    total = batches = imu_count = 0
    low = high = imu_low = imu_high = None
    frame = sample = None
    start = time.monotonic()
    while time.monotonic() - start < duration:
        if not capture.isRunning():
            print('Camera stopped or disconnected during acquisition.')
            return 1
        if available[0]:
            events = capture.getNextEventBatch()
            if events is not None and len(events):
                total += len(events); batches += 1
                lo, hi = events.getLowestTime(), events.getHighestTime()
                low = lo if low is None else min(low, lo)
                high = hi if high is None else max(high, hi)
        if available[1]:
            f = capture.getNextFrame()
            if f is not None and frame is None:
                frame = f
        if available[2]:
            batch = capture.getNextImuBatch()
            if batch:
                imu_count += len(batch)
                if sample is None: sample = batch[0]
                for item in batch:
                    imu_low = item.timestamp if imu_low is None else min(imu_low, item.timestamp)
                    imu_high = item.timestamp if imu_high is None else max(imu_high, item.timestamp)
        time.sleep(.001)
    elapsed = time.monotonic() - start
    print(f'Observation duration: {elapsed:.3f} s')
    print(f'Events: {total}; non-empty batches: {batches}; mean rate: {total / elapsed:.1f} events/s; timestamp range (us): {low} to {high}')
    print(f'Frame received: {"yes" if frame is not None else "no"} (advertised: {available[1]})')
    if frame is not None:
        print(f'Frame resolution: {capture.getFrameResolution()}; timestamp: {frame.timestamp}; dtype: {frame.image.dtype}; shape: {frame.image.shape}')
    print(f'IMU received: {"yes" if sample is not None else "no"} (advertised: {available[2]}); samples: {imu_count}; timestamp range (us): {imu_low} to {imu_high}')
    if sample is not None:
        a, g = imu_values(sample)
        print(f'First IMU acceleration (m/s²): {a}; angular velocity (rad/s): {g}')
    if not total or frame is None or sample is None:
        print('One or more streams did not deliver data; an advertised stream is not proof of delivery.')
        return 1
    print('Full acquisition: success; clean exit')
    return 0
