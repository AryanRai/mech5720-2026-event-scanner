"""Split ordered event packets into fixed sensor-time windows."""
import numpy as np
class WindowSlicer:
    def __init__(self,window_us): self.window_us=window_us; self.start=None; self.chunks=[]
    def push(self,events):
        if not len(events): return []
        out=[]
        if self.start is None: self.start=int(events['timestamp'][0])//self.window_us*self.window_us
        i=0
        while i<len(events):
            t=int(events['timestamp'][i])
            if t<self.start: raise ValueError('Events out of order')
            if t>=self.start+self.window_us:
                if self.chunks: out.append((self.start,np.concatenate(self.chunks))); self.chunks=[]
                self.start=t//self.window_us*self.window_us
            end=np.searchsorted(events['timestamp'],self.start+self.window_us,side='left')
            self.chunks.append(events[i:end]); i=end
        return out
    def flush(self):
        if not self.chunks: return []
        a=np.concatenate(self.chunks); self.chunks=[]; return [(self.start,a)]
