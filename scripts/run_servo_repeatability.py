"""Bounded P2 batch through rig_ctl only; halts on uncertainty or invalid data.

Requires a connected user-enabled dashboard. No serial connection, firmware
upload, arming, emission or camera acquisition is performed by this script.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import rig_ctl
import analyse_servo_probe


def idle():
    deadline=time.monotonic()+4
    while True:
        status=rig_ctl.get('/rig/status'); c=status.get('controller',{})
        if not status.get('fresh') or not c.get('connected') or not c.get('agentEnabled'):
            raise RuntimeError('Dashboard stale/disconnected/disabled; no dispatch')
        if c.get('laser') or c.get('armed'):
            raise RuntimeError('Controller not off/disarmed; no dispatch')
        if status.get('active'):
            raise RuntimeError('Active/uncertain operation; no dispatch')
        if not c.get('busy'):
            if not 1500 <= c.get('cmd',0) <= 1510:
                raise RuntimeError('Initial command outside cleared 1500–1510 window')
            return
        if time.monotonic()>=deadline:
            raise RuntimeError('Dashboard stayed busy; no dispatch')
        time.sleep(.2)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--prefix',required=True)
    parser.add_argument('--execute',action='store_true')
    args=parser.parse_args()
    # Fixed cleared window; any expansion requires deliberate protocol revision.
    conditions=[('up_end',1500,1510),('down_end',1510,1500),
                ('up_mid',1500,1505),('down_mid',1510,1505)]
    trials=[]
    for rep in range(1,6):
        order=conditions if rep%2 else list(reversed(conditions))
        for name,source,target in order:
            ident=f'{args.prefix}_r{rep}_{name}'
            if len(ident)>70:parser.error('Prefix too long')
            trials.append(dict(id=ident,condition=name,repetition=rep,source_us=source,target_us=target,hold_ms=3000))
    args.output.mkdir(parents=True,exist_ok=False)
    plan=dict(status='planned',trials=trials,laser='OFF throughout',
        hold_summary='last 500 ms of target hold; report per-trial means then between-trial SD',
        settling_proxy={'band_raw_adc_counts':1.0,'minimum_remaining_dwell_ms':200,
            'reference':'mean of final 500 ms; first sample after last excursion outside band',
            'limitation':'electrical feedback stability relative to own terminal level, not calibrated shaft settling or target accuracy'},
        rationale='Band rounded above 3x pilot no-step block-mean SD 0.2438 counts; fixed before batch. Five repetitions per condition; interleaved order. Midpoint compares opposite command approaches at same 1505 us target. Source arrival must be checked in analysis; command direction alone is not verified shaft direction.',
        failures='Halt on CLI uncertainty, missing operation result, invalid trace or incomplete off/disarm/release. Never automatically replay.')
    (args.output/'plan.json').write_text(json.dumps(plan,indent=2),encoding='utf-8')
    if not args.execute:
        print('Plan only; no hardware action');return 0
    completed=[]
    for trial in trials:
        try:
            idle()
            directory=args.output/trial['id']
            directory.mkdir()
            command=[sys.executable,str(ROOT/'scripts/rig_ctl.py'),'--request-id',trial['id'],'--contained',
                'probe',str(trial['source_us']),str(trial['target_us']),str(trial['hold_ms'])]
            process=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=40)
            (directory/'cli_stdout.log').write_text(process.stdout,encoding='utf-8')
            (directory/'cli_stderr.log').write_text(process.stderr,encoding='utf-8')
            op=rig_ctl.get('/rig/operations/'+trial['id'])
            (directory/'operation.json').write_text(json.dumps(op,indent=2),encoding='utf-8')
            result=op.get('result') or {}
            # A saved, explicit pre-dispatch guard refusal is not uncertain
            # motion. Retain it, do not replay it, continue to the next trial.
            known_refusal=(op.get('state')=='failed' and
                result.get('error')=='Dashboard not idle/agent-enabled; no action performed' and
                result.get('stop_confirmed') is True and not result.get('probe_dispatched') and
                all(flag in result.get('final_status','').split() for flag in ('armed=0','laser=0','attached=0')))
            if known_refusal:
                completed.append(dict(trial,status='REFUSED_BEFORE_DISPATCH'))
                (args.output/'progress.json').write_text(json.dumps(completed,indent=2),encoding='utf-8')
                print(f'{len(completed)}/{len(trials)} {trial["id"]}: REFUSED_BEFORE_DISPATCH (no replay)',flush=True)
                continue
            if process.returncode:
                raise RuntimeError(f'CLI returned {process.returncode}; inspect {trial["id"]}; no replay')
            summary,samples=analyse_servo_probe.analyse(op)
            (directory/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
            import csv
            if samples:
                with (directory/'samples.csv').open('w',newline='',encoding='utf-8') as f:
                    w=csv.DictWriter(f,fieldnames=list(samples[0]));w.writeheader();w.writerows(samples)
            completed.append(dict(trial,status=summary['status']))
            (args.output/'progress.json').write_text(json.dumps(completed,indent=2),encoding='utf-8')
            print(f'{len(completed)}/{len(trials)} {trial["id"]}: {summary["status"]}',flush=True)
            if summary['status']!='VALID_DIAGNOSTIC':
                raise RuntimeError('Invalid trace; batch halted for inspection')
        except Exception as exc:
            (args.output/'HALTED.txt').write_text(str(exc),encoding='utf-8')
            print(str(exc),file=sys.stderr,flush=True)
            return 2
    (args.output/'BATCH_FINISHED.txt').write_text('Planned sequence finished; inspect progress.json for acquired/refused trial counts. Analysis still required.\n')
    return 0


if __name__=='__main__':raise SystemExit(main())
