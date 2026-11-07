"""Static optical pulse timing: first pass fit, later passes reserved prediction."""
import argparse
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scripts.compare_static_events_aps import read_events,pulse_pair


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);args=p.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    session=Path('outputs/static_checks/shoe_repeat_session_20261103_02');runs=json.loads((session/'runs.json').read_text());edges=[]
    for r in runs:
        e=read_events(Path('data/raw')/(r['run_id']+'.aedat4'));on,off,pair=pulse_pair(e)
        op=json.loads((Path('outputs/static_checks')/r['run_id']/'operation.json').read_text())
        for name,polarity,centre in [('LASER_ON',1,on),('LASER_OFF',0,off)]:
            select=e[(e['polarity']==polarity)&(e['y']>=20)&(e['y']<=105)&(abs(e['timestamp']-centre)<40000)]
            t=select['timestamp'];bins=np.arange(centre-40000,centre+41000,1000);h,_=np.histogram(t,bins);peak=int(np.argmax(h));peak_time=int(bins[peak])
            burst=t[(t>=peak_time-2000)&(t<peak_time+3000)]
            if len(burst)<20:raise ValueError('Insufficient optical edge support')
            quantiles=np.percentile(burst,[10,50,90])
            ticks=[int(line.split(',')[1]) for line in op['result']['lines'] if line.startswith('E,') and line.split(',')[2]==name]
            if len(ticks)!=1:raise ValueError('Ambiguous firmware marker')
            edges.append(dict(run_id=r['run_id'],repeat=r['repeat'],command_us=r['command_us'],edge=name,controller_tick_us=ticks[0],camera_edge_us=float(quantiles[1]),event_p10_p90_us=quantiles[[0,2]].tolist(),burst_count=len(burst)))
    # Unwrap in chronological acquisition/edge order. Never correct source timestamps.
    origin=edges[0]['controller_tick_us'];last=origin;elapsed=0
    for q in edges:
        tick=q['controller_tick_us'];delta=(tick-last)%2**32
        if delta>=2**31:raise ValueError('Reset/backward controller clock')
        elapsed+=delta;q['controller_elapsed_us']=elapsed;last=tick
    train=[q for q in edges if q['repeat']==1 and q['edge']=='LASER_ON']
    c0=train[0]['camera_edge_us'];x=np.array([q['controller_elapsed_us'] for q in train],float);y=np.array([q['camera_edge_us']-c0 for q in train])
    slope,intercept=np.polyfit(x,y,1)
    for q in edges:
        q['used_for_fit']=q['repeat']==1 and q['edge']=='LASER_ON'
        q['prediction_residual_us']=float((q['camera_edge_us']-c0)-(slope*q['controller_elapsed_us']+intercept))
    summary={}
    for name,selected in [('reserved_ON',[q for q in edges if q['repeat']>1 and q['edge']=='LASER_ON']),('all_OFF',[q for q in edges if q['edge']=='LASER_OFF'])]:
        a=np.array([q['prediction_residual_us'] for q in selected]);summary[name]=dict(n=len(a),rms_ms=float(np.sqrt(np.mean(a*a))/1000),max_absolute_ms=float(abs(a).max()/1000),signed_mean_ms=float(a.mean()/1000))
    limits=('Exploratory camera event burst peak/median versus firmware electrical marker. Fit first-pass5ON edges, reserve subsequent10ON and all15OFF edges. '
        'Static pulses at several positions; optical response/polarity/threshold/background and selection latency contribute to residuals. '
        'Event burst p10-p90 is not an absolute timing uncertainty. No independent timing instrument, moving-stripe validation, per-event servo-plane mapping or continuous reconstruction. '
        'Mapping only for this uninterrupted recording/controller session; invalid after resets/discontinuities. No source timestamps modified.')
    result=dict(status='STATIC_OPTICAL_PULSE_CLOCK_PREDICTION',mapping=dict(controller_tick_origin_us=origin,camera_origin_us=c0,camera_us_per_controller_us=float(slope),intercept_us=float(intercept)),summary=summary,edges=edges,limitations=limits)
    (args.output/'audit.json').write_text(json.dumps(result,indent=2))
    fig,ax=plt.subplots(figsize=(10,4))
    for edge,marker in [('LASER_ON','o'),('LASER_OFF','x')]:
        selected=[q for q in edges if q['edge']==edge]
        ax.plot([q['controller_elapsed_us']/1e6 for q in selected],[q['prediction_residual_us']/1000 for q in selected],marker+'-',label=edge)
    ax.axhline(0,color='black',lw=.7);ax.set(xlabel='Controller elapsed time (s)',ylabel='Optical-edge prediction residual (ms)',title='Static pulse timing: first-pass ON fit; later ON/OFF prediction');ax.legend();ax.grid(alpha=.2)
    fig.tight_layout();fig.savefig(args.output/'timing_prediction.png',dpi=170);plt.close(fig)
    (args.output/'REVIEW.md').write_text('# Static pulse timing prediction\n\n'+limits+'\n\n'+json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
