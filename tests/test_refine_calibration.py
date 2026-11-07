import cv2
import numpy as np
from scripts.refine_calibration import align_grid, grid_residual, fit_model
from event_camera.calibration import object_points


def test_align_grid_recovers_reversed_order():
    p=object_points(9,6,10)[:,:2].reshape(-1,1,2)
    assert np.allclose(align_grid(p,p[::-1],(9,6)),p)


def test_projective_grid_residual_is_small():
    p=object_points(9,6,1)[:,:2].reshape(-1,1,2)
    H=np.array([[10.,1.,20.],[.3,9.,15.],[.01,.02,1.]])
    q=cv2.perspectiveTransform(p,H)
    assert np.max(grid_residual(q,(9,6)))<1e-4


def test_displaced_corner_is_visible_in_grid_residual():
    p=object_points(9,6,10)[:,:2].reshape(-1,1,2)
    p[0,0,0]+=12
    assert np.max(grid_residual(p,(9,6)))>2


def test_fit_model_uses_reserved_points_only_for_pose_evaluation():
    obj=object_points(9,6,18)
    K=np.array([[310.,0,120.],[0,309.,90.],[0,0,1.]])
    rng=np.random.default_rng(11); rows=[]
    for i in range(15):
        rv=rng.uniform(-.3,.3,3); tv=np.array([-65.+i,-45.,400.+i*8])
        points,_=cv2.projectPoints(obj,rv,tv,K,np.zeros(5))
        rows.append({'index':i,'corners':points})
    result=fit_model(rows[:12],rows[12:],(9,6),18,(240,180),cv2.CALIB_FIX_K3)
    assert result['training_frame_indices']==list(range(12))
    assert result['reserved_frame_indices']==[12,13,14]
    assert result['training_rms_px']<1e-3
    assert max(result['reserved_per_view_rms_px'])<1e-3
    assert abs(result['camera_matrix'][0][0]-310)<.1
