import numpy as np
import cv2
from event_camera.calibration import object_points, pose_distance, novelty, reprojection_errors, save_json, load_json


def test_object_points():
    p=object_points(9,6,18)
    assert p.shape==(54,3)
    np.testing.assert_allclose(p[1],[18,0,0]); np.testing.assert_allclose(p[-1],[144,90,0])


def test_serialization(tmp_path):
    data={'camera_matrix':[[1.,0.,2.],[0.,1.,3.],[0.,0.,1.]],'distortion_coefficients':[.1,0,0,0,0]}
    file=tmp_path/'intrinsics.json'; save_json(file,data); assert load_json(file)==data


def test_novelty():
    a=np.array([.5,.5,.5,.5,0,0,0]); b=a.copy(); b[0]+=.2
    assert pose_distance(a,a)==0 and novelty(a,[a])==0
    assert novelty(b,[a])>1
    assert np.isinf(novelty(a,[]))


def test_reprojection():
    obj=object_points(9,6,18); K=np.array([[200.,0,120],[0,200,90],[0,0,1.]])
    r=np.zeros((3,1)); t=np.array([[0.],[0.],[1000.]])
    image,_=cv2.projectPoints(obj,r,t,K,np.zeros(5))
    assert reprojection_errors([obj],[image],[r],[t],K,np.zeros(5))[0]<1e-5
    shifted=image.copy(); shifted[:,:,0]+=2
    assert abs(reprojection_errors([obj],[shifted],[r],[t],K,np.zeros(5))[0]-2)<1e-4
