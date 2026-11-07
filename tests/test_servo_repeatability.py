import importlib.util
from pathlib import Path
from types import SimpleNamespace
import sys
import pytest

spec=importlib.util.spec_from_file_location('servo_repeatability',Path(__file__).parents[1]/'scripts/run_servo_repeatability.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)


@pytest.mark.parametrize('change',[{'armed':True},{'laser':True},{'cmd':1499},{'connected':False},{'agentEnabled':False}])
def test_no_dispatch_when_not_ready(monkeypatch,change):
    c=dict(connected=True,agentEnabled=True,busy=False,armed=False,laser=False,cmd=1500)
    c.update(change)
    monkeypatch.setattr(runner.rig_ctl,'get',lambda _:dict(fresh=True,active=None,controller=c))
    with pytest.raises(RuntimeError):runner.idle()


def test_plan_does_not_operate_and_all_travel_in_cleared_window(monkeypatch,tmp_path):
    import json
    monkeypatch.setattr(sys,'argv',['batch','--output',str(tmp_path/'plan'),'--prefix','test'])
    monkeypatch.setattr(runner,'idle',lambda:pytest.fail('plan must not inspect/operate hardware'))
    assert runner.main()==0
    plan=json.loads((tmp_path/'plan/plan.json').read_text())
    assert len(plan['trials'])==20
    assert all(1500<=t['source_us']<=1510 and 1500<=t['target_us']<=1510 for t in plan['trials'])


def test_failure_halts_without_retry_or_second_trial(monkeypatch,tmp_path):
    monkeypatch.setattr(sys,'argv',['batch','--output',str(tmp_path/'run'),'--prefix','test','--execute'])
    monkeypatch.setattr(runner,'idle',lambda:None)
    monkeypatch.setattr(runner.rig_ctl,'get',lambda _:dict(state='unknown',result={}))
    calls=[]
    def uncertain(command,**kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=2,stdout='unknown',stderr='inspect operation')
    monkeypatch.setattr(runner.subprocess,'run',uncertain)
    assert runner.main()==2
    assert len(calls)==1
    assert (tmp_path/'run/HALTED.txt').exists()


def test_confirmed_refusal_advances_without_replaying(monkeypatch,tmp_path):
    import json
    monkeypatch.setattr(sys,'argv',['batch','--output',str(tmp_path/'run'),'--prefix','test','--execute'])
    monkeypatch.setattr(runner,'idle',lambda:None)
    calls=[]
    def failed(command,**kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=1,stdout='failed',stderr='')
    monkeypatch.setattr(runner.subprocess,'run',failed)
    def result(_):
        if len(calls)==1:
            return dict(state='failed',result=dict(error='Dashboard not idle/agent-enabled; no action performed',
                stop_confirmed=True,final_status='OK status armed=0 laser=0 attached=0'))
        return dict(state='unknown',result={})
    monkeypatch.setattr(runner.rig_ctl,'get',result)
    assert runner.main()==2
    assert len(calls)==2
    assert calls[0][calls[0].index('--request-id')+1]!=calls[1][calls[1].index('--request-id')+1]
    assert json.loads((tmp_path/'run/progress.json').read_text())[0]['status']=='REFUSED_BEFORE_DISPATCH'
