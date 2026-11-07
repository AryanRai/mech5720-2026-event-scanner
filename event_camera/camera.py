"""Minimal DAVIS discovery and stream helpers."""
import dv_processing as dv


def open_davis(serial=None):
    devices = dv.io.camera.discover()
    candidates = [d for d in devices if 'DAVIS' in str(d.cameraModel) and (serial is None or d.serialNumber == serial)]
    if not candidates:
        raise RuntimeError('No matching DAVIS detected; check USB connection and serial.')
    if len(candidates) != 1:
        raise RuntimeError('Multiple DAVIS cameras detected; select one with --serial.')
    device = candidates[0]
    camera = dv.io.camera.open(device)
    print(f'Camera: {camera.getCameraName()} | Serial: {device.serialNumber}', flush=True)
    return camera


def require_stream(camera, name):
    if not getattr(camera, 'is' + name + 'StreamAvailable')():
        raise RuntimeError(f'{name} stream unavailable')
    print(f'{name} stream start: available; awaiting data', flush=True)


def imu_values(sample):
    return sample.getAccelerations().reshape(-1), sample.getAngularVelocities().reshape(-1)
