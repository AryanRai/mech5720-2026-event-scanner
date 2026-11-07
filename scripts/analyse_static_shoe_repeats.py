"""Analyse three fresh per-command acquisitions; no registration or refitting."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import cv2
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scripts.compare_static_events_aps import read_events,pulse_pair,event_rows,xyz
from scripts.reconstruct_sparse_shoe import detect


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--session',required=True,type=Path);p.add_argument('--output',required=True,type=Path);args=p.parse_args()
    runs=json.loads((args.session/'runs_with_correction.json').read_text())
    if len(runs)!=18 or any(r['returncode'] for r in runs):raise ValueError('Need eighteen completed records including preserved1627 and three1626 correction acquisitions')
    args.output.mkdir(parents=True,exist_ok=False)
    mp=Path('outputs/calibration/dense_planes_ABC_20261103_01/planes.json');model=json.loads(mp.read_text())
    digest=hashlib.sha256(mp.read_bytes()).hexdigest();assert digest==json.loads((mp.parent/'frozen_model.json').read_text())['planes_sha256']
    intr=json.loads(Path(model['intrinsics']).read_text())['models']['primary_five_coefficient'];k=np.array(intr['camera_matrix']);dist=np.array(intr['distortion_coefficients'])
    planes={q['command_us']:q for q in model['planes'] if 'normal_camera' in q}
    excluded=[r for r in runs if r['command_us'] not in planes]
    runs=[r for r in runs if r['command_us'] in planes]
    points=[];observations=[];data={}
    for r in runs:
        raw=Path('data/raw')/(r['run_id']+'.aedat4');trace=json.loads((Path('outputs/static_checks')/r['run_id']/'summary.json').read_text())
        if trace['errors']:raise ValueError('Invalid trace '+r['run_id'])
        e=read_events(raw);on,off,pair=pulse_pair(e);a,_,_=detect(raw,20,40)
        a=a[(a[:,1]>=20)&(a[:,1]<=105)] if len(a) else np.empty((0,2))
        ev,_=event_rows(e,on,1,50);ef,_=event_rows(e,off,0,50);el={int(q[1]):q[0] for q in ef}
        ev=np.array([q for q in ev if int(q[1]) in el and abs(q[0]-el[int(q[1])])<=3]).reshape(-1,2)
        obs={**r,'raw_sha256':hashlib.sha256(raw.read_bytes()).hexdigest(),'pair':pair,'feedback_warning':trace['feedback_screen_warning'],'support':{},'training_depth_range_check':{}}
        for method,pixels in [('APS',a),('Events',ev)]:
            coords,valid=xyz(pixels,planes[r['command_us']],k,dist);pixels=pixels[valid]
            data[(r['command_us'],r['repeat'],method)]={int(q[1]):[*q,*z] for q,z in zip(pixels,coords)}
            obs['support'][method]=len(coords)
            training=np.concatenate([np.array(q['points_camera_mm']) for q in planes[r['command_us']]['observations']])
            low,high=training[:,2].min(),training[:,2].max()
            obs['training_depth_range_check'][method]=dict(training_Z_range_mm=[float(low),float(high)],
                outside_count=int(np.sum((coords[:,2]<low)|(coords[:,2]>high))),
                reconstructed_Z_range_mm=[float(coords[:,2].min()),float(coords[:,2].max())] if len(coords) else None,
                interpretation='Model-derived range membership, not accuracy; no points deleted')
            for q,z in zip(pixels,coords):points.append([r['command_us'],r['repeat'],method,*q,*z])
        observations.append(obs)
    stats=[];rowstats=[]
    for command in sorted(planes):
        if not any(r['command_us']==command for r in runs):continue
        for method in ['APS','Events']:
            d=[data[(command,repeat,method)] for repeat in [1,2,3]]
            common=sorted(set(d[0])&set(d[1])&set(d[2]));sds=[];xsd=[]
            for row in common:
                v=np.array([q[row] for q in d]);zs=float(np.std(v[:,4],ddof=1));xs=float(np.std(v[:,0],ddof=1));sds.append(zs);xsd.append(xs)
                rowstats.append([command,method,row,*v[:,4],zs,xs])
            support=[len(q) for q in d]
            stats.append(dict(command_us=command,method=method,independent_acquisitions=3,rows_present_in_all_three=len(common),
                root_mean_row_depth_sample_variance_mm=float(np.sqrt(np.mean(np.square(sds)))) if sds else None,
                median_row_depth_sample_sd_mm=float(np.median(sds)) if sds else None,
                root_mean_row_x_sample_variance_px=float(np.sqrt(np.mean(np.square(xsd)))) if xsd else None,
                retained_rows_each_acquisition=support,support_mean=float(np.mean(support)),support_sample_sd=float(np.std(support,ddof=1))))
    matched=[]
    for command in sorted({r['command_us'] for r in runs}):
        common=set.intersection(*(set(data[(command,repeat,method)]) for method in ['APS','Events'] for repeat in [1,2,3]))
        entry=dict(command_us=command,common_rows_both_methods_all_three=len(common))
        for method in ['APS','Events']:
            variances=[np.var([data[(command,repeat,method)][row][4] for repeat in [1,2,3]],ddof=1) for row in sorted(common)]
            entry[method+'_depth_repeatability_mm']=float(np.sqrt(np.mean(variances))) if variances else None
        matched.append(entry)
    before=cv2.imread(str(Path('outputs/agent_control')/(args.session.name+'_before')/'aps.png'),0)
    after=cv2.imread(str(Path('outputs/agent_control')/(args.session.name+'_after_supplement')/'aps.png'),0)
    shift,response=cv2.phaseCorrelate(before.astype(np.float32),after.astype(np.float32))
    limitation=('Three new acquisitions at each of five commands, same stationary shoe placement; no registration, refitting or bias correction. '
        'Object was moved BEFORE this session; old shoe data excluded from repeatability. Same image row across repeats identifies a sampling ray, not independently tracked physical material. '
        'Depth variation includes servo, stripe detector and scene effects. Fixed command planes retain known calibration errors. '
        'Row SD uses n=3 acquisitions and ddof1; many correlated rows are not extra repeats. Common-row selection can favour reliably detectable areas; report support counts too. '
        'Events use two50ms transition windows; APS pools selected lit35ms frames, so this is not equal integration-time, speed, latency or photon-budget comparison. '
        'The image-row ROI includes possible background/target crossings after shoe repositioning; interpret as scene-stripe repeatability, not isolated shoe accuracy. '
        'Some model-derived APS depths fall outside training ranges; counts retained and reported, no depth filtering. '
        'No independent absolute accuracy or full-surface completeness. Temporal scene stability diagnostic is not rigid-body proof.')
    result=dict(status='THREE_ACQUISITIONS_PER_COMMAND_STATIC_REPEATABILITY',model_sha256=digest,session=str(args.session),stats=stats,matched_support_stats=matched,observations=observations,
        retained_unfitted_records_excluded_from_depth=excluded,command_correction='Initial1627 had no fitted plane; preserved and excluded. Three additional1626 acquisitions used instead. No interpolation.',
        reference_stability=dict(phase_correlation_shift_xy_px=list(shift),response=response,alignment_applied=False),limitations=limitation)
    (args.output/'repeatability.json').write_text(json.dumps(result,indent=2))
    for name,header,rows in [('points.csv',['command_us','repeat','method','pixel_x','pixel_y','X_mm','Y_mm','Z_mm'],points),
        ('row_repeatability.csv',['command_us','method','pixel_y','Z_repeat1_mm','Z_repeat2_mm','Z_repeat3_mm','Z_sample_sd_mm','x_sample_sd_px'],rowstats)]:
        with (args.output/name).open('w',newline='') as f:w=csv.writer(f);w.writerow(header);w.writerows(rows)
    fig,axes=plt.subplots(1,2,figsize=(11,4.5))
    for method,color in [('APS','#1685bc'),('Events','#e96b25')]:
        ss=[q for q in stats if q['method']==method];x=[q['command_us'] for q in ss]
        axes[0].plot([q['command_us'] for q in matched],[q[method+'_depth_repeatability_mm'] for q in matched],'o-',label=method,color=color)
        axes[1].errorbar(x,[q['support_mean'] for q in ss],yerr=[q['support_sample_sd'] for q in ss],fmt='o-',capsize=4,label=method,color=color)
    axes[0].set(xlabel='Servo command (µs)',ylabel='Root mean row depth sample variance (mm)',title='Same rows in both methods and all3 trials')
    axes[1].set(xlabel='Servo command (µs)',ylabel='Retained image rows (mean ± sample SD)',title='Detection support over3 acquisitions')
    for ax in axes:ax.legend();ax.grid(alpha=.2)
    fig.suptitle('Static scene-stripe repeatability — n=3 acquisitions per command');fig.tight_layout();fig.savefig(args.output/'repeatability.png',dpi=170);plt.close(fig)
    lines=['# Static shoe repeatability','',limitation,'','| Command (µs) | Method | Common rows | Depth repeatability (mm) | Retained rows in trials1/2/3 |','|---|---|---|---|---|']
    for q in stats:lines.append(f"| {q['command_us']} | {q['method']} | {q['rows_present_in_all_three']} | {q['root_mean_row_depth_sample_variance_mm']} | {q['retained_rows_each_acquisition']} |")
    lines+=['','Matched-support comparison (same rows in both methods and all three acquisitions):','',json.dumps(matched,indent=2)]
    (args.output/'REVIEW.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(result['stats'],indent=2))


if __name__=='__main__':main()
