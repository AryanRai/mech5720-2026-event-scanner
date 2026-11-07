"""Run shared filters and stripe fitting on an AEDAT4 recording."""
import argparse,csv,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2,numpy as np,dv_processing as dv
from event_camera.config import Config
from event_camera.filters import EventFilter
from event_camera.stripe_detector import detect_stripe
from event_camera.playback import WindowSlicer


def main():
 p=argparse.ArgumentParser(description=__doc__); p.add_argument('recording'); p.add_argument('--window-us',type=int,default=10000); p.add_argument('--polarity',choices=['both','positive','negative'],default='both'); p.add_argument('--refractory-us',type=int,default=1000); p.add_argument('--support-radius',type=int,default=1); p.add_argument('--support-us',type=int,default=10000); p.add_argument('--minimum-support',type=int,default=1); p.add_argument('--line-threshold',type=float,default=2.5); p.add_argument('--minimum-inliers',type=int,default=20); p.add_argument('--save-images',action='store_true'); a=p.parse_args()
 if min(a.window_us,a.line_threshold,a.minimum_inliers)<=0 or min(a.refractory_us,a.support_radius,a.support_us,a.minimum_support)<0: p.error('Invalid filter parameters')
 c=Config(a.window_us,a.polarity,a.refractory_us,a.support_radius,a.support_us,a.minimum_support,a.line_threshold,a.minimum_inliers)
 try:
  reader=dv.io.MonoCameraRecording(a.recording); w,h=reader.getEventResolution(); filt=EventFilter(w,h,c); slicer=WindowSlicer(c.window_us); rows=[]; obs=[]
  out=Path(__file__).resolve().parents[1]/'outputs'/'analysis'/Path(a.recording).stem; out.mkdir(parents=True,exist_ok=True)
  def process(t,raw):
   filtered=filt.apply(raw); o=detect_stripe(filtered,w,h,c); positive=int(np.count_nonzero(raw['polarity'])); rows.append({'timestamp_us':t,'raw':len(raw),'positive':positive,'negative':len(raw)-positive,'filtered':len(filtered),'inliers':o.inlier_count if o else 0,'residual_px':o.residual_px if o else None,'confidence':o.confidence if o else 0})
   if o: obs.append(o.as_dict())
   if a.save_images:
    img=np.zeros((h,w*2,3),np.uint8); img[raw['y'],raw['x'],:]=90
    if len(filtered): img[filtered['y'],filtered['x']+w,:]=255
    if o:
     aa,bb,cc=o.line_parameters
     if abs(aa)>1e-8:
      p1=(int(w-cc/aa),0); p2=(int(w-(cc+bb*(h-1))/aa),h-1); cv2.line(img,p1,p2,(0,0,255),1)
    cv2.imwrite(str(out/f'{t}.png'),img)
  while True:
   batch=reader.getNextEventBatch()
   if batch is None: break
   for t,e in slicer.push(batch.numpy()): process(t,e)
  for t,e in slicer.flush(): process(t,e)
  if not rows: raise RuntimeError('No events in recording')
  with (out/'windows.csv').open('w',newline='',encoding='utf-8') as f:
   writer=csv.DictWriter(f,fieldnames=rows[0].keys()); writer.writeheader(); writer.writerows(rows)
  (out/'stripe_observations.json').write_text(json.dumps(obs,indent=2),encoding='utf-8')
  raw=sum(r['raw'] for r in rows); filtered=sum(r['filtered'] for r in rows); inliers=sum(r['inliers'] for r in rows); span=(rows[-1]['timestamp_us']-rows[0]['timestamp_us']+c.window_us)/1e6
  total_windows=int(round(span*1e6/c.window_us)); summary={'configuration':c.as_dict(),'total_events':raw,'duration_event_span_s':span,'mean_rate_events_s':raw/span,'peak_window_rate_events_s':max(r['raw'] for r in rows)*1e6/c.window_us,'filter_retention_percent':100*filtered/raw,'windows_with_detection_percent':100*len(obs)/total_windows,'nonempty_windows':len(rows),'total_windows_in_span':total_windows,'positive_events':sum(r['positive'] for r in rows),'negative_events':sum(r['negative'] for r in rows),'mean_detected_residual_px':float(np.mean([o['residual_px'] for o in obs])) if obs else None,'candidate_inliers':inliers,'non_inlier_events':raw-inliers,'note':'Inliers are detector candidates, not ground-truth signal; background rate and signal/background ratio require labelled or laser-off reference. Detection percentage includes empty windows across the observed event span; event-span rate is not wall-clock recording rate.'}
  (out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
  import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
  x=np.array([(r['timestamp_us']-rows[0]['timestamp_us'])/1e6 for r in rows]); fig,axes=plt.subplots(4,1,figsize=(10,10),sharex=True)
  axes[0].plot(x,[r['raw']*1e6/c.window_us for r in rows]); axes[0].set_ylabel('events/s')
  axes[1].plot(x,[r['positive'] for r in rows],label='ON'); axes[1].plot(x,[r['negative'] for r in rows],label='OFF'); axes[1].legend(); axes[1].set_ylabel('count')
  axes[2].plot(x,[r['raw'] for r in rows],label='raw'); axes[2].plot(x,[r['filtered'] for r in rows],label='filtered'); axes[2].legend(); axes[2].set_ylabel('count')
  axes[3].plot(x,[r['residual_px'] if r['residual_px'] is not None else np.nan for r in rows],label='residual px'); axes[3].plot(x,[r['confidence'] for r in rows],label='confidence'); axes[3].legend(); axes[3].set_xlabel('Event time (s)'); fig.tight_layout(); fig.savefig(out/'diagnostics.png',dpi=150); plt.close(fig)
  print(json.dumps(summary,indent=2)); print(f'Output: {out}'); return 0
 except Exception as e: print(f'Analysis error ({type(e).__name__}): {e}',file=sys.stderr); return 1
if __name__=='__main__': sys.exit(main())
