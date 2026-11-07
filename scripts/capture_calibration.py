"""Capture diverse DAVIS calibration views; use --calibrate for an offline rerun."""
import argparse, csv, json, sys, time
from collections import deque
from datetime import datetime
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2
import dv_processing as dv
import numpy as np
from event_camera.camera import open_davis, require_stream
from event_camera.calibration import detect, features, novelty, quality, calibrate, save_json, load_json

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data/calibration/intrinsics'
FIELDS=['filename','timestamp_us','sharpness','center_x','center_y','width','height','orientation_degrees','capture_order','mode','features']


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--checkerboard-cols',type=int,default=9); p.add_argument('--checkerboard-rows',type=int,default=6); p.add_argument('--square-size-mm',type=float,default=18)
    p.add_argument('--serial'); p.add_argument('--duration',type=float,help='bounded live check in seconds'); p.add_argument('--calibrate',action='store_true',help='calibrate saved images without camera')
    p.add_argument('--exclude',action='append',default=[],help='filename to exclude, repeatable'); p.add_argument('--min-sharpness',type=float,default=20)
    a=p.parse_args(); pattern=(a.checkerboard_cols,a.checkerboard_rows)
    if min(pattern)<2 or a.square_size_mm<=0 or a.min_sharpness<0 or (a.duration is not None and a.duration<=0): p.error('invalid board dimensions, square size or sharpness')
    DATA.mkdir(parents=True,exist_ok=True); (DATA/'images').mkdir(exist_ok=True); (DATA/'diagnostics').mkdir(exist_ok=True)
    meta=DATA/'dataset.json'; spec={'cols':pattern[0],'rows':pattern[1],'square_size_mm':a.square_size_mm}
    if meta.exists():
        saved=load_json(meta)
        if any(saved[k]!=v for k,v in spec.items()): p.error('Board specification differs from existing dataset; use the same parameters or move the dataset aside')
        if a.serial and saved.get('serial') and a.serial!=saved['serial']: p.error('Serial differs from existing dataset')
    elif a.calibrate: p.error('No existing dataset metadata')
    else: saved=dict(spec,serial=a.serial)
    csvpath=DATA/'captures.csv'
    rows=[]
    if csvpath.exists():
        with csvpath.open(newline='',encoding='utf-8') as f: rows=list(csv.DictReader(f))
    def run_calibration():
        names={r['filename'] for r in rows}; unknown=set(a.exclude)-names
        if unknown: raise ValueError(f'Unknown exclusions: {sorted(unknown)}')
        images=[DATA/'images'/r['filename'] for r in rows if r['filename'] not in a.exclude]
        calibrate(images,pattern,a.square_size_mm,saved.get('serial'),DATA)
    if a.calibrate:
        try: run_calibration(); return 0
        except Exception as e: print(f'Calibration error: {type(e).__name__}: {e}',file=sys.stderr); return 1
    try:
        camera=open_davis(a.serial); require_stream(camera,'Frame'); camera.setColorMode(dv.io.camera.DAVIS.ColorMode.GRAYSCALE)
        serial=camera.getDeviceDescriptor().serialNumber
        if saved.get('serial') and saved['serial']!=serial: raise ValueError('Connected camera serial differs from dataset')
        saved['serial']=serial; save_json(meta,saved)
        print(f'Frame resolution: {camera.getFrameResolution()}'); print('SPACE capture, A auto, C calibrate, S screenshot, R reset guidance, Q quit')
        accepted=[np.array(json.loads(r['features'])) for r in rows]; recent=deque(maxlen=5); auto=False; last_save=0; message='Move board through varied poses'; current=None; preview=None; reset_pending=False; started=time.monotonic(); received=0; last_monitor=0
        while a.duration is None or time.monotonic()-started<a.duration:
            if not camera.isRunning(): raise RuntimeError('Camera stopped or disconnected')
            frame=camera.getNextFrame()
            if frame is not None:
                received+=1
                gray=frame.image
                if time.monotonic()-last_monitor >= 1:
                    monitor_path=ROOT/'outputs'/'live_monitor.png'
                    monitor_path.parent.mkdir(parents=True,exist_ok=True)
                    cv2.imwrite(str(monitor_path),gray)
                    last_monitor=time.monotonic()
                if gray.ndim!=2: raise RuntimeError(f'Expected grayscale, got {gray.shape}')
                h,w=gray.shape; corners=detect(gray,pattern); score,reasons=quality(gray,corners,pattern,a.min_sharpness)
                f=features(corners,(w,h),pattern) if corners is not None else None
                dist=novelty(f,accepted) if f is not None else 0
                recent.append(f.copy() if f is not None else None)
                stable=len(recent)==5 and all(x is not None for x in recent) and max(np.linalg.norm((x[:4]-recent[-1][:4])) for x in recent)<.015
                current=(frame,score,reasons,f,dist,stable)
                im=cv2.cvtColor(gray,cv2.COLOR_GRAY2BGR)
                if corners is not None: cv2.drawChessboardCorners(im,pattern,corners,True)
                im=cv2.resize(im,(720,540),interpolation=cv2.INTER_NEAREST)
                preview=np.zeros((540,1200,3),np.uint8); preview[:,:720]=im
                grid=[False]*9
                for feature in accepted:
                    col=min(2,max(0,int(feature[0]*3))); row=min(2,max(0,int(feature[1]*3))); grid[row*3+col]=True
                lines=[f'Checkerboard: {"YES" if corners is not None else "NO"}  corners: {len(corners) if corners is not None else 0}/{pattern[0]*pattern[1]}',f'Sharpness: {score:.1f} (min {a.min_sharpness:g})',f'Board width/height: {f[2]*100:.0f}% / {f[3]*100:.0f}%' if f is not None else 'Board width/height: --',f'Centre: {f[0]*w:.1f}, {f[1]*h:.1f} | angle: {f[4]*180:.1f} deg' if f is not None else 'Centre / angle: --',f'Pose: {"GOOD NEW POSE" if f is not None and dist>=1 else "POSE TOO SIMILAR" if f is not None else "NOT DETECTED"}',f'Stable: {stable} | AUTO: {auto}',f'Accepted: {len(rows)} (target 15-25 diverse views)',f'Quality: {", ".join(reasons) if reasons else "OK"}', 'COVERAGE: centres in image thirds']
                for y in range(3): lines.append('  '.join(('TL','T','TR','L','C','R','BL','B','BR')[y*3+x]+(' [X]' if grid[y*3+x] else ' [ ]') for x in range(3)))
                if len(rows)>=15 and sum(grid)>=5: lines.append('ENOUGH DIVERSE IMAGES - PRESS C')
                lines += [message,'SPACE save | A auto | C calibrate','R reset guidance (confirm R) | S screenshot | Q quit']
                for i,line in enumerate(lines): cv2.putText(preview,line[:64],(730,23+i*27),cv2.FONT_HERSHEY_SIMPLEX,.42,(255,255,255),1,cv2.LINE_AA)
                cv2.imshow('DAVIS calibration capture',preview)
            key=cv2.waitKey(1)&255
            if key in (ord('q'),27): break
            if key==ord('a'): auto=not auto; message=f'Auto capture {"ON" if auto else "OFF"}'
            if key==ord('r'):
                if reset_pending: accepted=[]; recent.clear(); reset_pending=False; message='Guidance reset; saved images preserved'
                else: reset_pending=True; message='Press R again to reset guidance only'
            elif key!=255: reset_pending=False
            if key==ord('s') and preview is not None:
                path=DATA/'diagnostics'/f'diagnostic_{datetime.now():%Y%m%d_%H%M%S_%f}.png'; cv2.imwrite(str(path),preview); message=f'Saved {path.name}'
            if key==ord('c'):
                try: run_calibration(); message='Calibration saved; see console and report'
                except Exception as e: message=f'Calibration failed: {e}'; print(message,file=sys.stderr)
            should_save=key==32 or (auto and current is not None and current[4]>=1 and current[5] and time.monotonic()-last_save>=2)
            if should_save and current is not None:
                fr,score,reasons,f,dist,stable=current
                if reasons: message='REJECTED: '+', '.join(reasons); print(message)
                elif dist<1: message='REJECTED: pose too similar'; print(message)
                else:
                    name=f'image_{datetime.now():%Y%m%d_%H%M%S_%f}.png'; path=DATA/'images'/name
                    if not cv2.imwrite(str(path),fr.image): raise RuntimeError('Failed to save image')
                    row={'filename':name,'timestamp_us':fr.timestamp,'sharpness':score,'center_x':f[0]*w,'center_y':f[1]*h,'width':f[2]*w,'height':f[3]*h,'orientation_degrees':f[4]*180,'capture_order':len(rows)+1,'mode':'manual' if key==32 else 'automatic','features':json.dumps(f.tolist())}
                    with csvpath.open('a',newline='',encoding='utf-8') as file:
                        writer=csv.DictWriter(file,fieldnames=FIELDS)
                        if file.tell()==0: writer.writeheader()
                        writer.writerow(row)
                    rows.append(row); accepted.append(f); last_save=time.monotonic(); message=f'Saved {name}'; print(message)
            time.sleep(.001)
        print(f'Capture exited cleanly; frames received: {received}'); return 0 if received else 1
    except KeyboardInterrupt: print('Capture interrupted cleanly'); return 0
    except Exception as e: print(f'Capture error: {type(e).__name__}: {e}',file=sys.stderr); return 2
    finally: cv2.destroyAllWindows()

if __name__=='__main__': sys.exit(main())
