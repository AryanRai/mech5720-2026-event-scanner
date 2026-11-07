import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('feedback_test', Path(__file__).parents[1] / 'scripts/feedback_camera_test.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_no_laser_commands():
    for target in (1450, 1500, 1550):
        assert mod.plan(target) == ['move', str(target)]


@pytest.mark.parametrize('bad', [900, 1449, 1551, 2100, True, 1500.0, '1500'])
def test_rejects_outside_initial_window(bad):
    with pytest.raises(ValueError):
        mod.plan(bad)
