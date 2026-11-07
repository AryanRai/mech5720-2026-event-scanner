"""Provider-neutral rig CLI: status, operation ID, move/read/pulse/sweep/stop.

Camera commands use the existing camera_ctl CLI. No serial device is opened.
Actuators require the dashboard connected + Allow local agent control checked.
"""
import argparse
import math
import json
from pathlib import Path
import sys
import time
import urllib.request
import urllib.error
import uuid
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def get(path):
    with urllib.request.urlopen('http://127.0.0.1:8933' + path, timeout=4) as r:
        return json.load(r)


def submit(body):
    descriptor = json.loads((ROOT / '.runtime/rig.json').read_text())
    if descriptor['url'] != 'http://127.0.0.1:8933':
        raise ValueError('Unexpected rig endpoint')
    request = urllib.request.Request(descriptor['url'] + '/rig/command',
        data=json.dumps(body).encode(), method='POST', headers={
            'Content-Type':'application/json','X-Rig-Token':descriptor['token']})
    with urllib.request.urlopen(request, timeout=4) as r:
        return json.load(r)


def main():
    if len(sys.argv)>1 and sys.argv[1]=='camera':
        return subprocess.call([sys.executable,str(ROOT/'scripts/camera_ctl.py'),*sys.argv[2:]])
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--request-id')
    p.add_argument('--contained', action='store_true', help='Explicit verified enclosed/clear beam path')
    p.add_argument('--arm', action='store_true', help='Explicit authorization for this bounded emitting operation')
    p.add_argument('--wait', type=float, default=25)
    sub=p.add_subparsers(dest='action',required=True)
    sub.add_parser('status')
    sub.add_parser('operation').add_argument('id')
    sub.add_parser('move').add_argument('us',type=int)
    sub.add_parser('static', help='Firmware v1.5 fixed-pose capture: 3s dark, stability gate, 1s lit, .5s dark').add_argument('us',type=int)
    sub.add_parser('observe', help='Firmware v1.7 bounded optical observation; ADC amplitude/drift advisory, optical review required').add_argument('us',type=int)
    sub.add_parser('read').add_argument('n',type=int,default=100,nargs='?')
    probe=sub.add_parser('probe',help='Firmware v1.4 laser-off, bounded feedback trace')
    probe.add_argument('source_us',type=int)
    probe.add_argument('target_us',type=int)
    probe.add_argument('hold_ms',type=int)
    sub.add_parser('pulse').add_argument('seconds',type=int)
    for verb in ('sweep','scan'):
        s=sub.add_parser(verb);s.add_argument('start_us',type=int);s.add_argument('end_us',type=int);s.add_argument('duration_ms',type=int)
    sub.add_parser('stop')
    a=p.parse_args()
    if not math.isfinite(a.wait) or not 1 <= a.wait <= 60:
        p.error('--wait must be finite and between 1 and 60 seconds')
    if a.action=='status':
        result={'rig':get('/rig/status')}
        try:result['camera']=get('/camera/status')
        except OSError as exc:result['camera']={'error':str(exc)}
        print(json.dumps(result,indent=2));return 0
    if a.action=='operation':
        print(json.dumps(get('/rig/operations/'+a.id),indent=2));return 0
    body={'id':a.request_id or uuid.uuid4().hex,'action':'sweep' if a.action=='scan' else a.action,'contained':a.contained}
    for key in ('us','n','seconds','start_us','end_us','duration_ms','source_us','target_us','hold_ms'):
        if hasattr(a,key):body[key]=getattr(a,key)
    if a.action in ('pulse','sweep','scan','static','observe'):body['arm']=a.arm
    # Validate before networking. Not an authority check; server validates independently.
    sys.path.insert(0,str(ROOT))
    from event_camera.rig_control import validate
    validate(body)
    print('Request ID: '+body['id'],file=sys.stderr,flush=True)
    camera_started=False
    capture_dir=None
    if a.action=='scan':
        if len(body['id'])>60:
            raise ValueError('Combined scan IDs must be <=60 characters for camera filenames')
        # An existing operation/name is never re-recorded on a repeated CLI call.
        try:
            previous=get('/rig/operations/'+body['id'])
        except urllib.error.HTTPError as exc:
            if exc.code!=404:raise
        else:
            print(json.dumps(previous,indent=2));return 2
        health=get('/camera/status')
        if not health.get('camera_connected') or health.get('stale') or health.get('recording'):
            raise ValueError('DAVIS must be fresh and idle before combined scan')
        rig_health=get('/rig/status')
        controller=rig_health.get('controller',{})
        if not rig_health['fresh'] or not controller.get('connected') or not controller.get('agentEnabled') or controller.get('busy'):
            raise ValueError('Rig must be fresh, connected, agent-enabled and idle before recording')
        capture_dir=ROOT/'outputs/rig_runs'/body['id']
        capture_dir.mkdir(parents=True,exist_ok=False)
        ctl=[sys.executable,str(ROOT/'scripts/camera_ctl.py')]
        started=subprocess.run(ctl+['--request-id',body['id']+'_cam','record','rig_'+body['id'],
            '--duration',str(min(30,a.duration_ms/1000+15)),
            '--notes','Combined scan; Arduino logs in outputs/rig_runs/'+body['id']+'; clock alignment NOT calibrated'],capture_output=True,text=True)
        (capture_dir/'camera_start.log').write_text(started.stdout+started.stderr)
        if started.returncode:
            raise ValueError('Camera start failed/uncertain; inspect '+body['id']+'_cam; never replay')
        camera_started=True
    result=None
    try:
        result=submit(body)
        deadline=time.monotonic()+a.wait
        while result['state'] in ('queued','claimed') and time.monotonic()<deadline:
            time.sleep(.2);result=get('/rig/operations/'+body['id'])
    finally:
        if camera_started:
            stopped=subprocess.run(ctl+['--request-id',body['id']+'_camstop','record-stop'],capture_output=True,text=True)
            (capture_dir/'camera_stop.log').write_text(stopped.stdout+stopped.stderr)
            (capture_dir/'rig_operation.json').write_text(json.dumps(result,indent=2))
            (capture_dir/'manifest.json').write_text(json.dumps({'request':body,'clock_alignment':'NOT calibrated; host overlap only',
                'camera_file':'data/raw/rig_'+body['id']+'.aedat4','camera_stop_returncode':stopped.returncode},indent=2))
    print(json.dumps(result,indent=2))
    if result['state'] in ('queued','claimed','unknown'):
        print('Uncertain/pending: inspect this ID; never issue a new ID to replay.',file=sys.stderr)
        return 2
    return 0 if result['state']=='done' and result.get('result',{}).get('stop_confirmed') else 1


if __name__=='__main__':
    try:sys.exit(main())
    except urllib.error.HTTPError as exc:
        detail=exc.read(2048).decode('utf-8',errors='replace')
        print(json.dumps({'http_status':exc.code,'server_response':detail,'note':'Inspect the printed operation ID before retry; never replay an uncertain operation under a new ID.'},ensure_ascii=True),file=sys.stderr)
        sys.exit(2)
    except (OSError,ValueError) as exc:
        print(str(exc)+' — if submitted, inspect the printed request ID before retrying.',file=sys.stderr)
        sys.exit(2)
