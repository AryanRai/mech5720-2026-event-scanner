"""Bounded laser-OFF feedback diagnostic paired with the existing DAVIS owner.

Default is a dry-run. No serial port or camera is opened by importing this file.
The firmware centres on reset. Disconnect the laser and clear the mechanism first.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parents[1]


def plan(target):
    if type(target) is not int or not 1450 <= target <= 1550:
        raise ValueError('Initial test restricted to 1450–1550 us')
    return ['move', str(target)]  # no backlash preroll, no arm, no laser command


def camera_status():
    with urllib.request.urlopen('http://127.0.0.1:8931/status', timeout=3) as r:
        return json.load(r)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--target-us', type=int, default=1500)
    p.add_argument('--port', default='COM13')
    p.add_argument('--execute-laser-disconnected', action='store_true')
    a = p.parse_args()
    command = plan(a.target_us)
    print('Plan: 12-second DAVIS capture + servo ' + ' '.join(command), flush=True)
    if not a.execute_laser_disconnected:
        print('DRY RUN: no hardware accessed')
        return 0
    # Require the old dashboard to relinquish serial first; never steal its port.
    try:
        with urllib.request.urlopen('http://127.0.0.1:8932/status', timeout=2) as r:
            bench = json.load(r)
        if bench.get('connected') or bench.get('busy'):
            raise RuntimeError('Disconnect/stop the existing bench controller first')
    except urllib.error.URLError:
        pass
    status = camera_status()
    if not status.get('camera_connected') or status.get('stale') or not status.get('timestamp_initialized'):
        raise RuntimeError('DAVIS is disconnected, stale, or timestamps uninitialized')
    if status.get('recording'):
        raise RuntimeError('An existing camera recording must finish first')
    ident = 'feedback_off_' + time.strftime('%Y%m%d_%H%M%S')
    out = ROOT / 'outputs' / 'feedback_tests' / ident
    out.mkdir(parents=True, exist_ok=False)
    (out / 'plan.json').write_text(json.dumps(dict(command=command, port=a.port,
        laser='physically disconnected; never armed', synchronization='NOT calibrated'), indent=2))
    ctl = [sys.executable, str(ROOT / 'scripts/camera_ctl.py')]
    # A nonzero/pending outcome is never automatically retried.
    start = subprocess.run(ctl + ['--request-id', ident, 'record', ident,
        '--duration', '12', '--notes', 'Laser disconnected; feedback servo diagnostic'],
        capture_output=True, text=True)
    (out / 'camera_start.log').write_text(start.stdout + start.stderr)
    if start.returncode:
        raise RuntimeError('Camera start uncertain/failed; inspect operation ' + ident)
    try:
        logger = ROOT / 'firmware/feedback_controller/host/scan_logger.py'
        result = subprocess.run([sys.executable, str(logger), '--port', a.port,
            '--timeout', '8', '--out', str(out), *command], timeout=20,
            capture_output=True, text=True)
        (out / 'servo.log').write_text(result.stdout + result.stderr)
    finally:
        # Recording is also bounded independently if this process fails.
        stop = subprocess.run(ctl + ['--request-id', ident + '_stop', 'record-stop'],
                              capture_output=True, text=True)
        (out / 'camera_stop.log').write_text(stop.stdout + stop.stderr)
    print('Saved ' + str(out))
    print('Review logs/AEDAT4: host overlap is not measured clock synchronization.')
    return result.returncode


if __name__ == '__main__':
    sys.exit(main())
