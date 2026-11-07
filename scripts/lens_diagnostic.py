"""Live lens diagnosis; retains rolling metrics and latest unmodified frame."""
import csv,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2,dv_processing as dv,numpy as np
from event_camera.camera import open_davis,require_stream
from event_camera.calibration import detect

root=Path(__file__).resolve().parents[1]; out=root/'outputs/lens_diagnostic'; out.mkdir(parents=True,exist_ok=True)
try:
 c=open_davis(); require_stream(c,'Frame'); c.setColorMode(dv.io.camera.DAVIS.ColorMode.GRAYSCALE)
 print(f'Auto exposure: {c.getAutoExposure()}; requested exposure: {c.getExposureDuration()}')
 path=out/'live_metrics.csv'
 with path.open('w',newline='',encoding='utf-8') as file:
  writer=csv.writer(file); writer.writerow(['monotonic','camera_timestamp_us','exposure_us','sharpness','mean','dark_pct','bright_pct','corners']); file.flush()
  start=time.monotonic(); last=0; count=0
  while True:
   if not c.isRunning(): raise RuntimeError('Camera stopped or disconnected')
   frame=c.getNextFrame()
   if frame is not None:
    gray=frame.image; count+=1
    now=time.monotonic()
    if now-last>=.5:
     sharp=float(cv2.Laplacian(gray,cv2.CV_64F).var()); corners=detect(gray,(9,6)); n=len(corners) if corners is not None else 0
     exposure=frame.exposure.total_seconds()*1e6
     mean=float(gray.mean()); dark=float(np.mean(gray<=5)*100); bright=float(np.mean(gray>=250)*100)
     writer.writerow([now,frame.timestamp,exposure,sharp,mean,dark,bright,n]); file.flush()
     cv2.imwrite(str(out/'latest.png'),gray); last=now
    preview=cv2.resize(gray,(720,540),interpolation=cv2.INTER_NEAREST); preview=cv2.cvtColor(preview,cv2.COLOR_GRAY2BGR)
    cv2.putText(preview,f'Sharpness {sharp:.1f}  corners {n}/54  exposure {exposure/1000:.1f} ms',(8,24),cv2.FONT_HERSHEY_SIMPLEX,.55,(0,255,255),1)
    cv2.imshow('Lens diagnostic - q to quit',preview)
   if (cv2.waitKey(1)&255) in (27,ord('q')): break
   time.sleep(.001)
except KeyboardInterrupt: pass
except Exception as e: print(f'Diagnostic error: {type(e).__name__}: {e}',file=sys.stderr); sys.exit(1)
finally: cv2.destroyAllWindows()
