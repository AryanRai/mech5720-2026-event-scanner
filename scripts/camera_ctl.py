"""Agent-facing CLI: no camera ownership; talks to the existing live preview.

status | diagnostics | exposure US | auto on/off | focus [COLS ROWS] |
snapshot NAME [--notes TEXT] | record NAME --duration S [--notes TEXT] |
record-stop | operation ID | shutdown
"""
import argparse
import json
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request
import uuid


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--request-id', help='Reuse the SAME ID to inspect/retry an uncertain operation without duplicate execution')
    p.add_argument('--wait', type=float, default=10)
    sub = p.add_subparsers(dest='verb', required=True)
    for name in ('status', 'diagnostics', 'record-stop', 'shutdown'):
        sub.add_parser(name)
    sub.add_parser('operation').add_argument('id')
    sub.add_parser('exposure').add_argument('us', type=int)
    sub.add_parser('auto').add_argument('mode', choices=['on', 'off'])
    sub.add_parser('focus').add_argument('pattern', type=int, nargs='*')
    for name in ('snapshot', 'record'):
        s = sub.add_parser(name)
        s.add_argument('name')
        s.add_argument('--notes', default='')
        if name == 'record':
            s.add_argument('--duration', type=float, default=5)
    a = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        descriptor = json.loads((root / '.runtime/camera.json').read_text(encoding='utf-8'))
        base = descriptor['url']
        if not base.startswith('http://127.0.0.1:'):
            raise ValueError('Only local loopback control is supported')
        def get(path):
            with urllib.request.urlopen(base + path, timeout=3) as response:
                return json.load(response)
        if a.verb in ('status', 'diagnostics', 'operation'):
            path = '/operations/' + a.id if a.verb == 'operation' else '/' + a.verb
            print(json.dumps(get(path), indent=2))
            return 0
        request = {'id': a.request_id or uuid.uuid4().hex, 'command': a.verb}
        if a.verb == 'exposure':
            request.update(command='controls', exposure_us=a.us)
        elif a.verb == 'auto':
            request.update(command='controls', auto_exposure=a.mode == 'on')
        elif a.verb == 'focus':
            if len(a.pattern) not in (0, 2):
                p.error('focus expects no pattern, or two inner-corner counts')
            request['pattern'] = a.pattern or None
        elif a.verb in ('snapshot', 'record'):
            request.update(name=a.name, notes=a.notes)
            if a.verb == 'record':
                request['duration_s'] = a.duration
        elif a.verb == 'record-stop':
            request['command'] = 'record_stop'
        print('Request ID: ' + request['id'], file=sys.stderr, flush=True)
        req = urllib.request.Request(base + '/command', data=json.dumps(request).encode(),
                    headers={'Content-Type': 'application/json', 'X-Camera-Token': descriptor['token']}, method='POST')
        with urllib.request.urlopen(req, timeout=3) as response:
            result = json.load(response)
        deadline = time.monotonic() + a.wait
        while result['state'] == 'queued' and time.monotonic() < deadline:
            time.sleep(.05)
            result = get('/operations/' + request['id'])
        print(json.dumps(result, indent=2))
        if result['state'] == 'queued':
            print('Outcome pending. Inspect operation ID; do not issue a new duplicate command.', file=sys.stderr)
            return 2
        return 0 if result['state'] == 'done' else 1
    except (OSError, ValueError, KeyError) as exc:
        print(f'Camera control error: {exc}. If a POST was sent, inspect its request ID before retrying.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
