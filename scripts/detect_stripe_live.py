"""Show raw events, filtered events, and candidate stripe fit live."""
import argparse,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2,numpy as np
from event_camera.camera import open_davis,require_stream
from event_camera.config import Config
from event_camera.filters import EventFilter
from event_camera.playback import WindowSlicer
from event_camera.stripe_detector import detect_stripe


def main():
 p=argparse.ArgumentParser(description=__doc__); p.add_argument('--window-us',type=int,default=10000); p.add_argument('--duration',type=float); p.add_argument('--no-display',action='store_true'); p.add_argument('--serial'); a=p.parse_args()
 if a.window_us<=0 or (a.duration is not None and a.duration<=0): p.error('window/duration must be positive')
 try:
  config=Config(window_us=a.window_us); print('Compiling filter before camera acquisition...',flush=True); filt=EventFilter(240,180,config); filt.warmup(); c=open_davis(a.serial); require_stream(c,'Event'); w,h=c.getEventResolution();
  if (w,h)!=(240,180): raise RuntimeError(f'Unexpected event resolution: {w}x{h}')
  print('Configuration:',config.as_dict()); slicer=WindowSlicer(config.window_us); start=time.monotonic(); total=0; detections=0
  while a.duration is None or time.monotonic()-start<a.duration:
   if not c.isRunning(): raise RuntimeError('Camera stopped or disconnected')
   batch=c.getNextEventBatch()
   if batch is not None:
    for t,raw in slicer.push(batch.numpy()):
     filtered=filt.apply(raw); o=detect_stripe(filtered,w,h,config); total+=len(raw); detections+=o is not None
     if not a.no_display:
      img=np.zeros((h,w*2,3),np.uint8); img[raw['y'],raw['x']]=100
      if len(filtered): img[filtered['y'],filtered['x']+w]=255
      if o:
       aa,bb,cc=o.line_parameters
       if abs(aa)>1e-8: cv2.line(img,(int(w-cc/aa),0),(int(w-(cc+bb*(h-1))/aa),h-1),(0,0,255),1)
      img=cv2.resize(img,None,fx=2,fy=2,interpolation=cv2.INTER_NEAREST)
      cv2.putText(img,f'raw {len(raw)} filtered {len(filtered)} confidence {o.confidence if o else 0:.2f}',(5,20),cv2.FONT_HERSHEY_SIMPLEX,.5,(0,255,0),1)
      cv2.imshow('Stripe candidate: raw | filtered',img)
   if not a.no_display and (cv2.waitKey(1)&255) in (27,ord('q')): break
   time.sleep(.001)
  print(f'Processed {total} events; candidate detections {detections}; clean exit'); return 0
 except KeyboardInterrupt: print('Stopped by user'); return 0
 except Exception as e: print(f'Stripe viewer error: {type(e).__name__}: {e}',file=sys.stderr); return 1
 finally: cv2.destroyAllWindows()
if __name__=='__main__': sys.exit(main())
