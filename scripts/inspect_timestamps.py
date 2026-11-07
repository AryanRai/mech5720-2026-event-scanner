"""Inspect recording stream timestamps and flag suspicious jumps; no correction applied."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import dv_processing as dv
from event_camera.timestamps import assess_timestamps

def main():
 p=argparse.ArgumentParser(description=__doc__); p.add_argument('recording'); a=p.parse_args()
 try:
  r=dv.io.MonoCameraRecording(a.recording); streams={}
  if r.isEventStreamAvailable():
   n=0; first=last=None; backward=0
   while True:
    b=r.getNextEventBatch()
    if b is None: break
    if len(b):
     lo,hi=b.getLowestTime(),b.getHighestTime(); backward+=int(last is not None and lo<last); first=lo if first is None else first; last=hi; n+=len(b)
   streams['events']={'count':n,'first_us':first,'last_us':last,'backward_batches':backward}
  if r.isFrameStreamAvailable():
   ts=[]
   while True:
    f=r.getNextFrame()
    if f is None: break
    ts.append(int(f.timestamp))
   streams['frames']={'count':len(ts),'first_us':ts[0] if ts else None,'last_us':ts[-1] if ts else None,'first_timestamps_us':ts[:5],'backward':sum(y<x for x,y in zip(ts,ts[1:])),'jumps_over_10s':sum(abs(y-x)>10000000 for x,y in zip(ts,ts[1:]))}
  if r.isImuStreamAvailable():
   n=0; first=last=None; backward=0
   while True:
    b=r.getNextImuBatch()
    if b is None: break
    for item in b:
     t=int(item.timestamp); backward+=int(last is not None and t<last); first=t if first is None else first; last=t; n+=1
   streams['imu']={'count':n,'first_us':first,'last_us':last,'backward':backward}
  assessment=assess_timestamps(streams); print(json.dumps({'streams':streams,'assessment':assessment},indent=2)); return 1 if assessment['status']=='FAIL' else 0
 except Exception as e: print(f'Timestamp inspection error: {type(e).__name__}: {e}',file=sys.stderr); return 1
if __name__=='__main__': sys.exit(main())
