"""Discover a camera and wait briefly for one non-empty event batch."""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--timeout', type=float, default=5.0, help='event wait in seconds (default: 5)')
    parser.add_argument('--serial', help='serial number of the camera to open')
    parser.add_argument('--full', action='store_true', help='measure all streams for --timeout seconds')
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error('--timeout must be positive')
    try:
        import dv_processing as dv
    except ImportError as exc:
        print(f'API/import error: {exc}. Install requirements with the project virtual environment.', file=sys.stderr)
        return 2
    print(f'dv-processing: {dv.__version__}')
    try:
        devices = dv.io.camera.discover()
    except Exception as exc:
        print(f'Camera discovery failed ({type(exc).__name__}): {exc}', file=sys.stderr)
        return 2
    print(f'Devices detected: {len(devices)}')
    for device in devices:
        print(f'  Model: {device.cameraModel}; serial: {device.serialNumber}')
    candidates = [d for d in devices if 'DAVIS' in str(d.cameraModel) and (not args.serial or d.serialNumber == args.serial)]
    if not candidates:
        print('No matching DAVIS detected. Check the USB connection, power, driver and optional serial.', file=sys.stderr)
        return 1
    if len(candidates) > 1 and not args.serial:
        print('Multiple DAVIS cameras detected; select one with --serial.', file=sys.stderr)
        return 1
    try:
        capture = dv.io.camera.open(candidates[0])
        print(f'Camera: {capture.getCameraName()}')
        events_available = capture.isEventStreamAvailable()
        print(f'Events available: {events_available}')
        print(f'Event resolution: {capture.getEventResolution() if events_available else "unavailable"}')
        print(f'Frames available: {capture.isFrameStreamAvailable()}')
        print(f'IMU available: {capture.isImuStreamAvailable()}')
        if not events_available:
            print('Event stream unavailable on this camera.', file=sys.stderr)
            return 1
        if args.full:
            from event_camera.full_check import run_full
            return run_full(capture, args.timeout)
        deadline = time.monotonic() + args.timeout
        while time.monotonic() < deadline:
            if not capture.isRunning():
                print('Camera stopped while waiting for events; check connection and device logs.', file=sys.stderr)
                return 1
            events = capture.getNextEventBatch()
            if events is not None and len(events) > 0:
                print(f'Event packet received: yes ({len(events)} events)')
                print(f'Timestamp range (us): {events.getLowestTime()} to {events.getHighestTime()}')
                return 0
            time.sleep(0.001)
        print(f'Event packet received: no after {args.timeout:g} s. Move a hand in front of the camera and retry; also check event configuration.', file=sys.stderr)
        return 1
    except Exception as exc:
        print(f'Camera open/read error ({type(exc).__name__}): {exc}', file=sys.stderr)
        print('The device may be busy, disconnected, inaccessible to the driver, or incompatible with the API. Close other camera applications and retry.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
