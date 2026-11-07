"""Image-space capture guidance and standard pinhole calibration."""
import json
from pathlib import Path
from datetime import datetime, timezone
import cv2
import numpy as np


def object_points(cols, rows, square_mm):
    if cols < 2 or rows < 2 or square_mm <= 0: raise ValueError('Invalid checkerboard dimensions or square size')
    p=np.zeros((cols*rows,3),np.float32)
    p[:,:2]=np.mgrid[0:cols,0:rows].T.reshape(-1,2)*square_mm
    return p


def detect(gray, pattern):
    ok,corners=cv2.findChessboardCorners(gray, pattern, cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE)
    if not ok: return None
    return cv2.cornerSubPix(gray,corners,(5,5),(-1,-1),(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_MAX_ITER,30,.01))


def features(corners, size, pattern):
    w,h=size; p=corners.reshape(pattern[1],pattern[0],2); allp=p.reshape(-1,2)
    low=allp.min(axis=0); high=allp.max(axis=0); center=allp.mean(axis=0)
    v=p[0,-1]-p[0,0]; angle=np.arctan2(v[1],v[0])
    top=np.linalg.norm(p[0,-1]-p[0,0]); bottom=np.linalg.norm(p[-1,-1]-p[-1,0])
    left=np.linalg.norm(p[-1,0]-p[0,0]); right=np.linalg.norm(p[-1,-1]-p[0,-1])
    return np.array([center[0]/w,center[1]/h,(high[0]-low[0])/w,(high[1]-low[1])/h,angle/np.pi,(top-bottom)/max(top+bottom,1e-9),(left-right)/max(left+right,1e-9)],float)


def pose_distance(a,b):
    d=np.asarray(a)-np.asarray(b)
    d[4]=((d[4]+.5)%1)-.5
    return float(np.linalg.norm(d / np.array([.15,.15,.15,.15,.15,.12,.12])))


def novelty(feature, accepted):
    return min((pose_distance(feature,x) for x in accepted),default=float('inf'))


def quality(gray,corners,pattern,min_sharpness=20):
    reasons=[]; h,w=gray.shape
    score=float(cv2.Laplacian(gray,cv2.CV_64F).var())
    if corners is None or len(corners)!=pattern[0]*pattern[1]: reasons.append('full board not detected')
    if score<min_sharpness: reasons.append('low sharpness')
    if np.mean(gray<=5)>=.2 or np.mean(gray>=250)>=.2: reasons.append('excess clipping')
    if corners is not None:
        pts=corners.reshape(-1,2); lo=pts.min(axis=0); hi=pts.max(axis=0)
        # One half-square margin approximates the unseen outer board edge.
        step=np.median(np.linalg.norm(np.diff(pts.reshape(pattern[1],pattern[0],2),axis=1),axis=2))
        margin=max(4,step*.5)
        if lo[0]<margin or lo[1]<margin or hi[0]>=w-margin or hi[1]>=h-margin: reasons.append('board near image edge')
        if (hi[0]-lo[0])/w<.25 or (hi[1]-lo[1])/h<.25: reasons.append('board too small')
    return score,reasons


def reprojection_errors(obj, image_points, rvecs, tvecs, K, dist):
    errors=[]
    for o,im,r,t in zip(obj,image_points,rvecs,tvecs):
        proj,_=cv2.projectPoints(o,r,t,K,dist)
        delta=proj.reshape(-1,2)-np.asarray(im).reshape(-1,2)
        errors.append(float(np.sqrt(np.mean(np.sum(delta**2,axis=1)))))
    return errors


def save_json(path, data):
    Path(path).write_text(json.dumps(data,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def calibrate(images, pattern, square_mm, serial, output):
    if len(images)<10: raise ValueError('At least 10 valid views are required')
    obj=[]; points=[]; used=[]; size=None
    for path in images:
        image=cv2.imread(str(path),cv2.IMREAD_GRAYSCALE)
        if image is None: raise ValueError(f'Cannot read {path}')
        current=(image.shape[1],image.shape[0])
        if size is None: size=current
        if current!=size: raise ValueError(f'Image resolution mismatch: {path}')
        corners=detect(image,pattern)
        if corners is None: raise ValueError(f'Checkerboard detection failed: {path}; exclude explicitly if necessary')
        obj.append(object_points(*pattern,square_mm)); points.append(corners); used.append(Path(path).name)
    rms,K,dist,rvecs,tvecs=cv2.calibrateCamera(obj,points,size,None,None)
    errors=reprojection_errors(obj,points,rvecs,tvecs,K,dist)
    med=float(np.median(errors)); mad=float(np.median(np.abs(np.array(errors)-med)))
    threshold=max(1.0,med+3*1.4826*mad)
    outliers=[used[i] for i,e in enumerate(errors) if e>threshold]
    data={'camera_model':'DAVIS240C','serial':serial,'resolution':{'width':size[0],'height':size[1]},'checkerboard':{'inner_corners_cols':pattern[0],'inner_corners_rows':pattern[1],'square_size_mm':square_mm},'camera_matrix':K.tolist(),'intrinsics':{'fx':float(K[0,0]),'fy':float(K[1,1]),'cx':float(K[0,2]),'cy':float(K[1,2])},'distortion_coefficients':dist.ravel().tolist(),'rms_reprojection_error_px':float(rms),'mean_per_view_rms_px':float(np.mean(errors)),'median_per_view_rms_px':med,'per_view_rms_px':dict(zip(used,errors)),'images_used':used,'potential_outliers':outliers,'outlier_threshold_px':threshold,'rotation_vectors':[v.ravel().tolist() for v in rvecs],'translation_vectors_mm':[v.ravel().tolist() for v in tvecs],'date_time':datetime.now(timezone.utc).isoformat()}
    output=Path(output); output.mkdir(parents=True,exist_ok=True)
    save_json(output/'davis240c_intrinsics.json',data)
    lines=['DAVIS240C intrinsic calibration',f"Date: {data['date_time']}",f'Serial: {serial}',f'Resolution: {size}',f'Checkerboard: {pattern}, {square_mm} mm',f'Images: {len(used)}',f'K:\n{K}',f'Distortion: {dist.ravel()}',f'Overall RMS: {rms:.4f} px',f'Mean/median per-view RMS: {np.mean(errors):.4f} / {med:.4f} px',f'Worst: {used[int(np.argmax(errors))]} {max(errors):.4f} px',f'Best: {used[int(np.argmin(errors))]} {min(errors):.4f} px',f'Potential outliers (threshold {threshold:.3f} px): {outliers}','Per-view RMS (px):']
    lines += [f'{name}: {e:.4f}' + ('  <-- possible outlier' if name in outliers else '') for name,e in zip(used,errors)]
    report='\n'.join(lines)+'\n'; (output/'calibration_report.txt').write_text(report,encoding='utf-8'); print(report)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(max(8,len(used)*.5),4)); ax.bar(range(len(used)),errors); ax.axhline(threshold,color='red',linestyle='--',label='outlier heuristic'); ax.set_xticks(range(len(used)),used,rotation=90,fontsize=7); ax.set_ylabel('Per-view RMS reprojection error (px)'); ax.legend(); fig.tight_layout()
    plot=Path(__file__).resolve().parents[1]/'outputs/calibration/reprojection_error.png'; plot.parent.mkdir(parents=True,exist_ok=True); fig.savefig(plot,dpi=150); plt.close(fig)
    print(f'Saved: {output / "davis240c_intrinsics.json"}; {plot}')
    return data
