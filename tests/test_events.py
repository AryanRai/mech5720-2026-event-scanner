import numpy as np
from event_camera.config import Config
from event_camera.filters import EventFilter
from event_camera.playback import WindowSlicer
from event_camera.stripe_detector import detect_stripe
DT=np.dtype([('timestamp','i8'),('x','i2'),('y','i2'),('polarity','i1')])
def arr(rows): return np.array(rows,dtype=DT)
def test_filters():
 c=Config(refractory_us=100,support_radius=1,support_us=1000,minimum_support=1,polarity='positive')
 e=arr([(1000,5,5,1),(1010,5,5,1),(1020,6,5,1),(1030,7,5,0),(1040,30,30,1)])
 f=EventFilter(40,40,c); out=f.apply(e)
 assert len(out)==1 and out[0]['x']==6

def test_windows_cross_packets():
 s=WindowSlicer(100); e=arr([(1,1,1,1),(50,1,1,1),(110,1,1,1),(250,1,1,1)])
 out=s.push(e[:1])+s.push(e[1:]); out+=s.flush()
 assert [len(v) for _,v in out]==[2,1,1]

def test_line_and_noise():
 c=Config(minimum_inliers=20); rng=np.random.default_rng(3); rows=[]
 for i in range(150):
  y=i%100; x=70+int(.1*y)+int(rng.integers(-1,2)); rows.append((i,x,y,1))
 e=arr(rows); obs=detect_stripe(e,240,180,c)
 assert obs is not None and obs.inlier_count>=120 and obs.residual_px<2 and 0<obs.confidence<=1
 assert detect_stripe(e[:5],240,180,c) is None

def test_filter_state_across_batches_and_timestamp_order():
 c=Config(refractory_us=100,minimum_support=0)
 f=EventFilter(20,20,c)
 assert len(f.apply(arr([(1000,4,4,1)])))==1
 assert len(f.apply(arr([(1050,4,4,1),(1100,4,4,1)])))==1
 import pytest
 with pytest.raises(ValueError): f.apply(arr([(1099,4,4,1)]))


def test_negative_polarity():
 c=Config(polarity='negative',minimum_support=0,refractory_us=0)
 out=EventFilter(20,20,c).apply(arr([(1,1,1,1),(2,2,2,0)]))
 assert len(out)==1 and out[0]['polarity']==0

def test_slanted_stripe_with_background():
 rng=np.random.default_rng(9); rows=[]
 for i in range(180):
  y=i%150; rows.append((i,80+int(y*.08)+int(rng.integers(-1,2)),y,1))
 for i in range(60): rows.append((180+i,int(rng.integers(0,240)),int(rng.integers(0,180)),int(rng.integers(0,2))))
 obs=detect_stripe(arr(rows),240,180,Config(minimum_inliers=20))
 assert obs is not None
 assert abs(obs.centroid_x-86)<5 and obs.inlier_count>=150 and obs.residual_px<2


def test_support_rejects_isolated_and_refractory_hot_pixel():
 c=Config(refractory_us=100, support_radius=1, support_us=200,minimum_support=1)
 events=arr([(1000,5,5,1),(1010,5,5,1),(1020,6,5,1),(1400,15,15,1)])
 out=EventFilter(20,20,c).apply(events)
 assert len(out)==1 and out[0]['x']==6

def test_compiled_filter_matches_reference_across_packets():
 rng=np.random.default_rng(71)
 times=np.cumsum(rng.integers(0,100,size=1000))+1000
 events=arr([(int(t),int(x),int(y),int(p)) for t,x,y,p in zip(times,rng.integers(0,12,1000),rng.integers(0,10,1000),rng.integers(0,2,1000))])
 c=Config(polarity='both',refractory_us=100,support_radius=2,support_us=500,minimum_support=2)
 refractory=np.full((10,12),-1,np.int64); support=np.full((10,12),-1,np.int64); expected=[]
 for e in events:
  t,x,y=int(e['timestamp']),int(e['x']),int(e['y'])
  last=refractory[y,x]
  if last>=0 and t-last<c.refractory_us: continue
  refractory[y,x]=t
  patch=support[max(0,y-2):min(10,y+3),max(0,x-2):min(12,x+3)]
  count=np.count_nonzero((patch>=0)&(patch>=t-c.support_us)); support[y,x]=t
  if count>=2: expected.append(e)
 f=EventFilter(12,10,c); got=np.concatenate([f.apply(events[:321]),f.apply(events[321:])])
 np.testing.assert_array_equal(got,np.array(expected,dtype=DT))
