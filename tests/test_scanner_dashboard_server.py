import importlib.util
from pathlib import Path
from unittest.mock import patch
import json
import pytest

spec = importlib.util.spec_from_file_location('dashboard_server', Path(__file__).parents[1] / 'scripts/scanner_dashboard_server.py')
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


@pytest.mark.parametrize('command', ['shutdown', 'arm', 'laser on', 'register', None])
def test_no_unscoped_commands(command):
    with pytest.raises(ValueError):
        server.camera_request({'id': 'test', 'command': command})


def test_private_camera_token_stays_in_backend_request():
    with patch.object(Path, 'read_text', return_value=json.dumps({'url':'http://127.0.0.1:8931', 'token':'private'})):
        r = server.camera_request({'id':'test', 'command':'focus'})
        assert r.full_url == 'http://127.0.0.1:8931/command'
        assert r.get_header('X-camera-token') == 'private'
        assert not r.has_header('Origin')


def test_no_redirected_descriptor_or_arbitrary_fields():
    with patch.object(Path, 'read_text', return_value=json.dumps({'url':'http://example.com', 'token':'private'})):
        with pytest.raises(ValueError):
            server.camera_request({'id':'test', 'command':'focus'})
    with pytest.raises(ValueError):
        server.camera_request({'id':'test', 'command':'focus', 'url':'http://example.com'})
