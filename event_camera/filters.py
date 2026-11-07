"""Causal per-pixel filters operating across timestamp-ordered packets."""
import numpy as np
from numba import njit

@njit(cache=True)
def _filter(timestamps,xs,ys,polarity,refractory,support,previous,mode,refractory_us,radius,support_us,minimum):
    n=len(timestamps); keep=np.zeros(n,np.bool_); h,w=refractory.shape
    for i in range(n):
        t=timestamps[i]; x=xs[i]; y=ys[i]; p=polarity[i]!=0
        if previous>=0 and t<previous: raise ValueError('Events must be timestamp ordered across packets')
        previous=t
        if x<0 or x>=w or y<0 or y>=h: raise ValueError('Event coordinate outside sensor')
        if (mode==1 and not p) or (mode==2 and p): continue
        last=refractory[y,x]
        if last>=0 and t-last<refractory_us: continue
        refractory[y,x]=t; count=0
        for yy in range(max(0,y-radius),min(h,y+radius+1)):
            for xx in range(max(0,x-radius),min(w,x+radius+1)):
                q=support[yy,xx]
                if q>=0 and q>=t-support_us: count+=1
        support[y,x]=t
        if count>=minimum: keep[i]=True
    return keep,previous

class EventFilter:
    def __init__(self,width,height,config):
        self.w=width; self.h=height; self.c=config
        self.refractory=np.full((height,width),-1,dtype=np.int64)
        self.support=np.full((height,width),-1,dtype=np.int64)
        self.last_time=-1
    def apply(self,events):
        c=self.c; mode={'both':0,'positive':1,'negative':2}[c.polarity]
        keep,self.last_time=_filter(np.ascontiguousarray(events['timestamp']),np.ascontiguousarray(events['x']),np.ascontiguousarray(events['y']),np.ascontiguousarray(events['polarity']),self.refractory,self.support,self.last_time,mode,c.refractory_us,c.support_radius,c.support_us,c.minimum_support)
        return events[keep]
    def warmup(self):
        dtype=np.dtype([('timestamp','i8'),('x','i2'),('y','i2'),('polarity','i1')])
        self.apply(np.empty(0,dtype=dtype))
