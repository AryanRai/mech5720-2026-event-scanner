import numpy as np
from scripts.compare_static_events_aps import event_rows, pulse_pair, xyz

DTYPE=[('timestamp','<i8'),('x','<i2'),('y','<i2'),('polarity','i1')]


def test_event_rows_weighted_centroid_and_polarity():
    e=np.array([(1000000,40,30,1)]*4+[(1000001,41,30,1)]*8+[(1000002,100,31,0)]*20,dtype=DTYPE)
    pixels,_=event_rows(e,1000000,1,50)
    assert pixels.shape==(1,2)
    np.testing.assert_allclose(pixels[0],[40+2/3,30])


def test_ray_plane_intersection_and_negative_depth_rejection():
    pixels=np.array([[0.,0.],[1.,2.]])
    points,valid=xyz(pixels,{'normal_camera':[0,0,1],'offset_mm':-100},np.eye(3),np.zeros(5))
    np.testing.assert_allclose(points,[[0,0,100],[100,200,100]])
    assert valid.all()
    points,valid=xyz(pixels,{'normal_camera':[0,0,1],'offset_mm':100},np.eye(3),np.zeros(5))
    assert not valid.any() and len(points)==0


def test_event_only_known_duration_pair_ignores_early_motion():
    background=[(t,5,30,t%2) for t in range(0,7000000,10000)]
    e=np.array(background+[(2500000,40,40,1)]*100+[(3500000,40,40,0)]*100+[(500000,80,40,1)]*1000,dtype=DTYPE)
    e.sort(order='timestamp')
    on,off,_=pulse_pair(e)
    assert abs(on-2500000)<=10000
    assert off-on==1000000


def test_board_reference_depth_and_finite_target_exclusion():
    from scripts.validate_static_events_board_d import evaluate
    obs={'board_normal':[0,0,1],'board_t_mm':[0,0,100],'board_rvec':[0.,0.,0.]}
    metrics,rows=evaluate(np.array([[.5,.5],[2.,2.]]),{'normal_camera':[0,0,1],'offset_mm':-110},obs,np.eye(3),np.zeros(5))
    assert metrics['rows']==1
    assert metrics['depth_rmse_mm']==10
    assert rows[0]['reference_Z_mm']==100
