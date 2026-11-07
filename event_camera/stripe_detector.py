"""Deterministic histogram candidate selection and robust line observation."""
from dataclasses import dataclass,asdict
import numpy as np

@dataclass
class StripeObservation:
    timestamp_us:int
    line_parameters:list
    centroid_x:float
    centroid_y:float
    event_count:int
    inlier_count:int
    residual_px:float
    confidence:float
    def as_dict(self): return asdict(self)

def detect_stripe(events,width,height,c):
    if len(events)<c.minimum_inliers: return None
    x=events['x'].astype(float); y=events['y'].astype(float)
    hist=np.bincount(x.astype(int),minlength=width)
    # Candidate band supports approximately vertical and moderately sloped lines.
    peak=int(np.argmax(hist)); band=max(8,width//8)
    mask=np.abs(x-peak)<=band
    pts=np.column_stack((x[mask],y[mask])); n=len(pts)
    if n<c.minimum_inliers: return None
    rng=np.random.default_rng(c.seed); best=None
    for _ in range(100):
        i,j=rng.choice(n,2,replace=False); v=pts[j]-pts[i]; norm=np.linalg.norm(v)
        if norm<1: continue
        normal=np.array([-v[1],v[0]])/norm; offset=-normal@pts[i]
        inside=np.abs(pts@normal+offset)<=c.line_threshold_px
        if best is None or inside.sum()>best.sum(): best=inside
    if best is None or best.sum()<c.minimum_inliers: return None
    inpts=pts[best]; center=inpts.mean(axis=0); _,_,vh=np.linalg.svd(inpts-center,full_matrices=False); normal=vh[-1]; offset=-normal@center
    residual=float(np.sqrt(np.mean((inpts@normal+offset)**2)))
    confidence=float(np.clip((len(inpts)/max(len(events),1))*(min(1,len(inpts)/(2*c.minimum_inliers)))*max(0,1-residual/c.line_threshold_px),0,1))
    return StripeObservation(int(events['timestamp'][-1]),[float(normal[0]),float(normal[1]),float(offset)],float(center[0]),float(center[1]),len(events),len(inpts),residual,confidence)
