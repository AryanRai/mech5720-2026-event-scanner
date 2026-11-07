"""Run with Python containing pyserial; no real device is opened."""
import importlib.util
from pathlib import Path
import unittest
import threading
from unittest.mock import patch, Mock

spec = importlib.util.spec_from_file_location('bench_dashboard', Path(__file__).parents[1] / 'scripts/bench_dashboard.py')
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)


class BenchTests(unittest.TestCase):
    def test_import_does_not_open_serial(self):
        self.assertIsNone(bench.port)

    def test_stop_does_not_require_checkbox(self):
        self.assertEqual(bench.validate({'action': 'stop'}), 'stop')

    def test_containment_required(self):
        for action in ('connect', 'move', 'laser_on'):
            with self.assertRaises(ValueError):
                bench.validate({'action': action, 'angle': 0})

    def test_narrow_angle_range(self):
        for value in (-4.51, 4.51, '0', True, None, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                bench.validate({'action': 'move', 'contained': True, 'angle': value})
        for angle, width in ((-4.5, 1450), (0, 1500), (4.5, 1550)):
            self.assertEqual(bench.validate({'action': 'move', 'contained': True, 'angle': angle}), 'move')
            self.assertEqual(bench.angle_to_us(angle), width)
        for tenth in range(-45, 46):
            self.assertTrue(1450 <= bench.angle_to_us(tenth / 10) <= 1550)

    def test_old_raw_move_and_pulse_rejected(self):
        for body in ({'action': 'pulse'}, {'action': 'move', 'us': 1500}):
            with self.assertRaises(ValueError):
                bench.validate(dict(body, contained=True))

    def test_laser_timeout_is_bounded(self):
        self.assertEqual(bench.MAX_LASER_SECONDS, 5)

    def test_unreliable_positioning_blocks_laser(self):
        self.assertTrue(bench.LASER_POSITIONING_HOLD)
        with self.assertRaisesRegex(ValueError, 'non-repeatable'):
            bench.validate({'action': 'laser_on', 'contained': True})

    def test_toggle_operation_stops_after_host_hold(self):
        body = {'id': 'test-toggle', 'action': 'laser_on', 'contained': True}
        fake_jobs = Mock()
        fake_jobs.get.side_effect = [body, StopIteration]
        fake_state = dict(connected=True, command_us=1500)
        off = ['OK status armed=0 laser=0']
        replies = [[], off, ['OK goto 1500'], ['OK armed'], ['OK laser on'], [], [], off]
        with patch.object(bench, 'jobs', fake_jobs), patch.object(bench, 'state', fake_state), patch.object(bench, 'seen', {'test-toggle': {'done': False}}), patch.object(bench, 'port', object()), patch.object(bench, 'halt', threading.Event()), patch.object(bench, 'send') as send, patch.object(bench, 'receive', side_effect=replies) as receive:
            with self.assertRaises(StopIteration):
                bench.worker()
            self.assertEqual([x.args[0] for x in send.call_args_list], ['stop', 'status', 'goto 1500', 'arm', 'laser on', 'stop', 'status'])
            self.assertTrue(4 <= receive.call_args_list[5].args[0] <= 5)
            self.assertFalse(fake_state['laser_on'])
            self.assertFalse(fake_state['busy'])

    def test_stop_interrupts_serial_wait(self):
        interrupted = threading.Event()
        interrupted.set()
        with patch.object(bench, 'halt', interrupted), patch.object(bench, 'port', Mock()) as port:
            with self.assertRaisesRegex(RuntimeError, 'Stopped by user'):
                bench.receive(5)
            port.readline.assert_not_called()

    def test_no_arbitrary_serial_commands(self):
        with self.assertRaises(ValueError):
            bench.validate({'action': 'laser on', 'contained': True})

    def test_stop_requires_off_telemetry(self):
        with patch.object(bench, 'port', object()), patch.object(bench, 'send') as send, patch.object(bench, 'receive', side_effect=[[], ['OK status armed=0 laser=0']]):
            bench.stop()
            self.assertEqual([x.args[0] for x in send.call_args_list], ['stop', 'status'])
        with patch.object(bench, 'port', object()), patch.object(bench, 'send'), patch.object(bench, 'receive', return_value=[]):
            with self.assertRaises(RuntimeError):
                bench.stop()


if __name__ == '__main__':
    unittest.main()
