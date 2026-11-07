"""Loopback camera service. Camera reads, writes and controls have ONE owner thread.

No Arduino, laser, shell execution, arbitrary paths or remote network binding.
POSTs require a per-run local token and idempotency ID. HTTP workers only enqueue.
"""
from collections import deque
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import copy
import gc
import json
import math
import queue
import re
import secrets
import threading
import time

import cv2
import numpy as np

from event_camera.focus import FocusMonitor
from event_camera.timestamps import assess_timestamps


def safe_name(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}', value):
        raise ValueError('Name must be 1-80 ASCII letters/digits/underscores/hyphens')
    return value


def number(value, lo, hi):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not lo <= value <= hi:
        raise ValueError(f'Expected a finite number in {lo}..{hi}')
    return value


def clean(value):
    """JSON diagnostics must not contain NaN/Infinity or numpy objects."""
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return clean(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [clean(v) for v in value]
    return value


class ControlState:
    def __init__(self):
        self.lock = threading.Lock()
        self.commands = queue.Queue(maxsize=32)
        self.operations = {}
        self.history = deque(maxlen=300)
        self.info = {'running': False, 'camera_connected': False, 'error': None}
        self.frame_jpeg = self.events_jpeg = None
        self.token = secrets.token_urlsafe(32)

    def submit(self, request):
        if not isinstance(request, dict):
            raise ValueError('Expected a JSON object')
        ident = safe_name(request.get('id'))
        with self.lock:
            if ident in self.operations:
                if self.operations[ident]['request'] != request:
                    raise ValueError('Id already used for different command')
                return copy.deepcopy(self.operations[ident])
            if len(self.operations) >= 2000:
                raise ValueError('Session operation limit reached; restart service')
            operation = {'id': ident, 'state': 'queued', 'request': copy.deepcopy(request)}
            self.commands.put_nowait((ident, copy.deepcopy(request)))
            self.operations[ident] = operation
            return copy.deepcopy(operation)

    def finish(self, ident, result=None, error=None):
        with self.lock:
            self.operations[ident].update(state='failed' if error else 'done', result=clean(result), error=error)

    def status(self):
        with self.lock:
            result = copy.deepcopy(self.info)
        now = time.monotonic()
        for key in ('heartbeat', 'last_frame', 'last_event', 'last_imu'):
            t = result.pop(key, None)
            result[key + '_age_s'] = None if t is None else max(0, now - t)
        result['stale'] = result['last_frame_age_s'] is None or result['last_frame_age_s'] > 2
        return clean(result)


def make_handler(state):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, code, obj, content_type='application/json'):
            body = obj if isinstance(obj, bytes) else json.dumps(clean(obj), allow_nan=False).encode()
            self.send_response(code)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(body)

        def valid_host(self):
            return self.headers.get('Host', '') in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}')

        def do_GET(self):
            if not self.valid_host():
                return self.reply(403, {'error': 'Loopback host required'})
            if self.path == '/':
                page = Path(__file__).with_name('camera_preview.html').read_bytes()
                return self.reply(200, page, 'text/html; charset=utf-8')
            if self.path == '/status':
                return self.reply(200, state.status())
            with state.lock:
                if self.path == '/diagnostics':
                    history = copy.deepcopy(list(state.history))
                else:
                    history = None
                op = copy.deepcopy(state.operations.get(self.path.rsplit('/', 1)[-1])) if self.path.startswith('/operations/') else None
                image = state.frame_jpeg if self.path == '/frame.jpg' else state.events_jpeg if self.path == '/events.jpg' else None
            # Never hold the acquisition lock while writing to a slow HTTP client.
            if history is not None:
                return self.reply(200, {'history': history})
            if self.path.startswith('/operations/'):
                return self.reply(200 if op else 404, op or {'error': 'Unknown operation'})
            if self.path in ('/frame.jpg', '/events.jpg'):
                return self.reply(200 if image else 503, image or b'No image yet', 'image/jpeg' if image else 'text/plain')
            return self.reply(404, {'error': 'Use /status, /diagnostics, /frame.jpg, /events.jpg'})

        def do_POST(self):
            if not self.valid_host() or self.headers.get('Origin') is not None or self.headers.get('X-Camera-Token') != state.token:
                return self.reply(403, {'error': 'Local CLI token required; browser-origin commands rejected'})
            if self.path != '/command':
                return self.reply(404, {'error': 'Unknown endpoint'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 4096:
                    raise ValueError('Command body must be 1..4096 bytes')
                request = json.loads(self.rfile.read(length))
                return self.reply(202, state.submit(request))
            except (ValueError, queue.Full) as exc:
                return self.reply(400, {'error': str(exc) or 'Command queue full'})
    return Handler


class CameraSession:
    def __init__(self, camera, dv, root, state):
        self.camera, self.dv, self.root, self.state = camera, dv, Path(root), state
        self.monitor = FocusMonitor()
        self.pattern = None
        self.gray = None
        self.frame_timestamp = self.exposure_us = None
        self.focus = None
        self.last_metrics = 0
        self.last_frame = self.last_event = self.last_imu = None
        self.counts = dict(events=0, frames=0, imu=0)
        self.rate_at = time.monotonic()
        self.rate_count = 0
        self.event_rate = 0
        self.drain_limits_hit = dict(events=0, frames=0, imu=0)
        self.stream_timestamps = dict(events=None, frames=None, imu=None)
        self.started = time.monotonic()
        self.event_image = np.zeros((180, 240, 3), np.uint8)
        self.last_event_pixels = None
        self.valid_frames = 0
        self.writer = None
        self.record = None
        self.last_record = None
        self.requested_exposure = None
        self.auto_exposure = bool(camera.getAutoExposure())
        self.shutdown = False
        self.shutdown_at = None
        self.root.joinpath('outputs/agent_control').mkdir(parents=True, exist_ok=True)
        self.journal = self.root.joinpath('outputs/agent_control/commands.jsonl').open('a', encoding='utf-8')

    def control(self, request):
        command = request.get('command')
        if command == 'controls':
            if self.writer:
                raise ValueError('Stop recording before changing exposure')
            if set(request) - {'id', 'command', 'auto_exposure', 'exposure_us'}:
                raise ValueError('Unsupported control; no arbitrary camera register writes')
            if 'exposure_us' in request and 'auto_exposure' in request:
                raise ValueError('Set manual exposure OR auto_exposure, not both')
            if 'exposure_us' in request:
                value = int(number(request['exposure_us'], 100, 500000))
                self.camera.setAutoExposure(False)
                self.camera.setExposureDuration(timedelta(microseconds=value))
                self.requested_exposure = value
            elif 'auto_exposure' in request:
                if type(request['auto_exposure']) is not bool:
                    raise ValueError('auto_exposure must be boolean')
                self.camera.setAutoExposure(request['auto_exposure'])
            else:
                raise ValueError('Specify exposure_us or auto_exposure')
            self.auto_exposure = bool(self.camera.getAutoExposure())
            self.monitor.reset()  # brightness change invalidates a relative focus comparison
            return {'auto_exposure': self.auto_exposure, 'requested_exposure_us': self.requested_exposure,
                    'note': 'Requested controls; inspect subsequent frames for actual applied exposure'}
        if command == 'focus':
            pattern = request.get('pattern')
            if pattern is not None:
                if not isinstance(pattern, list) or len(pattern) != 2 or any(type(v) is not int or not 2 <= v <= 30 for v in pattern):
                    raise ValueError('pattern must be [inner_cols, inner_rows], each 2..30, or null')
                pattern = tuple(pattern)
            self.pattern = pattern
            self.monitor = FocusMonitor(pattern)
            return {'pattern': pattern, 'reset': True}
        if command == 'snapshot':
            if self.gray is None or time.monotonic() - self.last_frame > 2:
                raise ValueError('No fresh frame available')
            name = safe_name(request.get('name'))
            folder = self.root / 'outputs/agent_control' / name
            folder.mkdir(exist_ok=False)
            if not cv2.imwrite(str(folder / 'aps.png'), self.gray):
                raise RuntimeError('Failed to write raw APS image')
            cv2.imwrite(str(folder / 'events.png'), self.event_image)
            metadata = clean({'timestamp_us': self.frame_timestamp, 'exposure_us': self.exposure_us,
                              'camera': self.camera.getCameraName(), 'focus': self.focus,
                              'note': request.get('notes', ''), 'events_note': 'Latest event visualization, not synchronized ground truth',
                              'date_time_utc': datetime.now(timezone.utc).isoformat()})
            (folder / 'metadata.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
            return {'folder': str(folder), 'timestamp_us': self.frame_timestamp}
        if command == 'record':
            if self.writer:
                raise ValueError('Recording already active')
            name = safe_name(request.get('name'))
            duration = number(request.get('duration_s'), .1, 300)
            if self.valid_frames < 2:
                raise ValueError('APS timestamps not initialized; wait for two valid frames')
            if self.last_frame is None or time.monotonic() - self.last_frame > 2:
                raise ValueError('Frame stream is stale; recording refused')
            times = [t for t in self.stream_timestamps.values() if t is not None]
            if len(times) < 3 or max(times) - min(times) > 500000:
                raise ValueError('Stream timestamp horizons diverge or missing data; inspect diagnostics first')
            folder = self.root / 'data/raw'
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / (name + '.aedat4')
            if path.exists() or path.with_suffix('.json').exists():
                raise ValueError('Recording exists; choose a new name')
            self.writer = self.dv.io.MonoCameraWriter(str(path), self.camera)
            self.record = {'path': path, 'started': time.monotonic(), 'duration_s': duration,
                           'date_time_utc': datetime.now(timezone.utc).isoformat(), 'notes': request.get('notes', ''),
                           'streams': {k: {'count': 0, 'first_us': None, 'last_us': None, 'backward': 0} for k in self.counts}}
            return {'path': str(path), 'duration_s': duration, 'state': 'recording'}
        if command == 'record_stop':
            if not self.writer:
                raise ValueError('No active recording')
            return self.finish_record('stopped')
        if command == 'shutdown':
            self.shutdown_at = time.monotonic() + .3
            return {'stopping': True}
        raise ValueError('Unsupported command: use controls, focus, snapshot, record, record_stop, shutdown')

    def note_stream(self, kind, count, first, last):
        stat = self.record['streams'][kind]
        if stat['last_us'] is not None and first < stat['last_us']:
            stat['backward'] += 1
        if stat['first_us'] is None:
            stat['first_us'] = first
        stat['last_us'] = last
        stat['count'] += count

    def finish_record(self, status, error=None):
        record = self.record
        self.writer = None
        gc.collect()  # flush/finalize native AEDAT4 writer before reporting finished
        record['elapsed_s'] = time.monotonic() - record.pop('started')
        record['status'] = status
        record['error'] = error
        record['timestamp_assessment'] = assess_timestamps(record['streams'])
        if not error and record['timestamp_assessment']['status'] != 'PASS':
            record['status'] = 'timestamp_audit_failed'
        record['note'] = 'Native timestamps unchanged. Audit is plausibility only, not physical synchronization.'
        record['path'] = str(record['path'])
        Path(record['path']).with_suffix('.json').write_text(json.dumps(clean(record), indent=2), encoding='utf-8')
        self.last_record = clean(record)
        self.record = None
        return self.last_record

    def step(self):
        now = time.monotonic()
        if self.shutdown_at is not None and now >= self.shutdown_at:
            self.shutdown = True
        if not self.camera.isRunning():
            raise RuntimeError('Camera stopped/disconnected; reconnect explicitly, do not trust cached frames')
        # UI message pumps can take >10 ms on Windows. A single read per draw
        # leaves event/IMU packets queued while APS appears current. Drain each
        # stream, bounded for command responsiveness; report hitting the bound.
        for _ in range(128):
            events = self.camera.getNextEventBatch()
            if events is None:
                break
            if not len(events):
                continue
            self.counts['events'] += len(events)
            self.last_event = now
            self.stream_timestamps['events'] = int(events.getHighestTime())
            arr = events.numpy()
            if self.last_event_pixels is None or now - self.last_event_pixels > .08:
                self.event_image.fill(0)
                self.last_event_pixels = now
            positive = arr['polarity'] != 0
            self.event_image[arr['y'][positive], arr['x'][positive], 2] = 255
            self.event_image[arr['y'][~positive], arr['x'][~positive], 0] = 255
            if self.writer:
                self.writer.writeEvents(events)
                self.note_stream('events', len(events), int(events.getLowestTime()), int(events.getHighestTime()))
        else:
            self.drain_limits_hit['events'] += 1
        for _ in range(32):
            frame = self.camera.getNextFrame()
            if frame is None:
                break
            self.gray = frame.image.copy()
            self.last_frame = now
            self.frame_timestamp = int(frame.timestamp)
            self.exposure_us = frame.exposure.total_seconds() * 1e6
            self.counts['frames'] += 1
            offset = int(self.camera.getTimestampOffset().total_seconds() * 1e6)
            initialized = offset > 0 and frame.timestamp >= offset
            self.valid_frames = self.valid_frames + 1 if initialized else 0
            if initialized:
                self.stream_timestamps['frames'] = int(frame.timestamp)
            if self.writer:
                previous = self.record['streams']['frames']['last_us']
                if not initialized or (previous is not None and (frame.timestamp < previous or frame.timestamp - previous > 10000000)):
                    self.finish_record('error', 'Uninitialized/backward/large-jump frame timestamp; raw data preserved')
                else:
                    self.writer.writeFrame(frame)
                    self.note_stream('frames', 1, int(frame.timestamp), int(frame.timestamp))
        else:
            self.drain_limits_hit['frames'] += 1
        for _ in range(128):
            imu = self.camera.getNextImuBatch()
            if imu is None:
                break
            if not imu:
                continue
            self.counts['imu'] += len(imu)
            self.last_imu = now
            self.stream_timestamps['imu'] = int(imu[-1].timestamp)
            if self.writer:
                for sample in imu:
                    self.writer.writeImu(sample)
                    self.note_stream('imu', 1, int(sample.timestamp), int(sample.timestamp))
        else:
            self.drain_limits_hit['imu'] += 1
        now = time.monotonic()
        if self.writer and now - self.record['started'] >= self.record['duration_s']:
            self.finish_record('complete')
        # Start captures only AFTER draining already queued pre-command packets.
        for _ in range(4):
            try:
                ident, request = self.state.commands.get_nowait()
            except queue.Empty:
                break
            try:
                result = self.control(request)
                self.state.finish(ident, result=result)
                outcome = {'result': clean(result)}
            except Exception as exc:
                self.state.finish(ident, error=f'{type(exc).__name__}: {exc}')
                outcome = {'error': f'{type(exc).__name__}: {exc}'}
            self.journal.write(json.dumps({'utc': datetime.now(timezone.utc).isoformat(), 'request': request, **outcome}) + '\n')
            self.journal.flush()
        if now - self.rate_at >= 1:
            self.event_rate = (self.counts['events'] - self.rate_count) / (now - self.rate_at)
            self.rate_at, self.rate_count = now, self.counts['events']
        if now - self.last_metrics >= .25:
            if self.gray is not None and self.last_frame > self.last_metrics:
                focus = self.monitor.process(self.gray)
                self.focus = clean({k: v for k, v in focus.items() if k != 'corners'})
                self.focus['status'] = 'CHECKERBOARD_HEURISTIC_READY' if focus['streak'] >= 5 else 'RELATIVE_ONLY_NOT_CALIBRATED'
                self.focus['mean'] = float(self.gray.mean())
                self.focus['p05'], self.focus['p95'] = [float(v) for v in np.percentile(self.gray, [5, 95])]
                self.focus['interpretation'] = 'Relative focus only; noise/exposure/scene/motion affect scores. Not a physical calibration.'
                _, encoded = cv2.imencode('.jpg', self.gray)
                with self.state.lock:
                    self.state.frame_jpeg = encoded.tobytes()
            visual = self.event_image.copy()
            if self.last_event is None or now - self.last_event > .5:
                visual.fill(0)
            _, encoded = cv2.imencode('.jpg', visual)
            with self.state.lock:
                self.state.events_jpeg = encoded.tobytes()
                self.state.history.append(clean({'host_monotonic': now, 'timestamp_us': self.frame_timestamp,
                                                'exposure_us': self.exposure_us, 'focus': self.focus, 'event_rate': self.event_rate}))
            self.last_metrics = now
        with self.state.lock:
            times = [t for t in self.stream_timestamps.values() if t is not None]
            self.state.info = clean({'running': True, 'camera_connected': True, 'error': None,
                'camera': self.camera.getCameraName(), 'resolution': list(self.camera.getEventResolution()),
                'heartbeat': now, 'last_frame': self.last_frame, 'last_event': self.last_event, 'last_imu': self.last_imu,
                'uptime_s': now - self.started, 'counts': dict(self.counts), 'event_rate_s': self.event_rate,
                'drain_limits_hit': dict(self.drain_limits_hit),
                'latest_stream_timestamps_us': dict(self.stream_timestamps),
                'stream_horizon_spread_us': max(times) - min(times) if len(times) == 3 else None,
                'auto_exposure': self.auto_exposure, 'requested_exposure_us': self.requested_exposure,
                'actual_exposure_us': self.exposure_us, 'frame_timestamp_us': self.frame_timestamp,
                'timestamp_initialized': self.valid_frames >= 2, 'focus': self.focus,
                'recording': str(self.record['path']) if self.record else None, 'last_recording': self.last_record,
                'actuators': 'Not connected: this service never accesses Arduino/laser/servo'})

    def close(self, error=None):
        if self.writer:
            self.finish_record('error' if error else 'interrupted', error)
        self.journal.close()
        with self.state.lock:
            self.state.info.update(running=False, camera_connected=False, error=error)


def preview(session):
    canvas = np.zeros((670, 1100, 3), np.uint8)
    gray = session.gray
    if gray is not None:
        canvas[35:575, :720] = cv2.cvtColor(cv2.resize(gray, (720, 540), interpolation=cv2.INTER_NEAREST), cv2.COLOR_GRAY2BGR)
    events = session.event_image.copy()
    if session.last_event is None or time.monotonic() - session.last_event > .5:
        events.fill(0)
    canvas[35:305, 730:1090] = cv2.resize(events, (360, 270), interpolation=cv2.INTER_NEAREST)
    focus = session.focus or {}
    stale = session.last_frame is None or time.monotonic() - session.last_frame > 2
    lines = ['APS grayscale - adjust physical focus',
             f"Exposure {(session.exposure_us or 0)/1000:.1f} ms | Auto {session.auto_exposure}",
             f"Focus score {focus.get('score', 0):.1f} | best {focus.get('best', 0):.1f} | {100*focus.get('ratio', 0):.0f}% relative",
             f"Clipped dark {focus.get('dark', 0):.1f}% | bright {focus.get('bright', 0):.1f}%",
             'FRAME STALE / NO SIGNAL' if stale else 'LIVE | relative score is NOT proof of correct focus',
             'q: quit | s: save snapshot | r: reset focus baseline | a: toggle auto exposure']
    cv2.putText(canvas, lines[0], (8, 24), cv2.FONT_HERSHEY_SIMPLEX, .6, (255, 255, 255), 1)
    for i, line in enumerate(lines[1:]):
        cv2.putText(canvas, line, (8, 592 + i*17), cv2.FONT_HERSHEY_SIMPLEX, .43, (0, 255, 255), 1)
    labels = ['ON red / OFF blue (recent events)', f'{session.event_rate:.0f} events/s',
              f'Frames {session.counts["frames"]} | IMU {session.counts["imu"]}',
              'Record: ' + ('ACTIVE' if session.writer else 'off'),
              'Pattern: ' + str(session.pattern or 'not configured'),
              f"Board detected: {focus.get('detected', False)}", 'Actuators: NOT CONTROLLED',
              'Laser must remain off for focusing']
    for i, line in enumerate(labels):
        cv2.putText(canvas, line, (737, 330 + i*25), cv2.FONT_HERSHEY_SIMPLEX, .42, (220, 220, 220), 1)
    return canvas


def run(root, port=8931, serial=None, display=True):
    import dv_processing as dv
    from event_camera.camera import open_davis
    root = Path(root)
    state = ControlState()
    server = ThreadingHTTPServer(('127.0.0.1', port), make_handler(state))
    server.daemon_threads = True
    server.timeout = .5
    session = None
    runtime = root / '.runtime'
    runtime.mkdir(exist_ok=True)
    descriptor = runtime / 'camera.json'
    try:
        camera = open_davis(serial)
        camera.setColorMode(dv.io.camera.DAVIS.ColorMode.GRAYSCALE)
        session = CameraSession(camera, dv, root, state)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        descriptor.write_text(json.dumps({'url': f'http://127.0.0.1:{server.server_port}', 'token': state.token}), encoding='utf-8')
        print(f'Camera agent control at http://127.0.0.1:{server.server_port}; local descriptor .runtime/camera.json', flush=True)
        last_draw = 0
        while not session.shutdown:
            session.step()
            if display:
                if time.monotonic() - last_draw > .1:
                    cv2.imshow('DAVIS Agent Preview - focus and diagnostics', preview(session))
                    last_draw = time.monotonic()
                key = cv2.waitKey(1) & 255
                if key in (27, ord('q')):
                    break
                if key in (ord('s'), ord('r'), ord('a')):
                    request = {'id': secrets.token_hex(8)}
                    if key == ord('s'):
                        request.update(command='snapshot', name='manual_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
                    elif key == ord('r'):
                        request.update(command='focus', pattern=list(session.pattern) if session.pattern else None)
                    else:
                        request.update(command='controls', auto_exposure=not session.auto_exposure)
                    state.submit(request)
            time.sleep(.001)
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        if session:
            session.close(f'{type(exc).__name__}: {exc}')
            session = None
        raise
    finally:
        if session:
            session.close()
        if 'thread' in locals():
            server.shutdown()
        server.server_close()
        if display:
            cv2.destroyAllWindows()
        if descriptor.exists():
            try:
                if json.loads(descriptor.read_text(encoding='utf-8')).get('token') == state.token:
                    descriptor.unlink()
            except (OSError, ValueError):
                pass
