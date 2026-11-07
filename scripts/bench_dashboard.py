"""Loopback-only manual bench controls. No serial access until user clicks Connect.

Host-timed pulses are NOT a hardware safety interlock. Existing firmware's
60-second manual-laser timeout is the fallback if this process/USB fails.
"""
import json
import math
import queue
import secrets
import threading
import time
import urllib.request
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import serial

ORIGIN = 'http://127.0.0.1:8932'
TOKEN = secrets.token_urlsafe(32)
MIN_US, MAX_US = 1450, 1550
MAX_LASER_SECONDS = 5.0
# User reports non-repeatable direction: do not illuminate an unverified path.
LASER_POSITIONING_HOLD = True
jobs = queue.Queue(maxsize=1)
halt = threading.Event()
lock = threading.Lock()
state = dict(connected=False, busy=False, command_us=None, angle_deg=None,
             laser='not connected', laser_on=False, action=None,
             laser_enabled=not LASER_POSITIONING_HOLD,
             error=None, log=[], operation=None)
history = deque(maxlen=60)
seen = {}
port = None


def update(**values):
    with lock:
        state.update(values)


def log(message):
    with lock:
        history.append(message)
        state['log'] = list(history)


def send(command):
    if port is None:
        raise RuntimeError('Arduino not connected')
    log('> ' + command)
    port.write((command + '\n').encode())
    port.flush()


def receive(seconds, interruptible=True):
    lines = []
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if interruptible and halt.is_set():
            raise RuntimeError('Stopped by user')
        line = port.readline().decode(errors='replace').strip()
        if line:
            lines.append(line)
            log(line)
    return lines


def stop():
    if port is None:
        return
    send('stop')
    receive(.15, False)
    send('status')
    lines = receive(.2, False)
    if not any('armed=0' in x and 'laser=0' in x for x in lines):
        update(laser='UNKNOWN — cut physical power', error='Stop not confirmed')
        raise RuntimeError('Stop not confirmed — cut physical power')
    update(laser='OFF — controller confirmed', laser_on=False)


def angle_to_us(value):
    # Nominal relative angle, NOT calibrated horn/beam angle. 0deg = 1500us.
    if type(value) not in (int, float) or not math.isfinite(value) or not -4.5 <= value <= 4.5:
        raise ValueError('Relative angle must be between -4.5 and +4.5 degrees')
    return round(1500 + value * 1000 / 90)


def validate(body):
    action = body.get('action')
    if action not in ('connect', 'move', 'laser_on', 'stop'):
        raise ValueError('Unsupported action')
    if action != 'stop' and body.get('contained') is not True:
        raise ValueError('Confirm containment and mechanical clearance first')
    if action == 'laser_on' and LASER_POSITIONING_HOLD:
        raise ValueError('Laser disabled: resolve non-repeatable servo positioning first')
    if action == 'move':
        angle_to_us(body.get('angle'))
    return action


def worker():
    global port
    while True:
        body = jobs.get()
        update(busy=True, error=None, operation=body['id'], action=body['action'])
        try:
            action = body['action']
            if action == 'connect':
                if port is not None:
                    raise RuntimeError('Already connected; no reset performed')
                # Existing firmware may centre servo at 1500 on USB serial reset.
                port = serial.Serial('COM13', 115200, timeout=.05, write_timeout=.3)
                banner = receive(3)
                if not any('scanner_controller v1.2' in x for x in banner):
                    raise RuntimeError('Unexpected firmware; controls disabled')
                stop()
                update(connected=True, command_us=None, angle_deg=None)
            elif action == 'stop':
                stop()
            else:
                if not state['connected'] or port is None:
                    raise RuntimeError('Connect to the verified controller first')
                stop()
                if action == 'move':
                    target = angle_to_us(body['angle'])
                    # Fixed goto rather than approach: park starts from last command.
                    # Firmware goto approaches from 60us below target, min 1390us.
                    send('goto ' + str(target))
                    lines = receive(2.5)
                    if not any(x.startswith('OK goto ' + str(target)) for x in lines) or any(x.startswith('ERR') for x in lines):
                        raise RuntimeError('Move not confirmed; no retry')
                    update(command_us=target, angle_deg=round((target - 1500) * 90 / 1000, 2))
                elif action == 'laser_on':
                    # Never illuminate while moving. First hold the last explicit position.
                    target = state['command_us']
                    if target is None:
                        raise RuntimeError('Select and move to an angle before turning laser on')
                    send('goto ' + str(target))
                    lines = receive(2.5)
                    if not any(x.startswith('OK goto ' + str(target)) for x in lines) or any(x.startswith('ERR') for x in lines):
                        raise RuntimeError('Position not confirmed')
                    send('arm')
                    if 'OK armed' not in receive(.2):
                        raise RuntimeError('Arming refused — check real enclosure interlock')
                    send('laser on')
                    started = time.monotonic()
                    lines = receive(.15)
                    if 'OK laser on' not in lines:
                        raise RuntimeError('Laser-on not confirmed; no retry')
                    update(laser='ON — 5 second maximum; toggle OFF to stop sooner', laser_on=True)
                    receive(max(0, MAX_LASER_SECONDS - (time.monotonic() - started)))
        except Exception as error:
            update(error=str(error))
            log('ERROR: ' + str(error))
        finally:
            try:
                stop()
            except Exception as error:
                update(error=str(error), connected=False)
            with lock:
                seen[body['id']]['done'] = True
            halt.clear()
            update(busy=False, action=None)
            jobs.task_done()


class Handler(BaseHTTPRequestHandler):
    def response(self, code, data, mime='application/json'):
        payload = data.encode() if isinstance(data, str) else json.dumps(data).encode()
        self.send_response(code)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(payload)

    def host_ok(self):
        return self.headers.get('Host') == '127.0.0.1:8932'

    def do_GET(self):
        if not self.host_ok():
            return self.response(403, {'error': 'Invalid Host'})
        if self.path == '/':
            html = Path(__file__).with_name('bench_dashboard.html').read_text(encoding='utf-8')
            return self.response(200, html.replace('__TOKEN__', TOKEN), 'text/html; charset=utf-8')
        if self.path == '/status':
            with lock:
                snapshot = dict(state)
            return self.response(200, snapshot)
        if self.path.split('?')[0] == '/camera.jpg':
            try:
                with urllib.request.urlopen('http://127.0.0.1:8931/frame.jpg', timeout=2) as upstream:
                    payload = upstream.read(2000000)
                self.send_response(200)
                self.send_header('Content-Type', 'image/jpeg')
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Content-Length', str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            except Exception:
                return self.response(503, {'error': 'Camera unavailable'})
        self.response(404, {})

    def do_POST(self):
        if not self.host_ok() or self.headers.get('Origin') != ORIGIN or self.headers.get('X-Bench-Token') != TOKEN:
            return self.response(403, {'error': 'Local dashboard origin/token required'})
        if self.path != '/command':
            return self.response(404, {})
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 2048:
                raise ValueError('Invalid request size')
            body = json.loads(self.rfile.read(size))
            action = validate(body)
            ident = body.get('id')
            if not isinstance(ident, str) or not 1 <= len(ident) <= 80:
                raise ValueError('Unique operation ID required')
            with lock:
                if ident in seen:
                    if seen[ident]['body'] != body:
                        raise ValueError('ID reused with different command')
                    return self.response(200, seen[ident])
                if len(seen) >= 1000:
                    raise ValueError('Session operation limit reached')
                if action == 'stop':
                    halt.set()  # interrupts an active receive before next serial action
                if state['busy'] or not jobs.empty():
                    if action == 'stop':
                        return self.response(202, {'stopping': True})
                    raise ValueError('Busy; wait. Commands are not queued behind moves.')
                halt.clear()
                seen[ident] = {'body': body, 'done': False}
                state['busy'] = True
                state['action'] = action
                jobs.put_nowait(body)
            self.response(202, {'id': ident, 'accepted': True})
        except (ValueError, TypeError, queue.Full) as error:
            self.response(400, {'error': str(error)})

    def log_message(self, *_):
        pass


if __name__ == '__main__':
    threading.Thread(target=worker, daemon=True).start()
    server = ThreadingHTTPServer(('127.0.0.1', 8932), Handler)
    try:
        server.serve_forever()
    finally:
        halt.set()
        if port is not None:
            try:
                port.write(b'stop\n')
            except Exception:
                pass
            port.close()
