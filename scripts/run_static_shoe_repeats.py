"""Three independent acquisition passes at five previously used shoe positions."""
import json
from pathlib import Path
import subprocess
import sys
import argparse
import urllib.request
from datetime import datetime, timezone


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--session',default='01');args=parser.parse_args()
    if not args.session.isdigit():raise ValueError('Numeric session suffix required')
    session='shoe_repeat_session_20261103_'+args.session
    out=Path('outputs/static_checks')/session
    out.mkdir(parents=True,exist_ok=False)
    commands=[1569,1590,1602,1627,1647]
    protocol=dict(created_utc=datetime.now(timezone.utc).isoformat(),commands_us=commands,passes=3,
        exposure_us=35000,pulse_s=1,recording_s=12,approach='Existing dashboard move operation; ascending command order per pass',
        event_analysis='Frozen compare_static_events_aps.py primary50ms, sensitivity20/100ms; no threshold changes on new repeats',
        aps_analysis='Existing delta20/intensity40 APS detector; rows20..105; frozenABC model; no registration',
        interpretation='Per-command repeated acquisitions, not full20-position repeated scans or independent accuracy. No geometry/ND/speed change.')
    (out/'protocol.json').write_text(json.dumps(protocol,indent=2))
    runs=[]
    try:
        before=subprocess.run([sys.executable,'scripts/camera_ctl.py','--request-id',session+'_before','snapshot',session+'_before'],capture_output=True,text=True)
        (out/'before_snapshot.txt').write_text(before.stdout+before.stderr)
        if before.returncode:raise RuntimeError('Reference snapshot failed before any acquisition')
        for repeat in range(1,4):
            for command in commands:
                run=f'shoe_repeat_r{repeat}_{command}_20261103_{args.session}'
                print(json.dumps(dict(start=run)),flush=True)
                result=subprocess.run([sys.executable,'scripts/capture_plane_position.py','--id',run,'--us',str(command),
                    '--exposure-us','35000','--duration','12'],capture_output=True,text=True)
                (out/(run+'.stdout.txt')).write_text(result.stdout)
                (out/(run+'.stderr.txt')).write_text(result.stderr)
                record=dict(run_id=run,repeat=repeat,command_us=command,returncode=result.returncode)
                runs.append(record);(out/'runs.json').write_text(json.dumps(runs,indent=2))
                print(json.dumps(record),flush=True)
                if result.returncode:raise RuntimeError('Capture failed; inspect saved operation, never retry: '+run)
        after=subprocess.run([sys.executable,'scripts/camera_ctl.py','--request-id',session+'_after','snapshot',session+'_after'],capture_output=True,text=True)
        (out/'after_snapshot.txt').write_text(after.stdout+after.stderr)
    finally:
        # STOP is a separate protective operation, never a replay of an acquisition.
        stop=subprocess.run([sys.executable,'scripts/rig_ctl.py','--request-id',session+'_finalstop','stop'],capture_output=True,text=True)
        (out/'final_stop.txt').write_text(stop.stdout+'\n'+stop.stderr)
        with urllib.request.urlopen('http://127.0.0.1:8933/rig/status',timeout=4) as response:final=json.load(response)
        (out/'final_status.json').write_text(json.dumps(final,indent=2))
    print(json.dumps(dict(completed=len(runs),output=str(out))),flush=True)


if __name__=='__main__':main()
