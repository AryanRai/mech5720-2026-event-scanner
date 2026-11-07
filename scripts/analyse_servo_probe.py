"""Export one saved bounded probe; never opens serial or operates hardware."""
import argparse
import csv
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
WRAP = 2**32


def analyse(op):
    result = op.get('result') or {}
    samples, events, errors = [], [], []
    phase = 'unknown'
    origin = previous = None
    elapsed = 0
    received = result.get('received') or []
    lines = result.get('lines') or []
    for index, line in enumerate(lines):
        fields = line.split(',')
        if fields[0] not in ('E', 'F'):
            continue
        try:
            tick = int(fields[1])
            if not 0 <= tick < WRAP:
                raise ValueError('invalid controller tick')
            if origin is None:
                origin = tick
            if previous is not None:
                delta = (tick - previous) % WRAP
                if delta > WRAP // 2:
                    raise ValueError('backwards timestamp/reset')
                elapsed += delta
            previous = tick
            if fields[0] == 'E':
                name = fields[2]
                events.append({'t_us': elapsed, 'name': name, 'raw_line': line})
                if name.startswith('PROBE_'):
                    phase = name.removeprefix('PROBE_').lower()
                continue
            if len(fields) != 10:
                raise ValueError('invalid F field count')
            _, begin, end, command, raw, total, count, divisor, attached, laser = map_fields(fields)
            adc_span = (end - begin) % WRAP
            if adc_span > 10000 or count <= 0 or divisor <= 0 or attached not in (0, 1) or laser != 0:
                raise ValueError('invalid ADC block or laser not off')
            if not (1100 <= command <= 1900 and 0 <= raw <= 16383 and 0 <= total <= count * 16383):
                raise ValueError('sample outside bounds')
            host = None
            if index < len(received) and received[index].get('line') == line:
                host = received[index].get('host_rx_monotonic_ms')
            samples.append(dict(t_us=elapsed,adc_duration_us=adc_span,phase=phase,cmd_us=command,
                raw_first=raw,adc_sum=total,adc_count=count,adc_divisor=divisor,
                block_mean_raw=total/count,feedback_scaled=total//divisor,
                attached=attached,laser=laser,host_rx_monotonic_ms=host))
        except (ValueError, IndexError) as exc:
            errors.append(f'{line}: {exc}')
    if not samples:
        errors.append('no F samples')
    if not any(e['name'] == 'PROBE_DONE' for e in events):
        errors.append('no controller PROBE_DONE')
    if any(e['name'] == 'PROBE_ABORTED' for e in events):
        errors.append('controller aborted')
    if op.get('state') != 'done' or result.get('error') or not result.get('stop_confirmed'):
        errors.append('operation incomplete/failed or final STOP not confirmed')
    final = result.get('final_status', '')
    if not all(flag in final.split() for flag in ('armed=0', 'laser=0', 'attached=0')):
        errors.append('final off/disarm/release status missing')
    if result.get('log_truncated'):
        errors.append('log truncated')
    phases = {}
    for label in sorted({s['phase'] for s in samples}):
        group = [s for s in samples if s['phase'] == label]
        gaps = [b['t_us']-a['t_us'] for a,b in zip(group,group[1:])]
        phases[label] = {'n_blocks':len(group),'duration_us':group[-1]['t_us']-group[0]['t_us'],
            'max_sample_gap_us':max(gaps,default=None)}
        for key in ('raw_first','block_mean_raw'):
            values = [s[key] for s in group]
            phases[label][key] = dict(mean=statistics.mean(values),
                sd=statistics.stdev(values) if len(values)>1 else None,min=min(values),max=max(values))
    return {'operation_id':op.get('id'),'status':'VALID_DIAGNOSTIC' if not errors else 'INVALID',
        'errors':errors,'phase_statistics':phases,'events':events,
        'interpretation':'ADC diagnostics only; no independently measured shaft motion, angle, settling criterion or camera synchronization.'}, samples


def map_fields(fields):
    return [fields[0], *map(int, fields[1:])]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--journal',type=Path,default=ROOT/'outputs/agent_control/rig_operations.jsonl')
    parser.add_argument('--request-id',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    op=None
    for line in args.journal.read_text(encoding='utf-8').splitlines():
        entry=json.loads(line)
        if entry.get('id') == args.request_id:
            op=entry
    if op is None or op.get('request',{}).get('action') != 'probe':
        parser.error('No matching probe operation; no hardware action performed')
    summary,samples=analyse(op)
    args.output.mkdir(parents=True,exist_ok=False)
    (args.output/'operation.json').write_text(json.dumps(op,indent=2),encoding='utf-8')
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    if samples:
        with (args.output/'samples.csv').open('w',newline='',encoding='utf-8') as fh:
            writer=csv.DictWriter(fh,fieldnames=list(samples[0]));writer.writeheader();writer.writerows(samples)
    print(json.dumps(summary,indent=2))
    return 0 if summary['status']=='VALID_DIAGNOSTIC' else 1


if __name__=='__main__':
    raise SystemExit(main())
