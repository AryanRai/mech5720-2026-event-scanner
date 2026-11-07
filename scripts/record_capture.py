"""Record available DAVIS streams to AEDAT4 and a metadata sidecar."""
import argparse,json,sys,time
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import dv_processing as dv
from event_camera.camera import open_davis
from event_camera.timestamps import assess_timestamps


def main():
 p=argparse.ArgumentParser(description=__doc__); p.add_argument('name'); p.add_argument('--duration',type=float,default=10); p.add_argument('--serial'); p.add_argument('--notes',default=''); a=p.parse_args()
 if a.duration<=0 or Path(a.name).name!=a.name or not a.name: p.error('Use a positive duration and simple recording name')
 root=Path(__file__).resolve().parents[1]; folder=root/'data/raw'; folder.mkdir(parents=True,exist_ok=True); path=folder/(a.name+'.aedat4'); meta=folder/(a.name+'.json')
 if path.exists() or meta.exists(): print('Recording already exists; choose a new name',file=sys.stderr); return 1
 warmup={'events':0,'frames':0,'imu':0,'uninitialized_frame_timestamps':[]}; frame_times=[]; event_first=None; event_last=None; imu_first=None; imu_last=None; event_backward=0; imu_backward=0; writer=None; counts={'events':0,'event_batches':0,'frames':0,'imu':0}; start=None; error=None; interrupted=False
 try:
  c=open_davis(a.serial); name=c.getCameraName(); resolution=c.getEventResolution(); streams={'events':c.isEventStreamAvailable(),'frames':c.isFrameStreamAvailable(),'imu':c.isImuStreamAvailable()}
  if not streams['events']: raise RuntimeError('Event stream unavailable')
  # Drain startup data until two consecutive APS timestamps reflect the API offset.
  # These samples precede the requested recording interval and are counted explicitly.
  deadline=time.monotonic()+5; valid_frames=0
  while streams['frames'] and valid_frames<2 and time.monotonic()<deadline:
   if not c.isRunning(): raise RuntimeError('Camera stopped during timestamp startup')
   e=c.getNextEventBatch()
   if e is not None: warmup['events']+=len(e)
   b=c.getNextImuBatch() if streams['imu'] else None
   if b: warmup['imu']+=len(b)
   f=c.getNextFrame()
   if f is not None:
    warmup['frames']+=1; offset=int(c.getTimestampOffset().total_seconds()*1000000)
    if offset>0 and f.timestamp>=offset: valid_frames+=1
    else: valid_frames=0; warmup['uninitialized_frame_timestamps'].append(int(f.timestamp))
   time.sleep(.001)
  if streams['frames'] and valid_frames<2: raise RuntimeError('APS timestamps did not initialize within 5 seconds; recording not started')
  print(f'Startup samples discarded before recording: {warmup}',flush=True)
  writer=dv.io.MonoCameraWriter(str(path),c); start=time.monotonic(); created=datetime.now(timezone.utc).isoformat()
  while time.monotonic()-start<a.duration:
   if not c.isRunning(): raise RuntimeError('Camera stopped or disconnected')
   e=c.getNextEventBatch()
   if e is not None and len(e):
    if event_first is None: event_first=e.getLowestTime()
    if event_last is not None and e.getLowestTime()<event_last: event_backward+=1
    event_last=e.getHighestTime()
    writer.writeEvents(e); counts['events']+=len(e); counts['event_batches']+=1
   if streams['frames']:
    f=c.getNextFrame()
    if f is not None:
     offset=int(c.getTimestampOffset().total_seconds()*1000000)
     if offset>0 and f.timestamp<offset: raise RuntimeError(f'Uninitialized APS timestamp during recording: {f.timestamp}, offset {offset}')
     if frame_times and (f.timestamp<frame_times[-1] or f.timestamp-frame_times[-1]>10000000): raise RuntimeError(f'Unexpected APS timestamp jump: {frame_times[-1]} to {f.timestamp}')
     writer.writeFrame(f); counts['frames']+=1; frame_times.append(f.timestamp)
   if streams['imu']:
    batch=c.getNextImuBatch()
    if batch:
     if imu_first is None: imu_first=batch[0].timestamp
     for sample in batch:
      if imu_last is not None and sample.timestamp<imu_last: imu_backward+=1
      imu_last=sample.timestamp
      writer.writeImu(sample)
     counts['imu']+=len(batch)
   time.sleep(.001)
 except KeyboardInterrupt: interrupted=True; print('Stopped by user')
 except Exception as exc: error=f'{type(exc).__name__}: {exc}'; print(f'Recording error: {error}',file=sys.stderr)
 finally:
  if start is not None:
   elapsed=time.monotonic()-start; del writer
   data={'recording_name':a.name,'date_time_utc':created,'camera_name':name,'serial':c.getDeviceDescriptor().serialNumber,'event_resolution':resolution,'duration_s':elapsed,'counts':counts,'mean_event_rate':counts['events']/elapsed,'streams':streams,'notes':a.notes,'requested_duration_s':a.duration,'startup_discarded':warmup,'status':'error' if error else 'interrupted' if interrupted else 'complete','error':error,'timestamp_note':'Native camera timestamps preserved; cross-stream clock alignment not validated.', 'first_timestamps_us':{'events':event_first,'frames':frame_times[0] if frame_times else None,'imu':imu_first},'nonmonotonic_frame_timestamps':sum(b<a for a,b in zip(frame_times,frame_times[1:])), 'frame_timestamp_jump_over_10s':any(abs(b-a)>10000000 for a,b in zip(frame_times,frame_times[1:]))}
   audit_streams={}
   if streams['events']: audit_streams['events']={'count':counts['events'],'first_us':event_first,'last_us':event_last,'backward_batches':event_backward}
   if streams['frames']: audit_streams['frames']={'count':counts['frames'],'first_us':frame_times[0] if frame_times else None,'last_us':frame_times[-1] if frame_times else None,'backward':data['nonmonotonic_frame_timestamps'],'jumps_over_10s':int(data['frame_timestamp_jump_over_10s'])}
   if streams['imu']: audit_streams['imu']={'count':counts['imu'],'first_us':imu_first,'last_us':imu_last,'backward':imu_backward}
   data['timestamp_assessment']=assess_timestamps(audit_streams)
   if data['timestamp_assessment']['status'] != 'PASS' and not error:
    error='Timestamp audit did not pass: '+str(data['timestamp_assessment']['issues'])
    data['status']='timestamp_audit_failed'; data['error']=error
   meta.write_text(json.dumps(data,indent=2),encoding='utf-8'); print(json.dumps(data,indent=2))
 return 1 if error or not counts['events'] else 0
if __name__=='__main__': sys.exit(main())
