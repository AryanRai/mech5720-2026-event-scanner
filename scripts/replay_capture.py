"""Replay event windows in sensor time; space pauses and n advances one window."""
import argparse,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2,numpy as np,dv_processing as dv
from event_camera.playback import WindowSlicer


def main():
 p=argparse.ArgumentParser(description=__doc__); p.add_argument('recording'); p.add_argument('--speed',type=float,default=1,help='0 = as fast as possible'); p.add_argument('--window-us',type=int,default=10000); p.add_argument('--no-display',action='store_true'); a=p.parse_args()
 if a.speed<0 or a.window_us<=0: p.error('invalid speed or window')
 try:
  r=dv.io.MonoCameraRecording(a.recording); w,h=r.getEventResolution(); slicer=WindowSlicer(a.window_us); total=0; previous=None; paused=False
  def windows():
   while True:
    batch=r.getNextEventBatch()
    if batch is None: break
    yield from slicer.push(batch.numpy())
   yield from slicer.flush()
  for t,events in windows():
   if a.speed and previous is not None:
    delay=(t-previous)/1e6/a.speed
    # Allow the GUI to process quit and pause during long gaps.
    while delay>0:
     part=min(delay,.02); delay-=part
     if a.no_display: time.sleep(part)
     else:
      key=cv2.waitKey(max(1,int(part*1000)))&255
      if key in (27,ord('q')): return 0
      if key==32: paused=not paused
      while paused:
       key=cv2.waitKey(30)&255
       if key in (27,ord('q')): return 0
       if key==32: paused=False
       if key==ord('n'): delay=0; break
   previous=t; total+=len(events)
   if not a.no_display:
    image=np.zeros((h,w,3),np.uint8); pos=events['polarity']!=0
    image[events['y'][~pos],events['x'][~pos],0]=255; image[events['y'][pos],events['x'][pos],2]=255
    cv2.imshow('Replay: space pause, n step, q quit',cv2.resize(image,None,fx=3,fy=3,interpolation=cv2.INTER_NEAREST))
    key=cv2.waitKey(1)&255
    if key in (27,ord('q')): return 0
    if key==32: paused=not paused
    while paused:
     key=cv2.waitKey(30)&255
     if key in (27,ord('q')): return 0
     if key==32: paused=False
     if key==ord('n'): break
  print(f'Replayed {total} events; stream: {r.getCameraName()}'); return 0
 except Exception as e: print(f'Replay error: {type(e).__name__}: {e}',file=sys.stderr); return 1
 finally: cv2.destroyAllWindows()
if __name__=='__main__': sys.exit(main())
