"""Exploratory paired static event/APS reconstruction from retained recordings.

No hardware access. Event locations are extracted without APS spatial guidance.
The known one-second pulse duration selects a candidate ON/OFF pair, not a
continuous camera/controller clock mapping. All screening settings are recorded.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path

import cv2
import dv_processing as dv
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from scripts.reconstruct_sparse_shoe import detect


def read_events(raw):
    reader=dv.io.MonoCameraRecording(str(raw)); batches=[]
    while True:
        batch=reader.getNextEventBatch()
        if batch is None: break
        batches.append(batch.numpy())
    return np.concatenate(batches)


def pulse_pair(e):
    origin=int(e['timestamp'][0]); edges=np.arange(origin,int(e['timestamp'][-1])+5000,5000)
    roi=(e['y']>=20)&(e['y']<=105)
    on=np.histogram(e['timestamp'][roi&(e['polarity']==1)],edges)[0]
    off=np.histogram(e['timestamp'][roi&(e['polarity']==0)],edges)[0]
    # A centred 25 ms count reduces dependence on a single temporal bin.
    a=np.convolve(on,np.ones(5),mode='same'); b=np.convolve(off,np.ones(5),mode='same')
    scores=[]
    for i in range(400,len(a)-240):
        j=i+200
        scores.append((float(a[i]*b[j]),i,j))
    if not scores: raise ValueError('Recording too short for pulse-pair search')
    _,i,j=max(scores)
    return origin+int(i)*5000,origin+int(j)*5000,dict(
        on_relative_s=i*.005,off_relative_s=j*.005,
        on_25ms_count=float(a[i]),off_25ms_count=float(b[j]),
        median_on_25ms_count=float(np.median(a)),median_off_25ms_count=float(np.median(b)),
        method='Max product of ON and OFF 25ms counts exactly1s apart; ON search starts2s after recording start; ROI rows20..105. Exploratory pair, not verified physical timing.')


def event_rows(e,centre,polarity,window_ms):
    half=int(window_ms*500)
    mask=(e['polarity']==polarity)&(abs(e['timestamp']-centre)<=half)
    background=(e['polarity']==polarity)&(e['timestamp']>=centre-500000)&(e['timestamp']<centre-100000)
    def counts(m):
        return np.bincount(e['y'][m].astype(int)*240+e['x'][m],minlength=240*180).reshape(180,240)
    raw=counts(mask); bg=counts(background)*(window_ms/400)
    contrast=np.maximum(raw-bg,0); result=[]
    for y in range(20,106):
        xs=np.flatnonzero((raw[y]>=3)&(contrast[y]>=2))
        if not len(xs): continue
        groups=np.split(xs,np.flatnonzero(np.diff(xs)>1)+1)
        groups=[g for g in groups if 1<=len(g)<=12]
        groups.sort(key=lambda g:contrast[y,g].sum(),reverse=True)
        if not groups: continue
        g=groups[0]
        if len(groups)>1 and contrast[y,groups[1]].sum()>.67*contrast[y,g].sum(): continue
        result.append([float(np.average(g,weights=contrast[y,g])),y])
    return np.array(result).reshape(-1,2),contrast


def xyz(pixels,plane,k,dist):
    if not len(pixels): return np.empty((0,3)),np.zeros(0,dtype=bool)
    xy=cv2.undistortPoints(pixels.astype(float).reshape(-1,1,2),k,dist).reshape(-1,2)
    rays=np.column_stack([xy,np.ones(len(xy))]); den=rays@np.array(plane['normal_camera'])
    scale=np.divide(-plane['offset_mm'],den,out=np.full(len(den),np.nan),where=abs(den)>1e-8)
    valid=np.isfinite(scale)&(scale>0)
    return rays[valid]*scale[valid,None],valid


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path);args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    modelpath=Path('outputs/calibration/dense_planes_ABC_20261103_01/planes.json')
    digest=hashlib.sha256(modelpath.read_bytes()).hexdigest()
    assert digest==json.loads((modelpath.parent/'frozen_model.json').read_text())['planes_sha256']
    model=json.loads(modelpath.read_text()); intr=json.loads(Path(model['intrinsics']).read_text())['models']['primary_five_coefficient']
    k=np.array(intr['camera_matrix']);dist=np.array(intr['distortion_coefficients'])
    run_map=json.loads(Path('outputs/static_checks/shoe_further2_session_20261103_01/run_map.json').read_text())
    observations=[]; allpoints=[]; comparisons=[]; examples=[]
    for plane in model['planes']:
        if 'normal_camera' not in plane:continue
        command=plane['command_us'];run=run_map.get(str(command),f'shoe_further2_{command}_20261103_01')
        raw=Path('data/raw')/(run+'.aedat4')
        trace=json.loads((Path('outputs/static_checks')/run/'summary.json').read_text())
        if trace['errors']:raise ValueError('Invalid source trace: '+run)
        e=read_events(raw);t_on,t_off,pair=pulse_pair(e)
        aps,screen,peak=detect(raw,20,40);aps=aps[(aps[:,1]>=20)&(aps[:,1]<=105)] if len(aps) else np.empty((0,2))
        apsxyz,valid=xyz(aps,plane,k,dist);aps=aps[valid]
        lookup={int(q[1]):(q,z) for q,z in zip(aps,apsxyz)}
        obs=dict(command_us=command,run_id=run,raw=str(raw),sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),
                 feedback_warning=trace['feedback_screen_warning'],pair=pair,aps_rows=len(aps),windows=[])
        for window in [20,50,100]:
            on,heat=event_rows(e,t_on,1,window);off,_=event_rows(e,t_off,0,window)
            offlookup={int(q[1]):q[0] for q in off}
            # Retain independently detected ON rows corroborated by OFF within3px.
            corroborated=np.array([q for q in on if int(q[1]) in offlookup and abs(q[0]-offlookup[int(q[1])])<=3]).reshape(-1,2)
            coords,valid=xyz(corroborated,plane,k,dist);corroborated=corroborated[valid]
            dx=[];dz=[]
            for q,z in zip(corroborated,coords):
                allpoints.append([command,window,*q,*z])
                if int(q[1]) in lookup:
                    ap,az=lookup[int(q[1])];dx.append(float(q[0]-ap[0]));dz.append(float(z[2]-az[2]))
                    comparisons.append([command,window,q[1],q[0]-ap[0],z[2]-az[2]])
            obs['windows'].append(dict(window_ms=window,on_rows=len(on),off_rows=len(off),corroborated_rows=len(coords),
                shared_aps_rows=len(dx),pixel_disagreement_rms=float(np.sqrt(np.mean(np.square(dx)))) if dx else None,
                depth_disagreement_rms_mm=float(np.sqrt(np.mean(np.square(dz)))) if dz else None))
            controls=[]
            for name,ca,cb in [('pre_dark',t_on-1000000,t_on-500000),('post_dark',t_off+1000000,t_off+1500000)]:
                da,_=event_rows(e,ca,1,window);db,_=event_rows(e,cb,0,window)
                dl={int(q[1]):q[0] for q in db}
                controls.append(dict(name=name,corroborated_rows=sum(int(q[1]) in dl and abs(q[0]-dl[int(q[1])])<=3 for q in da)))
            obs['windows'][-1]['laser_off_temporal_controls']=controls
            if window==50 and len(examples)<6:examples.append((command,peak.copy(),heat.copy(),corroborated.copy(),aps.copy()))
        observations.append(obs);print(json.dumps(dict(command=command,windows=obs['windows'])),flush=True)
    for name,header,rows in [('event_points.csv',['command_us','window_ms','pixel_x','pixel_y','X_mm','Y_mm','Z_mm'],allpoints),
                             ('paired_disagreement.csv',['command_us','window_ms','pixel_y','event_minus_APS_x_px','event_minus_APS_Z_mm'],comparisons)]:
        with (args.output/name).open('w',newline='') as f:w=csv.writer(f);w.writerow(header);w.writerows(rows)
    a=np.array(allpoints).reshape(-1,7);c=np.array(comparisons).reshape(-1,5); totals=[]
    for window in [20,50,100]:
        selected=a[a[:,1]==window];comp=c[c[:,1]==window]
        totals.append(dict(window_ms=window,points=len(selected),contributing_positions=len(set(selected[:,0])),shared_aps_rows=len(comp),
            pixel_disagreement_rms=float(np.sqrt(np.mean(comp[:,3]**2))) if len(comp) else None,
            depth_disagreement_rms_mm=float(np.sqrt(np.mean(comp[:,4]**2))) if len(comp) else None))
        totals[-1]['dark_control_candidate_rows']=sum(c['corroborated_rows'] for o in observations for w in o['windows'] if w['window_ms']==window for c in w['laser_off_temporal_controls'])
        totals[-1]['dark_control_row_opportunities']=len(observations)*86*2
    limitations=('Exploratory saved-data static event reconstruction with fixed command planes. Event/APS disagreement is NOT ground-truth accuracy. '
        'Same recordings, camera K, plane model and image rows20..105. Event extraction uses no APS spatial mask, but event settings developed on these recordings; no untouched detector test set or manual stripe labels. '
        'ON/OFF row agreement is corroboration, not confirmed laser identity. Known1s pulse pairing does not calibrate continuous timing. '
        'One acquisition per command; rows/events/windows are correlated, not independent repeats. The denominator20*86=1720 command-row opportunities is sampling support, not full-surface completeness. '
        'No independent object groundtruth, ND test, continuous sweep, latency benchmark or event advantage established. Shared calibration errors remain.')
    result=dict(status='EXPLORATORY_STATIC_EVENT_APS_COMPARISON',model=str(modelpath),model_sha256=digest,
        primary_window_ms=50,summary=totals,observations=observations,limitations=limitations,
        detector='ON/OFF polarity windows20/50/100ms centred on event-only paired25ms-rate peaks separated1s; each pixel >=3events and background-subtractedcount>=2; contiguous rowgroups1..12; strongestgroup; rejectrunnerup>.67; ON/OFF xagreement<=3px; rows20..105. No per-position threshold changes.')
    (args.output/'comparison.json').write_text(json.dumps(result,indent=2))
    fig,axes=plt.subplots(2,3,figsize=(12,7))
    for ax,(command,peak,heat,ev,ap) in zip(axes.ravel(),examples):
        ax.imshow(peak,cmap='gray',vmin=0,vmax=255)
        if len(ap):ax.scatter(ap[:,0],ap[:,1],s=9,c='cyan',label='APS')
        if len(ev):ax.scatter(ev[:,0],ev[:,1],s=11,c='orange',marker='x',label='Event ON/OFF')
        ax.set_title(f'{command} µs, event window50ms');ax.set_xlim(0,239);ax.set_ylim(105,20);ax.legend(fontsize=7)
    fig.suptitle('Same-recording stripe comparison — exploratory event candidates vs APS');fig.tight_layout();fig.savefig(args.output/'stripe_comparison.png',dpi=160);plt.close(fig)
    fig=plt.figure(figsize=(11,5));ax=fig.add_subplot(121,projection='3d');bx=fig.add_subplot(122)
    primary=a[a[:,1]==50]
    if len(primary):
        ax.scatter(primary[:,4],primary[:,6],-primary[:,5],c=primary[:,0],s=6,cmap='viridis')
        ax.set(xlabel='Camera X (mm)',ylabel='Camera Z (mm)',zlabel='−Camera Y (mm)',title='Static event candidate point cloud')
        ax.view_init(elev=24,azim=-62)
    for window in [20,50,100]:
        rows=[(o['command_us'],next(w for w in o['windows'] if w['window_ms']==window)['corroborated_rows']) for o in observations]
        bx.plot([r[0] for r in rows],[r[1] for r in rows],marker='.',label=f'{window}ms')
    bx.set(xlabel='Servo command (µs)',ylabel='Retained image rows',title='Event-window sensitivity');bx.legend()
    fig.suptitle('Static event reconstruction; no independent object accuracy');fig.tight_layout();fig.savefig(args.output/'event_reconstruction.png',dpi=160);plt.close(fig)
    lines=['# Exploratory static event / APS comparison','',limitations,'',result['detector'],'','| Window (ms) | Event points | Positions | Shared APS rows | x disagreement RMS (px) | Z disagreement RMS (mm) |','|---|---|---|---|---|---|']
    for t in totals:lines.append('| '+' | '.join(str(t[k]) for k in ['window_ms','points','contributing_positions','shared_aps_rows','pixel_disagreement_rms','depth_disagreement_rms_mm'])+' |')
    (args.output/'REVIEW.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(dict(output=str(args.output),summary=totals)),flush=True)


if __name__=='__main__':main()
