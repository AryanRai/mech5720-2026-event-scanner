"""Combined acquisition orchestration tests; no hardware/network access."""
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import urllib.error
import pytest

spec=importlib.util.spec_from_file_location('rig_cli',Path(__file__).parents[1]/'scripts/rig_ctl.py')
cli=importlib.util.module_from_spec(spec);spec.loader.exec_module(cli)


def prepare(monkeypatch,tmp_path):
    monkeypatch.setattr(cli,'ROOT',tmp_path)
    monkeypatch.setattr(sys,'argv',['rig_ctl.py','--request-id','scan_test','--contained','--arm','scan','1480','1520','1000'])
    def get(path):
        if path.startswith('/rig/operations/'):
            raise urllib.error.HTTPError(path,404,'unknown',{},None)
        if path=='/camera/status':return {'camera_connected':True,'stale':False,'recording':None}
        return {'fresh':True,'controller':{'connected':True,'agentEnabled':True,'busy':False}}
    monkeypatch.setattr(cli,'get',get)
    calls=[]
    def run(args,**kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0,stdout='done',stderr='')
    monkeypatch.setattr(cli.subprocess,'run',run)
    return calls


def test_scan_records_then_finalizes_with_manifest(monkeypatch,tmp_path):
    calls=prepare(monkeypatch,tmp_path)
    monkeypatch.setattr(cli,'submit',lambda b:{'id':b['id'],'state':'done','result':{'stop_confirmed':True}})
    assert cli.main()==0
    assert 'record' in calls[0] and 'record-stop' in calls[1]
    manifest=json.loads((tmp_path/'outputs/rig_runs/scan_test/manifest.json').read_text())
    assert manifest['request']['action']=='sweep'
    assert 'NOT calibrated' in manifest['clock_alignment']


def test_uncertain_dispatch_still_stops_camera_without_replay(monkeypatch,tmp_path):
    calls=prepare(monkeypatch,tmp_path)
    def submit(body):raise OSError('uncertain dispatch')
    monkeypatch.setattr(cli,'submit',submit)
    with pytest.raises(OSError):cli.main()
    assert len(calls)==2 and 'record-stop' in calls[-1]


def test_existing_scan_id_never_records_again(monkeypatch,tmp_path):
    calls=prepare(monkeypatch,tmp_path)
    monkeypatch.setattr(cli,'get',lambda path:{'id':'scan_test','state':'claimed'})
    assert cli.main()==2
    assert calls==[]
