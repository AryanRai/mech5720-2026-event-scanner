"""Compare raw and undistorted APS or a saved grayscale image."""
import argparse, sys, time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2
import dv_processing as dv
import numpy as np
from event_camera.camera import open_davis, require_stream
from event_camera.calibration import load_json

ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--calibration',default=str(ROOT/'data/calibration/intrinsics/davis240c_intrinsics.json')); p.add_argument('--image'); p.add_argument('--serial'); a=p.parse_args()
    try:
        data=load_json(a.calibration); K=np.array(data['camera_matrix'],dtype=float); dist=np.array(data['distortion_coefficients'],dtype=float)
        size=(data['resolution']['width'],data['resolution']['height'])
        camera=None
        if a.image:
            img=cv2.imread(a.image,cv2.IMREAD_GRAYSCALE)
            if img is None: raise ValueError(f'Cannot read image: {a.image}')
        else:
            camera=open_davis(a.serial); require_stream(camera,'Frame'); camera.setColorMode(dv.io.camera.DAVIS.ColorMode.GRAYSCALE)
            if camera.getDeviceDescriptor().serialNumber!=data['serial']: raise ValueError('Connected camera serial differs from calibration')
            print(f'Frame resolution: {camera.getFrameResolution()}'); img=None
        while True:
            if camera:
                if not camera.isRunning(): raise RuntimeError('Camera stopped or disconnected')
                frame=camera.getNextFrame()
                if frame is not None: img=frame.image
            if img is not None:
                if (img.shape[1],img.shape[0])!=size: raise ValueError('Image resolution differs from calibration')
                corrected=cv2.undistort(img,K,dist)
                combined=np.hstack((img,corrected)); combined=cv2.resize(combined,None,fx=2,fy=2,interpolation=cv2.INTER_NEAREST)
                cv2.putText(combined,'RAW',(8,20),cv2.FONT_HERSHEY_SIMPLEX,.6,255,1)
                cv2.putText(combined,'UNDISTORTED',(size[0]*2+8,20),cv2.FONT_HERSHEY_SIMPLEX,.6,255,1)
                cv2.imshow('Calibration validation',combined)
            if (cv2.waitKey(1)&255) in (27,ord('q')): break
            time.sleep(.001)
        print('Validation exited cleanly'); return 0
    except KeyboardInterrupt: print('Validation interrupted cleanly'); return 0
    except Exception as e: print(f'Validation error ({type(e).__name__}): {e}',file=sys.stderr); return 2
    finally: cv2.destroyAllWindows()

if __name__=='__main__': sys.exit(main())
