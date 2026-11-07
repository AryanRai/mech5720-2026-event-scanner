import numpy as np
import pytest
from scripts.reconstruct_dense_interpolated import interpolate


def test_interpolation_preserves_endpoints_and_plane_sign():
    planes={100:dict(normal_camera=[1.,0,0],offset_mm=-10.),
            200:dict(normal_camera=[0.,0,-1.],offset_mm=20.)}
    n,d,meta=interpolate(planes,100)
    assert np.allclose(n,[1,0,0]) and d==-10 and meta['independently_fitted_knot']
    n,d,_=interpolate(planes,200)
    assert np.allclose(n,[0,0,-1]) and d==20
    flipped={100:dict(normal_camera=[1.,0,0],offset_mm=-10.),
             200:dict(normal_camera=[-1.,0,0],offset_mm=20.)}
    n,d,meta=interpolate(flipped,150)
    assert np.allclose(n,[1,0,0]) and d==-15 and meta['upper_weight']==.5


def test_interpolation_refuses_unobserved_command_range():
    planes={100:dict(normal_camera=[1.,0,0],offset_mm=-10.),
            200:dict(normal_camera=[1.,0,0],offset_mm=-20.)}
    with pytest.raises(ValueError):interpolate(planes,99)
