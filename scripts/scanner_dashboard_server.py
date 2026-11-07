"""Loopback dashboard + explicit, token-authenticated camera UI bridge.

Does not open serial/USB. DAVIS remains owned by camera_agent. No arbitrary URLs,
paths, registers or commands. Camera token never reaches the browser.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import secrets
import urllib.request
import urllib.error
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from event_camera.rig_control import RigControl

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / 'firmware/feedback_controller/dashboard/scanner_dashboard.html'
ORIGIN = 'http://127.0.0.1:8933'
TOKEN = secrets.token_urlsafe(32)
RIG = None


def camera_request(body):
    allowed = {'controls', 'focus', 'snapshot', 'record', 'record_stop'}
    if not isinstance(body, dict) or body.get('command') not in allowed:
        raise ValueError('Unsupported camera command')
    keys = {'id', 'command', 'exposure_us', 'auto_exposure', 'pattern', 'name', 'duration_s', 'notes'}
    if set(body) - keys or len(json.dumps(body)) > 2048:
        raise ValueError('Invalid camera request')
    descriptor = json.loads((ROOT / '.runtime/camera.json').read_text())
    if descriptor['url'] != 'http://127.0.0.1:8931':
        raise ValueError('Unexpected camera endpoint')
    return urllib.request.Request('http://127.0.0.1:8931/command',
        data=json.dumps(body).encode(), method='POST',
        headers={'Content-Type': 'application/json', 'X-Camera-Token': descriptor['token']})


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def reply(self, code, data, mime='application/json'):
        payload = data if isinstance(data, bytes) else json.dumps(data).encode()
        self.send_response(code)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(payload)

    def host_ok(self):
        return self.headers.get('Host') == '127.0.0.1:8933'

    def do_GET(self):
        if not self.host_ok():
            return self.reply(403, {'error': 'Loopback Host required'})
        path = self.path.split('?')[0]
        if path == '/rig/status':
            return self.reply(200, RIG.status())
        if path.startswith('/rig/operations/'):
            with RIG.lock:
                op = RIG.ops.get(path.rsplit('/', 1)[-1])
                return self.reply(200 if op else 404, op or {'error':'Unknown operation'})
        if path in ('/', '/scanner_dashboard.html'):
            return self.reply(200, PAGE.read_text(encoding='utf-8').replace('__CAMERA_UI_TOKEN__', TOKEN).encode(), 'text/html; charset=utf-8')
        if path.startswith('/camera/'):
            endpoint = path[len('/camera'):]
            if endpoint not in ('/status', '/frame.jpg', '/events.jpg', '/diagnostics') and not (
                    endpoint.startswith('/operations/') and endpoint[12:].replace('_', '').replace('-', '').isalnum()):
                return self.reply(404, {})
            try:
                with urllib.request.urlopen('http://127.0.0.1:8931' + endpoint, timeout=3) as r:
                    return self.reply(r.status, r.read(2_000_000), r.headers.get('Content-Type', 'application/json'))
            except OSError:
                return self.reply(503, {'error': 'Camera unavailable'})
        return self.reply(404, {})

    def do_POST(self):
        ui = self.headers.get('Origin') == ORIGIN and self.headers.get('X-Camera-UI-Token') == TOKEN
        agent = self.headers.get('Origin') is None and RIG and self.headers.get('X-Rig-Token') == RIG.token
        if not self.host_ok() or not (ui or agent):
            return self.reply(403, {'error': 'Dashboard origin/token required'})
        if self.path not in ('/camera/command', '/rig/heartbeat', '/rig/command'):
            return self.reply(404, {})
        try:
            size = int(self.headers.get('Content-Length', '0'))
            limit = 524288 if self.path == '/rig/heartbeat' and ui else 2048
            if not 0 < size <= limit:
                raise ValueError('Invalid request size')
            body = json.loads(self.rfile.read(size))
            if self.path == '/rig/heartbeat':
                if not ui:
                    return self.reply(403, {})
                return self.reply(200, RIG.heartbeat(body))
            if self.path == '/rig/command':
                if not agent:
                    return self.reply(403, {})
                return self.reply(202, RIG.submit(body))
            request = camera_request(body)
            with urllib.request.urlopen(request, timeout=3) as r:
                return self.reply(r.status, r.read(100_000))
        except (ValueError, OSError) as exc:
            return self.reply(503 if isinstance(exc, OSError) else 400,
                              {'error': str(exc), 'note': 'Inspect operation ID before retry; never duplicate a capture.'})


if __name__ == '__main__':
    RIG = RigControl(ROOT)
    ThreadingHTTPServer(('127.0.0.1', 8933), Handler).serve_forever()
