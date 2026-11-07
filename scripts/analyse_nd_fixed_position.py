"""Fixed-position unknown-ND comparison; camera signal ratio, not optical T."""
import argparse
import hashlib
import json
from pathlib import Path
import cv2
import dv_processing as dv
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scripts.reconstruct_sparse_shoe import detect
from scripts.compare_static_events_aps import read_events,pulse_pair,event_rows


def frames(raw):
    reader=dv.io.MonoCameraRecording(str(raw));images=[];times=[]
    while True:
        f=reader.getNextFrame()
        if f is None:break
        images.append(f.image.copy());times.append(int(f.timestamp))
    return np.stack(images),np.array(times)


def stable_reference_diagnostic(images,reference,selected):
    """Separate post-pilot diagnostic; keeps legacy spatial thresholds unchanged."""
    byrow={}
    for index in selected:
        delta=images[index].astype(float)-reference
        for y in range(20,106):
            xs=np.flatnonzero((delta[y]>20)&(images[index,y]>40))
            if not len(xs):continue
            groups=np.split(xs,np.flatnonzero(np.diff(xs)>1)+1)
            groups=[g for g in groups if 1<=len(g)<=12]
            groups.sort(key=lambda g:float(delta[y,g].sum()),reverse=True)
            if not groups:continue
            g=groups[0]
            if len(groups)>1 and delta[y,groups[1]].sum()>.67*delta[y,g].sum():continue
            if np.any(images[index,y,g]>=250):continue
            byrow.setdefault(y,[]).append(float(np.average(g,weights=delta[y,g])))
    return np.array([[float(np.median(v)),y] for y,v in sorted(byrow.items()) if len(v)>=len(selected)/2]).reshape(-1,2)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--filtered',nargs='+',required=True);p.add_argument('--baseline',nargs='+');p.add_argument('--control',nargs='*',default=[]);p.add_argument('--output',type=Path,required=True);args=p.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    baseline=args.baseline or [f'shoe_repeat_r{i}_1626_20261103_02' for i in [1,2,3]]
    # Frozen spatial integration mask from first no-filter record, not ND output.
    pixels,_,_=detect(Path('data/raw')/(baseline[0]+'.aedat4'),20,40)
    pixels=pixels[(pixels[:,1]>=20)&(pixels[:,1]<=105)]
    mask=np.zeros((180,240),bool)
    for x,y in pixels:
        mask[int(y),max(0,int(round(x))-6):min(240,int(round(x))+7)]=True
    results=[];traces=[];peaks=[];pixelsets=[]
    for condition,runs in [('no_filter',baseline),('unknown_ND',args.filtered),('filter_removed_control',args.control)]:
        for run in runs:
            raw=Path('data/raw')/(run+'.aedat4');images,t=frames(raw);relative=(t-t[0])/1e6
            tracepath=Path('outputs/static_checks')/run/'summary.json';trace=json.loads(tracepath.read_text())
            if trace['errors']:raise ValueError('Invalid trace '+run)
            ref=np.median(images[relative<1.5],axis=0);delta=images.astype(float)-ref
            signal=delta[:,mask].mean(axis=1)
            # Fixed0.5s moving average, search2..8s, avoids a single noisy frame.
            dt=float(np.median(np.diff(relative)));width=max(1,round(.5/dt));smooth=np.convolve(signal,np.ones(width)/width,mode='same')
            candidates=np.flatnonzero((relative>=2)&(relative<=8));peak=int(candidates[np.argmax(smooth[candidates])])
            dark=signal[relative<2];amplitude=float(smooth[peak]-np.median(dark));noise=float(np.std(dark,ddof=1))
            supported=amplitude>max(2,5*noise)
            selected=np.flatnonzero(abs(relative-relative[peak])<=.25)
            lit=np.median(images[selected],axis=0)
            try:aps,screen,_=detect(raw,20,40)
            except ValueError as exc:aps=np.empty((0,2));screen={'failure':str(exc)}
            aps=aps[(aps[:,1]>=20)&(aps[:,1]<=105)] if len(aps) else np.empty((0,2))
            e=read_events(raw);on,off,pair=pulse_pair(e);a,_=event_rows(e,on,1,50);b,_=event_rows(e,off,0,50);bl={int(q[1]):q[0] for q in b}
            ev=np.array([q for q in a if int(q[1]) in bl and abs(q[0]-bl[int(q[1])])<=3]).reshape(-1,2)
            # A background burst can satisfy duration pairing. Do not call it a stripe
            # if independent APS fixed-mask light increase is not supported.
            entry=dict(run_id=run,condition=condition,raw_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),
                fixed_mask_amplitude_levels=amplitude,dark_frame_signal_sd_levels=noise,light_increase_screen=supported,
                selected_peak_relative_s=float(relative[peak]),selected_frame_count=len(selected),
                bright_clipping_fraction_in_mask=float((images[selected][:,mask]>=250).mean()),
                aps_candidate_rows=len(aps),event_corroborated_candidate_rows=len(ev),event_pair=pair,
                event_identity_unvalidated=not supported,aps_screen=screen,feedback_warning=trace['feedback_screen_warning'])
            diagnostics=stable_reference_diagnostic(images,ref,selected) if supported else np.empty((0,2))
            entry['post_pilot_APS_diagnostic']=dict(retained_rows=len(diagnostics),pixels=diagnostics.tolist(),
                first3_vs_first1p5s_reference_mean_difference=float(np.mean(np.median(images[:3],axis=0)-ref)),
                method='Post-pilot diagnostic: median first1.5s reference; same delta20/intensity40/spatial screens; frames within0.25s of fixed-mask0.5s-mean peak. Not frozen primary detector or independent validation.')
            entry['event_window_sensitivity']=[]
            for window in [20,50,100]:
                va,_=event_rows(e,on,1,window);vb,_=event_rows(e,off,0,window);vl={int(q[1]):q[0] for q in vb}
                count=sum(int(q[1]) in vl and abs(q[0]-vl[int(q[1])])<=3 for q in va)
                entry['event_window_sensitivity'].append(dict(window_ms=window,candidate_rows=int(count)))
            results.append(entry);traces.append((condition,run,relative,signal));peaks.append((condition,run,lit,ref));pixelsets.append((condition,run,aps,ev))
    no=[r for r in results if r['condition']=='no_filter'];nd=[r for r in results if r['condition']=='unknown_ND'];reference=float(np.mean([r['fixed_mask_amplitude_levels'] for r in no]))
    for r in nd:r['relative_camera_signal_vs_historical_unfiltered_mean']=r['fixed_mask_amplitude_levels']/reference if reference else None
    controls=[r for r in results if r['condition']=='filter_removed_control']
    condition_summary=[]
    for condition,rows in [('no_filter',no),('unknown_ND',nd),('filter_removed_control',controls)]:
        if not rows:continue
        values=np.array([r['fixed_mask_amplitude_levels'] for r in rows])
        condition_summary.append(dict(condition=condition,independent_acquisitions=len(values),
            mean_camera_signal_levels=float(values.mean()),sample_sd_camera_signal_levels=float(values.std(ddof=1)) if len(values)>1 else None,
            relative_mean_camera_signal=float(values.mean()/reference),primary_APS_rows_each=[r['aps_candidate_rows'] for r in rows],
            primary_event_rows_each=[r['event_corroborated_candidate_rows'] for r in rows]))
    shifts=[]
    baseline_lookup={int(q[1]):q[0] for q in pixelsets[0][2]}
    for condition,run,aps,ev in pixelsets:
        if condition=='no_filter':continue
        dx=[float(q[0]-baseline_lookup[int(q[1])]) for q in aps if int(q[1]) in baseline_lookup]
        shifts.append(dict(run_id=run,shared_aps_rows=len(dx),median_x_shift_px=float(np.median(dx)) if dx else None,
            x_shift_rms_px=float(np.sqrt(np.mean(np.square(dx)))) if dx else None))
    diagnostic_baseline={int(q[1]):q[0] for q in no[0]['post_pilot_APS_diagnostic']['pixels']}
    changed=[r for r in results if r['condition']!='no_filter']
    for row,entry in zip(shifts,changed):
        dx=[q[0]-diagnostic_baseline[int(q[1])] for q in entry['post_pilot_APS_diagnostic']['pixels'] if int(q[1]) in diagnostic_baseline]
        row['post_pilot_diagnostic_shared_rows']=len(dx)
        row['post_pilot_diagnostic_median_x_shift_px']=float(np.median(dx)) if dx else None
        row['post_pilot_diagnostic_x_shift_rms_px']=float(np.sqrt(np.mean(np.square(dx)))) if dx else None
        row['interpretation']='Apparent pixel change under separate diagnostic, not an independent optical-plane shift calibration'
    spatial_confounded=any(abs(q.get('median_x_shift_px') or q.get('post_pilot_diagnostic_median_x_shift_px') or 0)>1 for q in shifts)
    limits=('Unknown ND marking, one physical filter configuration at fixed1626us, manual35ms APS. '
        'Ratio is background-subtracted digital camera stripe signal in a fixed unfiltered-derived mask, NOT calibrated optical transmittance or ND density. '
        'APS linearity/response unverified; historical no-filter baseline not interleaved; scene/light/laser drift and filter-induced beam displacement confound ratio. '
        'Broad fixedROI includes background/target crossings; candidate rows are not labelled true detections or surface completeness. '
        'Event-only known1s ON/OFF pairing may pick background if stripe weak; independent light-increase flag reported. '
        'No moving scan, no independent depth accuracy, no weakest-level threshold and no multi-level attenuation curve. No plane recalibration or reconstruction correctness assumed after adding filter.')
    ratios={}
    if controls:
        after_mean=float(np.mean([r['fixed_mask_amplitude_levels'] for r in controls]));nd_mean=float(np.mean([r['fixed_mask_amplitude_levels'] for r in nd]))
        ratios=dict(ND_camera_signal_vs_filter_removed_mean=nd_mean/after_mean,ND_camera_signal_vs_bracketing_mean=nd_mean/((reference+after_mean)/2),filter_removed_vs_historical_mean=after_mean/reference,
            valid_as_attenuation_estimate=False,
            interpretation='Diagnostic digital signal in the OLD spatial mask only. Geometry changed, so these ratios are invalid as attenuation/transmittance estimates. Historical baseline and camera-response confounds also remain.')
    result=dict(status='UNKNOWN_FILTER_FIXED_POSITION_REPEATS' if len(nd)>1 else 'UNKNOWN_FILTER_FIXED_POSITION_PILOT',command_us=1626,exposure_us=35000,
        baseline_runs=baseline,filtered_runs=args.filtered,control_runs=args.control,mask_pixels=int(mask.sum()),condition_summary=condition_summary,control_ratios=ratios,results=results,spatial_change=shifts,
        spatially_confounded=spatial_confounded,valid_attenuation_performance_comparison=False,limitations=limits)
    (args.output/'comparison.json').write_text(json.dumps(result,indent=2))
    cv2.imwrite(str(args.output/'fixed_measurement_mask.png'),mask.astype(np.uint8)*255)
    fig,ax=plt.subplots(figsize=(10,4))
    for condition,run,relative,signal in traces:ax.plot(relative,signal,label=run,alpha=.7)
    ax.set(xlabel='Camera recording elapsed time (s)',ylabel='Mean signed stripe-mask change (digital levels)',title='Same exposure / position: unknown filter versus earlier unfiltered recordings');ax.legend(fontsize=6);ax.grid(alpha=.2);fig.tight_layout();fig.savefig(args.output/'signal_traces.png',dpi=170);plt.close(fig)
    shown=[peaks[0],peaks[len(baseline)]]
    if controls:shown.append(peaks[len(baseline)+len(nd)])
    fig,axes=plt.subplots(len(shown),2,figsize=(8,3*len(shown)))
    for i,(condition,run,lit,ref) in enumerate(shown):
        axes[i,0].imshow(lit,cmap='gray',vmin=0,vmax=255);axes[i,0].set_title(condition+' selected median APS')
        axes[i,1].imshow(lit-ref,cmap='coolwarm',vmin=-50,vmax=50);axes[i,1].set_title('Signed change versus dark reference')
        for ax in axes[i]:ax.axis('off')
    fig.suptitle('Fixed1626µs /35ms; filter strength unknown');fig.tight_layout();fig.savefig(args.output/'filter_comparison.png',dpi=170);plt.close(fig)
    lines=['# Unknown ND fixed-position pilot','',limits,'','| Condition | Run | Mask signal (levels) | Relative camera signal | Light increase supported | APS rows | Event candidate rows |','|---|---|---|---|---|---|---|']
    for r in results:lines.append(f"| {r['condition']} | {r['run_id']} | {r['fixed_mask_amplitude_levels']:.3f} | {r.get('relative_camera_signal_vs_historical_unfiltered_mean','reference')} | {r['light_increase_screen']} | {r['aps_candidate_rows']} | {r['event_corroborated_candidate_rows']} |")
    lines+=['','Condition summaries:',json.dumps(condition_summary,indent=2),'',
        'Post-pilot diagnostic APS extraction uses a longer initial dark reference and fixed-mask pulse selection, with unchanged spatial thresholds. It is reported separately and does not replace the frozen primary results. See comparison.json for coordinates, temporal-window sensitivity and reference differences.']
    lines+=['','## Interpretation','',
        'The filter insertion/removal sequence is spatially confounded. The signal ratios are diagnostic measurements in an old spatial mask, NOT valid attenuation estimates. The filter-removed stripe did not restore its historical position. No filter transmission, weakest usable illumination, calibrated ND curve, event advantage or ND depth accuracy is established. Do not reconstruct new points with the old command-plane mapping without rechecking geometry. Prior saved calibration/reconstruction evidence is retained unchanged.']
    (args.output/'REVIEW.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(dict(results=results,spatial_change=shifts),indent=2))


if __name__=='__main__':main()
