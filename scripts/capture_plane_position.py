"""Coordinate one intentional stationary plane capture through existing owners."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
import urllib.request


def status(url):
    return json.load(urllib.request.urlopen(url,timeout=4))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--id',required=True);p.add_argument('--us',type=int,required=True)
    p.add_argument('--exposure-us',type=int,default=10000)
    p.add_argument('--duration',type=float,default=12)
    args=p.parse_args(); run=args.id
    out=Path('outputs/static_checks')/run
    if out.exists() or (Path('data/raw')/(run+'.aedat4')).exists():
        raise ValueError('Existing run: inspect, never replay')
    r=status('http://127.0.0.1:8933/rig/status')
    c=status('http://127.0.0.1:8931/status')
    if not r['fresh'] or r['active'] or not r['controller'].get('agentEnabled') or c['stale'] or c['recording']:
        raise ValueError('Owners not ready')
    def call(script,*words):
        result=subprocess.run([sys.executable,'scripts/'+script,*map(str,words)],capture_output=True,text=True)
        if result.returncode: raise RuntimeError(result.stderr+result.stdout[:500])
        return result.stdout
    ready_count=0
    for _ in range(40):
        ready=status('http://127.0.0.1:8933/rig/status')
        ready_count=ready_count+1 if ready['fresh'] and not ready['active'] and not ready['controller'].get('busy',True) else 0
        if ready_count>=3:break
        time.sleep(.3)
    else:raise ValueError('Dashboard not idle before movement; no operation started')
    if r['controller']['cmd']!=args.us:
        call('rig_ctl.py','--request-id',run+'_move','--contained','move',args.us)
    ready_count=0
    for _ in range(40):
        ready=status('http://127.0.0.1:8933/rig/status')
        ready_count=ready_count+1 if ready['fresh'] and not ready['active'] and not ready['controller'].get('busy',True) else 0
        if ready_count>=3: break
        time.sleep(.3)
    else: raise ValueError('Dashboard not idle after move; no recording/emission started')
    call('camera_ctl.py','exposure',args.exposure_us)
    camera=call('camera_ctl.py','--request-id',run+'_cam','record',run,'--duration',args.duration,
                '--notes',f'Stationary acquisition command{args.us}us exposure{args.exposure_us}us; no physical sync claim')
    # Camera setup and periodic manual telemetry may overlap the serial mailbox.
    # Re-observe idle after camera setup; never weaken or bypass the browser guard.
    ready_count=0
    for _ in range(25):
        ready=status('http://127.0.0.1:8933/rig/status')
        ready_count=ready_count+1 if ready['fresh'] and not ready['active'] and not ready['controller'].get('busy',True) else 0
        if ready_count>=3:break
        time.sleep(.2)
    else:raise ValueError('Dashboard not idle after camera setup; recording remains independently bounded, no emission requested')
    try:
        operation=call('rig_ctl.py','--request-id',run,'--contained','--arm','observe',args.us)
    except Exception:
        # Never retry the actuator here. Camera remains independently bounded.
        raise
    while status('http://127.0.0.1:8931/status')['recording']:
        time.sleep(.3)
    call('analyse_static_capture.py','--request-id',run,'--output',out)
    (out/'camera_operation.json').write_text(camera)
    (out/'dispatch_result.json').write_text(operation)
    call('review_visibility_recording.py',Path('data/raw')/(run+'.aedat4'),'--output',Path('outputs/visibility')/run)
    call('analyse_optical_observation.py',Path('data/raw')/(run+'.aedat4'),'--output',Path('outputs/visibility')/(run+'_optical'))
    summary=json.loads((out/'summary.json').read_text())
    optical=json.loads((Path('outputs/visibility')/(run+'_optical')/'summary.json').read_text())
    (out/'manifest.json').write_text(json.dumps(dict(run_id=run,command_us=args.us,exposure_us=args.exposure_us,trace=summary,optical=optical,
                 camera_sidecar=json.loads((Path('data/raw')/(run+'.json')).read_text()),
                 final=status('http://127.0.0.1:8933/rig/status')['controller']),indent=2))
    if summary['errors']:
        raise ValueError('Invalid saved trace; sequence must stop and inspect '+run)
    print(json.dumps(dict(run=run,trace_errors=summary['errors'],feedback_warning=summary['feedback_screen_warning'],
                         qualifying_frames=len(optical['measurements']),x70=optical.get('x70_range_px'))))


if __name__=='__main__':main()
