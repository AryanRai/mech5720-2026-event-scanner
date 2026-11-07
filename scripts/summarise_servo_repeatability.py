"""Reproduce P2 feedback repeatability statistics from saved bounded trials."""
import argparse
import csv
import json
from pathlib import Path
import statistics
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def stats(values):
    return dict(n=len(values),mean=statistics.mean(values) if values else None,
        sd=statistics.stdev(values) if len(values)>1 else None,
        min=min(values,default=None),max=max(values,default=None))


def terminal_metrics(samples,marker,band,dwell_us):
    target=[s for s in samples if s['phase']=='target_hold']
    source=[s for s in samples if s['phase']=='source_hold']
    end=max(float(s['t_us']) for s in target)
    terminal=[float(s['block_mean_raw']) for s in target if float(s['t_us'])>=end-500000]
    reference=statistics.mean(terminal)
    last_out=-1
    for i,s in enumerate(target):
        if abs(float(s['block_mean_raw'])-reference)>band:last_out=i
    candidate=last_out+1
    stable_us=None
    if candidate<len(target):
        start=float(target[candidate]['t_us'])
        if end-start>=dwell_us:
            stable_us=max(0,start-marker)
    source_end=max(float(s['t_us']) for s in source)
    source_mean=statistics.mean(float(s['block_mean_raw']) for s in source if float(s['t_us'])>=source_end-200000)
    return dict(terminal_mean_raw=reference,terminal_within_run_sd_raw=statistics.stdev(terminal),
        source_terminal_mean_raw=source_mean,feedback_change_raw=reference-source_mean,
        electrical_stability_ms=stable_us/1000 if stable_us is not None else None,
        stable_before_end=stable_us is not None,n_terminal_blocks=len(terminal))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('batch',type=Path)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();plan=json.loads((a.batch/'plan.json').read_text())
    a.output.mkdir(parents=True,exist_ok=False)
    policy=plan['settling_proxy'];rows=[];traces={}
    for trial in plan['trials']:
        d=a.batch/trial['id'];row=dict(trial,status='NOT_ACQUIRED')
        if (d/'operation.json').exists():
            op=json.loads((d/'operation.json').read_text())
            row['status']='OPERATION_FAILED' if op['state']!='done' else 'NO_VALID_EXPORT'
            row['operation_error']=(op.get('result') or {}).get('error') or ''
            if row['operation_error']=='Dashboard not idle/agent-enabled; no action performed' and not (op.get('result') or {}).get('probe_dispatched'):
                row['status']='REFUSED_BEFORE_DISPATCH'
        if (d/'summary.json').exists():
            summary=json.loads((d/'summary.json').read_text());row['status']=summary['status']
            if row['status']=='VALID_DIAGNOSTIC':
                with (d/'samples.csv').open(newline='') as f:samples=list(csv.DictReader(f))
                marker=next(e['t_us'] for e in summary['events'] if e['name']=='PROBE_TARGET_HOLD')
                row.update(terminal_metrics(samples,marker,policy['band_raw_adc_counts'],policy['minimum_remaining_dwell_ms']*1000))
                traces[trial['id']]=(samples,marker)
        rows.append(row)
    keys=list(dict.fromkeys(k for row in rows for k in row))
    with (a.output/'trial_metrics.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
    groups={}
    for condition in dict.fromkeys(t['condition'] for t in plan['trials']):
        valid=[r for r in rows if r['condition']==condition and r['status']=='VALID_DIAGNOSTIC']
        groups[condition]=dict(terminal_mean_raw=stats([r['terminal_mean_raw'] for r in valid]),
            electrical_stability_ms=stats([r['electrical_stability_ms'] for r in valid if r['stable_before_end']]),
            stability_failures=sum(not r['stable_before_end'] for r in valid),
            commanded_direction_response=stats([r['feedback_change_raw'] for r in valid]))
    up=groups['up_mid']['terminal_mean_raw']['mean'];down=groups['down_mid']['terminal_mean_raw']['mean']
    summary=dict(conditions=groups,
        midpoint_up_minus_down_raw=up-down if up is not None and down is not None else None,
        acquired=sum(r['status']=='VALID_DIAGNOSTIC' for r in rows),planned=len(rows),
        limitations=['Counts are electrical feedback units, not calibrated angles or depth.',
            'Stability is relative to own terminal reference; a stable wrong or unmoved position can pass.',
            'Command approach direction does not prove actual shaft approach direction; inspect source feedback.',
            'Between-trial SD is descriptive; samples within a trial are correlated.',
            'Only 1500–1510 us was tested; source hold is 500 ms, target hold is 3000 ms.'])
    (a.output/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    fig,axes=plt.subplots(2,2,figsize=(12,8));colors=plt.get_cmap('tab10')
    for ax,condition in zip(axes.flat,groups):
        for row in rows:
            if row['condition']!=condition or row['id'] not in traces:continue
            samples,marker=traces[row['id']]
            target=[s for s in samples if s['phase']=='target_hold']
            ax.plot([(float(s['t_us'])-marker)/1e6 for s in target],
                [float(s['block_mean_raw']) for s in target],lw=.7,alpha=.8,
                color=colors(row['repetition']-1),label=f'Trial {row["repetition"]}')
        ax.set_title(f'{condition}: n={groups[condition]["terminal_mean_raw"]["n"]}')
        ax.set_xlabel('Time after target command reached (s)');ax.set_ylabel('Block mean (raw ADC counts)')
        ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.suptitle('Laser-off P2: repeat approaches in 1500–1510 µs window\nElectrical feedback traces; independent shaft position not measured')
    fig.tight_layout(rect=(0,0,1,.93));fig.savefig(a.output/'repeatability_traces.png',dpi=160);plt.close(fig)
    fig,ax=plt.subplots(figsize=(9,5))
    for i,(condition,g) in enumerate(groups.items()):
        values=[r['terminal_mean_raw'] for r in rows if r['condition']==condition and r['status']=='VALID_DIAGNOSTIC']
        ax.scatter([i]*len(values),values,s=24,zorder=3)
        if values:ax.errorbar(i+.15,g['terminal_mean_raw']['mean'],yerr=g['terminal_mean_raw']['sd'] or 0,fmt='ks',capsize=5)
    ax.set_xticks(range(len(groups)),groups);ax.set_ylabel('Mean in final 0.5 s (raw ADC counts)')
    ax.set_title('Per-trial held feedback; black marker: mean ± between-trial SD')
    ax.grid(axis='y',alpha=.2);fig.tight_layout();fig.savefig(a.output/'terminal_repeatability.png',dpi=160);plt.close(fig)
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
