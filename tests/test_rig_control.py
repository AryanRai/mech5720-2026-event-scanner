import importlib.util
from pathlib import Path
import time
import pytest

spec=importlib.util.spec_from_file_location('rig_control',Path(__file__).parents[1]/'event_camera/rig_control.py')
rig=importlib.util.module_from_spec(spec);spec.loader.exec_module(rig)


def heartbeat(control,**extra):
    return control.heartbeat(dict(client='browser1',connected=True,agentEnabled=True,busy=False,**extra))


@pytest.mark.parametrize('body',[
    {'action':'arbitrary'}, {'action':'move','us':1901}, {'action':'move','us':True},
    {'action':'pulse','seconds':6,'arm':True}, {'action':'pulse','seconds':1},
    {'action':'sweep','start_us':1900,'end_us':1100,'duration_ms':1000,'arm':True},
    {'action':'sweep','start_us':1100,'end_us':1900,'duration_ms':10001,'arm':True},
    {'action':'move','us':1500,'shell':'bad'},
    {'action':'probe','source_us':1500,'target_us':1901,'hold_ms':1000},
    {'action':'probe','source_us':1500,'target_us':1510,'hold_ms':3001},
    {'action':'probe','source_us':1500,'target_us':1510,'hold_ms':True},
    {'action':'probe','source_us':1500,'target_us':1510,'hold_ms':1000,'arm':True},
])
def test_invalid_commands(body):
    with pytest.raises(ValueError):rig.validate(dict(id='test',contained=True,**body))


def test_containment_and_arm_are_explicit():
    with pytest.raises(ValueError):rig.validate({'id':'test','action':'move','us':1500})
    assert rig.validate({'id':'stop','action':'stop'})['action']=='stop'
    assert rig.validate({'id':'probe','action':'probe','source_us':1510,'target_us':1500,'hold_ms':1000,'contained':True})['action']=='probe'


def test_no_automatic_dispatch_and_exactly_once(tmp_path):
    c=rig.RigControl(tmp_path)
    b={'id':'move1','action':'move','us':1500,'contained':True}
    with pytest.raises(ValueError):c.submit(b)
    heartbeat(c)
    assert c.submit(b)['state']=='queued'
    claim=heartbeat(c)['operation']
    assert claim['id']=='move1'
    assert heartbeat(c)['operation'] is None
    assert c.submit(b)['state']=='claimed' # never dispatched twice
    with pytest.raises(ValueError):c.submit(dict(b,us=1520))
    heartbeat(c,result={'id':'move1','error':None,'stop_confirmed':True})
    assert c.ops['move1']['state']=='done'


def test_stop_preempts_and_restart_never_replays(tmp_path):
    c=rig.RigControl(tmp_path);heartbeat(c)
    c.submit({'id':'pulse','action':'pulse','seconds':1,'arm':True,'contained':True})
    heartbeat(c)
    c.submit({'id':'stop','action':'stop'})
    assert c.ops['pulse']['state']=='unknown'
    assert heartbeat(c)['operation']['id']=='stop'
    new=rig.RigControl(tmp_path)
    assert new.ops['stop']['state']=='unknown'
    assert heartbeat(new)['operation'] is None


def test_ownership_staleness_and_busy(tmp_path):
    c=rig.RigControl(tmp_path);heartbeat(c)
    with pytest.raises(ValueError):c.heartbeat({'client':'browser2'})
    c.state['busy']=True
    b={'id':'read','action':'read','n':100,'contained':True}
    with pytest.raises(ValueError):c.submit(b)
    c.updated=time.monotonic()-10
    with pytest.raises(ValueError):c.submit(b)
