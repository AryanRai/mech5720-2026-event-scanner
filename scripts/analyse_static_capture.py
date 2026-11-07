"""Offline integrity and feedback review of saved static acquisition operations."""
import argparse
import csv
import json
from pathlib import Path
import statistics


def analyse(op):
    result=op.get('result') or {}
    errors=[];samples=[];events=[];previous=None;elapsed=0;phase='initial'
    for line in result.get('lines',[]):
        parts=line.split(',')
        if parts[0] not in ('F','E'):continue
        try:
            tick=int(parts[1])
            if not 0<=tick<2**32:raise ValueError('tick bounds')
            if previous is not None:
                delta=(tick-previous)%2**32
                if delta>=2**31:raise ValueError('backwards/reset timestamp')
                elapsed+=delta
            previous=tick
            if parts[0]=='E':
                name=parts[2];events.append(dict(t_us=elapsed,name=name,line=line))
                if name=='STATIC_DARK':phase='dark_hold'
                elif name=='STATIC_LIT':phase='lit_hold'
                elif name=='LASER_OFF' and phase=='lit_hold':phase='post_dark'
                continue
            if len(parts)!=10:raise ValueError('malformed F record')
            begin,end,cmd,raw,total,count,divisor,attached,laser=map(int,parts[1:])
            if not (0< count<=64 and divisor>0 and attached==1 and laser in (0,1)
                    and cmd==op['request']['us'] and 0<=raw<=1023 and 0<=total<=1023*count
                    and (end-begin)%2**32<10000):raise ValueError('invalid ADC/attachment/command')
            samples.append(dict(t_us=elapsed,phase=phase,cmd_us=cmd,adc_sum=total,
                adc_count=count,block_mean_raw=total/count,raw_first=raw,attached=attached,laser=laser))
        except (ValueError,IndexError,KeyError) as exc:errors.append(f'{line}: {exc}')
    names=[e['name'] for e in events]
    if not samples:errors.append('No samples')
    if result.get('log_truncated'):errors.append('Truncated log')
    final=result.get('final_status','').split()
    if not result.get('stop_confirmed') or not all(x in final for x in ('armed=0','laser=0','attached=0')):
        errors.append('Final off/disarm/release unconfirmed')
    aborted='STATIC_ABORTED' in names
    if not (aborted or 'STATIC_DONE' in names):errors.append('No controller completion marker')
    on=[e['t_us'] for e in events if e['name']=='LASER_ON']
    off=[e['t_us'] for e in events if e['name']=='LASER_OFF']
    if not aborted and (op.get('state')!='done' or result.get('error') or len(on)!=1 or len(off)!=1):
        errors.append('Success status/light markers inconsistent')
    if not aborted and not any(s['laser']==1 for s in samples):errors.append('No lit feedback blocks')
    groups={}
    for phase in sorted({s['phase'] for s in samples}):
        rows=[s for s in samples if s['phase']==phase];v=[s['block_mean_raw'] for s in rows]
        groups[phase]=dict(n=len(v),mean=statistics.mean(v),sd=statistics.stdev(v) if len(v)>1 else None,
                          minimum=min(v),maximum=max(v))
    dark=[s for s in samples if s['phase']=='dark_hold'][-50:]
    values=[s['block_mean_raw'] for s in dark]
    gate=dict(n=len(values),mean=statistics.mean(values) if values else None,
              max_deviation_raw=max((abs(v-statistics.mean(values)) for v in values),default=None))
    status='INVALID' if errors else ('ABORTED_FEEDBACK_GATE' if 'STATIC_UNSTABLE' in names and not on
                                    else 'ABORTED_OTHER' if aborted else 'OBSERVATION_TRACE_REQUIRES_OPTICAL_REVIEW' if 'STATIC_OBSERVE' in names else 'VALID_HELD_COMMAND_TRACE')
    return dict(id=op['id'],status=status,observation_mode='STATIC_OBSERVE' in names,feedback_screen_warning='STATIC_SCREEN_WARN' in names,errors=errors,events=events,phase_statistics=groups,
                prelight_last50=gate,controller_light_interval_us=(off[0]-on[0]) if len(on)==len(off)==1 else None,
                limitations='Electrical held-command trace; no independent physical plane stability, calibrated angle or camera time alignment.'),samples


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--request-id',required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--journal',type=Path,default=Path('outputs/agent_control/rig_operations.jsonl'))
    a=p.parse_args();op=None
    for line in a.journal.read_text(encoding='utf-8').splitlines():
        entry=json.loads(line)
        if entry['id']==a.request_id:op=entry
    if op is None or op['request']['action'] not in ('static','observe'):p.error('No saved static/observe operation')
    summary,samples=analyse(op)
    a.output.mkdir(parents=True,exist_ok=False)
    (a.output/'operation.json').write_text(json.dumps(op,indent=2))
    (a.output/'summary.json').write_text(json.dumps(summary,indent=2))
    if samples:
        with (a.output/'samples.csv').open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(samples[0]));w.writeheader();w.writerows(samples)
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
