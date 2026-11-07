"""Offline optical edge timing audit; requires no hardware access."""
import json
from pathlib import Path
import cv2
import dv_processing as dv
import numpy as np


def audit(raw, operation, x_bounds=(120, 235)):
    reader = dv.io.MonoCameraRecording(str(raw))
    frames, times = [], []
    while True:
        frame = reader.getNextFrame()
        if frame is None: break
        frames.append(frame.image.copy()); times.append(int(frame.timestamp))
    images = np.stack(frames).astype(float)
    reference = np.median(images[:3], axis=0)
    difference = images-reference
    # Background upper image avoids foreground occlusion; chosen for this audit.
    region = np.zeros(reference.shape, np.uint8); region[:90, x_bounds[0]:x_bounds[1]] = 1
    mask = ((difference.max(axis=0)>60) & (region>0)).astype(np.uint8)
    if mask.sum()<20: raise ValueError('Insufficient optical marker pixels')
    mask = cv2.dilate(mask, np.ones((5,5),np.uint8))>0
    signal = np.maximum(difference[:,mask], 0).sum(axis=1)
    lit = np.flatnonzero(signal>signal.max()*.5)
    if not len(lit): raise ValueError('No APS marker')
    reader = dv.io.MonoCameraRecording(str(raw)); batches=[]
    while True:
        batch=reader.getNextEventBatch()
        if batch is None: break
        array=batch.numpy(); batches.append(array[mask[array['y'],array['x']]])
    events=np.concatenate(batches)
    edges=[]
    for name, polarity, centre in [('LASER_ON',True,times[lit[0]]),('LASER_OFF',False,times[min(lit[-1]+1,len(times)-1)])]:
        selected=events[(events['polarity']==polarity)&(abs(events['timestamp']-centre)<150000)]
        if len(selected)<20: raise ValueError('Insufficient transition events')
        ts=selected['timestamp']; origin=int(ts.min()); bins=((ts-origin)//1000).astype(int)
        counts=np.bincount(bins); peak=int(counts.argmax()); peak_time=origin+peak*1000
        burst=ts[(ts>=peak_time-5000)&(ts<peak_time+10000)]
        quantiles=np.percentile(burst,[10,50,90])
        lines=operation['result']['lines']
        controller=[int(line.split(',')[1]) for line in lines if line.startswith('E,') and line.split(',')[2]==name]
        if len(controller)!=1: raise ValueError('Ambiguous controller marker')
        edges.append(dict(name=name,controller_tick_us=controller[0],camera_event_median_us=float(quantiles[1]),
                          event_p10_p90_us=quantiles[[0,2]].tolist(),burst_events=len(burst),peak_1ms_count=int(counts[peak])))
    controller_duration=(edges[1]['controller_tick_us']-edges[0]['controller_tick_us'])%2**32
    camera_duration=edges[1]['camera_event_median_us']-edges[0]['camera_event_median_us']
    return dict(raw=str(raw),edges=edges,controller_duration_us=controller_duration,camera_duration_us=camera_duration,
                duration_difference_us=camera_duration-controller_duration,mask_pixels=int(mask.sum()))


def main():
    pairs=[('p3_poseB_board_20261102_02','p3_poseB_20261102_02'),
           ('p3_poseC_board_20261102_02','p3_poseC_20261102_02'),
           ('p3_poseC_board_20261102_03','p3_poseC_20261102_03'),
           ('holder1500_section_20261102_01','holder1500_observe_20261102_01'),
           ('object_swap_stripe_20261103_01','object_swap_observe_20261103_01')]
    out=Path('outputs/timing/optical_edge_audit_20261103_01'); out.mkdir(parents=True,exist_ok=False)
    results=[]
    for raw, run in pairs:
        try:
            op=json.loads((Path('outputs/static_checks')/run/'operation.json').read_text())
            results.append(audit(Path('data/raw')/(raw+'.aedat4'),op))
        except Exception as exc: results.append(dict(raw=raw,error=str(exc)))
    valid=[r for r in results[:4] if 'error' not in r]
    fit=None
    if len(valid)>=3:
        # Previous session only; latest recording follows an Uno reset.
        ticks=np.array([r['edges'][0]['controller_tick_us'] for r in valid],float)
        ticks=np.unwrap(ticks/(2**32)*2*np.pi)/(2*np.pi)*2**32
        camera=np.array([r['edges'][0]['camera_event_median_us'] for r in valid])
        slope=(camera[1]-camera[0])/(ticks[1]-ticks[0])
        residuals=[]
        for i,r in enumerate(valid):
            for e in r['edges']:
                tick=ticks[i]+((e['controller_tick_us']-r['edges'][0]['controller_tick_us'])%2**32)
                predicted=camera[0]+slope*(tick-ticks[0])
                residuals.append(dict(raw=r['raw'],edge=e['name'],used_for_fit=i<2 and e['name']=='LASER_ON',
                                      residual_us=float(e['camera_event_median_us']-predicted)))
        fit=dict(camera_us_per_controller_us=float(slope),rate_difference_ppm=float((slope-1)*1e6),residuals=residuals,
                 valid_session='Historical uninterrupted controller session only; invalid after reset',
                 method='Fit ON markers of first two observations; other markers reserved for diagnostic prediction.')
    result=dict(observations=results,historical_affine_check=fit,
                limitations='Exploratory post-selected ROI and event burst median. P10-P90 is event spread, not confidence interval or absolute edge uncertainty. Optical ON/OFF has polarity/threshold/laser response delay. No independent oscilloscope, continuous-angle plane calibration or validated sweep reconstruction. Clock reset invalidates historical offset. Newly reset session has only one pulse, insufficient drift verification.')
    (out/'audit.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))


if __name__=='__main__': main()
