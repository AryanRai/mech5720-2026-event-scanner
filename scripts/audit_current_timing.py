"""Fit current-session ON-marker clock mapping and predict a reserved pulse."""
import hashlib
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scripts.audit_optical_timing import audit


def main():
    pairs=[('object_swap_stripe_20261103_01','object_swap_observe_20261103_01'),
           ('timing_marker_20261103_02','timing_observe_20261103_02'),
           ('timing_marker_20261103_03','timing_observe_20261103_03')]
    out=Path('outputs/timing/current_session_20261103_01'); out.mkdir(parents=True,exist_ok=False)
    results=[]
    for raw,run in pairs:
        path=Path('data/raw')/(raw+'.aedat4')
        op=json.loads((Path('outputs/static_checks')/run/'operation.json').read_text())
        result=audit(path,op,x_bounds=(0,240))
        result['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
        result['operation']=run
        results.append(result)
    c0,c1=[r['edges'][0]['controller_tick_us'] for r in results[:2]]
    t0,t1=[r['edges'][0]['camera_event_median_us'] for r in results[:2]]
    slope=(t1-t0)/(c1-c0)
    residuals=[]
    for i,r in enumerate(results):
        for e in r['edges']:
            predicted=t0+slope*(e['controller_tick_us']-c0)
            residuals.append(dict(operation=r['operation'],name=e['name'],
                                  fit_point=i<2 and e['name']=='LASER_ON',
                                  prediction_residual_us=float(e['camera_event_median_us']-predicted)))
    result=dict(status='EXPLORATORY_OPTICAL_CLOCK_MAPPING_WITH_RESERVED_PULSE',observations=results,
                mapping=dict(controller_origin_us=c0,camera_origin_us=t0,camera_us_per_controller_us=slope,
                             nominal_rate_difference_ppm=(slope-1)*1e6),residuals=residuals,
                limitations='Postselected APS-difference marker ROI in upper90rows, eventburst median. FitON2pulses, thirdpulse reserved. Initialpulse1500us and newpulses1667us on different background locations. Opticalthreshold/polarity/laser delay and movingstripe timing uncertainty unresolved. Not global synchronization guarantee; invalid after Uno reset or camera clock discontinuity. No calibratedplane1667 or continuous3D. Pulseidentification is offline and no preregistered pass threshold.')
    (out/'audit.json').write_text(json.dumps(result,indent=2))
    values=[r['prediction_residual_us']/1000 for r in residuals]
    fig,ax=plt.subplots(figsize=(8,4))
    ax.bar(np.arange(len(values)),values,color=['#9ca3af' if r['fit_point'] else '#157f91' for r in residuals])
    ax.axhline(0,color='k',linewidth=.7)
    ax.set_xticks(np.arange(len(values)),['Fit1 ON','Pulse1 OFF','Fit2 ON','Pulse2 OFF','Test ON','Test OFF'])
    ax.set(ylabel='Camera event median minus clock prediction (ms)',title='Optical timing audit: third pulse excluded from fitting')
    fig.text(.5,.01,'Exploratory optical edges; residuals are not absolute timing uncertainty or a sweep-depth validation.',ha='center',fontsize=8)
    fig.tight_layout(rect=[0,.04,1,1]);fig.savefig(out/'timing_residuals.png',dpi=180)
    print(json.dumps({k:v for k,v in result.items() if k!='observations'},indent=2))


if __name__=='__main__': main()
