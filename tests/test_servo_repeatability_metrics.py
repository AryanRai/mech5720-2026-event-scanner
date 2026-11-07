import importlib.util
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('servo_metrics',Path(__file__).parents[1]/'scripts/summarise_servo_repeatability.py')
metrics=importlib.util.module_from_spec(spec);spec.loader.exec_module(metrics)


def samples(values):
    return [dict(phase='source_hold',t_us=-200000,block_mean_raw=300),
            dict(phase='source_hold',t_us=-100000,block_mean_raw=300)]+[
        dict(phase='target_hold',t_us=i*100000,block_mean_raw=v) for i,v in enumerate(values)]


def test_stable_unmoved_can_pass_proxy_but_delta_is_zero():
    result=metrics.terminal_metrics(samples([300]*11),0,1,200000)
    assert result['electrical_stability_ms']==0
    assert result['feedback_change_raw']==0


def test_transient_before_stable_tail():
    result=metrics.terminal_metrics(samples([310,305,300]+[300]*8),0,1,200000)
    assert result['electrical_stability_ms']==200


def test_late_excursion_has_no_minimum_remaining_dwell():
    result=metrics.terminal_metrics(samples([300]*9+[305,300]),0,1,200000)
    assert result['electrical_stability_ms'] is None


def test_terminal_reference_uses_final_half_second():
    result=metrics.terminal_metrics(samples([305]*5+[302]*6),0,1,200000)
    assert result['terminal_mean_raw']==302
    assert result['feedback_change_raw']==2
