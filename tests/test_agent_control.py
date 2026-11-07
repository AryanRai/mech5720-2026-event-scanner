"""Control-plane tests. Synthetic only; no USB camera or Arduino opened."""
from datetime import timedelta
from http.server import ThreadingHTTPServer
import json
import threading
import time
import urllib.error
import urllib.request
from types import SimpleNamespace

import numpy as np
import pytest

from event_camera.agent_control import CameraSession, ControlState, clean, make_handler, number, safe_name


class FakeCamera:
    auto = True
    exposure = None

    def getAutoExposure(self):
        return self.auto

    def setAutoExposure(self, value):
        self.auto = value

    def setExposureDuration(self, value):
        self.exposure = value

    def getCameraName(self):
        return 'FAKE_ONLY'


@pytest.fixture
def session(tmp_path):
    s = CameraSession(FakeCamera(), None, tmp_path, ControlState())
    yield s
    s.close()


def test_name_validation_and_numbers():
    assert safe_name('test_01-abc') == 'test_01-abc'
    for name in ('../escape', 'x/y', '', 'A' * 81, 'with space', 'C:\\data', None):
        with pytest.raises(ValueError):
            safe_name(name)
    for n in (True, float('nan'), float('inf'), -1, '1000'):
        with pytest.raises(ValueError):
            number(n, 0, 1000)
    assert clean({'x': float('inf'), 'a': np.array([1, 2])}) == {'x': None, 'a': [1, 2]}


def test_idempotency_and_payload_collision():
    state = ControlState()
    request = {'id': 'same', 'command': 'snapshot', 'name': 'test'}
    state.submit(request)
    state.submit(request)
    assert state.commands.qsize() == 1
    state.finish('same', {'saved': True})
    assert state.submit(request)['state'] == 'done'
    with pytest.raises(ValueError):
        state.submit({**request, 'name': 'different'})
    assert state.commands.qsize() == 1


def test_stale_frame_status():
    state = ControlState()
    assert state.status()['stale']
    state.info.update(last_frame=time.monotonic(), heartbeat=time.monotonic())
    assert not state.status()['stale']
    state.info['last_frame'] -= 3
    assert state.status()['stale']


def test_control_exposure_and_guardrails(session):
    result = session.control({'command': 'controls', 'exposure_us': 20000})
    assert result['auto_exposure'] is False
    assert session.camera.exposure == timedelta(microseconds=20000)
    for value in (0, 9999999, True):
        with pytest.raises(ValueError):
            session.control({'command': 'controls', 'exposure_us': value})
    with pytest.raises(ValueError):
        session.control({'command': 'controls', 'register': 123})
    session.writer = object()
    with pytest.raises(ValueError):
        session.control({'command': 'controls', 'auto_exposure': True})
    session.writer = None
    with pytest.raises(ValueError):
        session.control({'command': 'laser on'})


def test_focus_config_and_snapshot(session):
    session.control({'command': 'focus', 'pattern': [9, 6]})
    assert session.pattern == (9, 6)
    with pytest.raises(ValueError):
        session.control({'command': 'focus', 'pattern': [True, 6]})
    with pytest.raises(ValueError):
        session.control({'command': 'snapshot', 'name': 'empty'})
    session.gray = np.full((180, 240), 80, np.uint8)
    session.last_frame = time.monotonic()
    session.frame_timestamp = 12345
    result = session.control({'command': 'snapshot', 'name': 'fresh', 'notes': 'synthetic'})
    metadata = json.loads((session.root / 'outputs/agent_control/fresh/metadata.json').read_text())
    assert metadata['timestamp_us'] == 12345
    assert result['timestamp_us'] == 12345
    with pytest.raises(FileExistsError):
        session.control({'command': 'snapshot', 'name': 'fresh'})


def test_recording_requires_initialized_fresh_stream(session):
    with pytest.raises(ValueError, match='initialized'):
        session.control({'command': 'record', 'name': 'test', 'duration_s': 5})
    session.valid_frames = 2
    with pytest.raises(ValueError, match='stale'):
        session.control({'command': 'record', 'name': 'test', 'duration_s': 5})


def test_owner_drains_multiple_queued_batches_per_step(session):
    class QueuedCamera(FakeCamera):
        def __init__(self):
            self.batches = [[SimpleNamespace(timestamp=1000 + j)] * 10 for j in range(5)]

        def isRunning(self):
            return True

        def getNextEventBatch(self):
            return None

        def getNextFrame(self):
            return None

        def getNextImuBatch(self):
            return self.batches.pop(0) if self.batches else None

        def getEventResolution(self):
            return (240, 180)

    session.camera = QueuedCamera()
    session.step()
    assert session.counts['imu'] == 50
    assert session.drain_limits_hit['imu'] == 0
    assert session.state.status()['camera_connected']


def test_loopback_http_token_origin_and_get():
    state = ControlState()
    server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        with urllib.request.urlopen(base + '/', timeout=2) as response:
            assert response.headers['Content-Type'].startswith('text/html')
            assert b'DAVIS Live Camera' in response.read()
        with urllib.request.urlopen(base + '/status', timeout=2) as response:
            assert json.load(response)['stale']
        request = {'id': 'test', 'command': 'snapshot', 'name': 'synthetic'}
        body = json.dumps(request).encode()
        for headers in ({}, {'X-Camera-Token': state.token, 'Origin': 'http://evil.example'}):
            with pytest.raises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(urllib.request.Request(base + '/command', data=body, headers=headers), timeout=2)
            assert error.value.code == 403
        headers = {'X-Camera-Token': state.token}
        for _ in range(2):
            with urllib.request.urlopen(urllib.request.Request(base + '/command', data=body, headers=headers), timeout=2) as response:
                assert json.load(response)['id'] == 'test'
        assert state.commands.qsize() == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
