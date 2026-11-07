import numpy as np
from scripts.analyse_nd_fixed_position import stable_reference_diagnostic


def test_diagnostic_retains_repeated_stripe_and_rejects_clipping():
    reference=np.full((180,240),20.,float)
    images=np.full((5,180,240),20,np.uint8)
    images[:,30,40:42]=80
    pixels=stable_reference_diagnostic(images,reference,[0,1,2,3,4])
    np.testing.assert_allclose(pixels,[[40.5,30]])
    images[:,30,40:42]=255
    assert stable_reference_diagnostic(images,reference,[0,1,2,3,4]).shape==(0,2)


def test_diagnostic_rejects_ambiguous_parallel_groups():
    reference=np.full((180,240),20.,float)
    images=np.full((5,180,240),20,np.uint8)
    images[:,30,40:42]=80
    images[:,30,80:82]=80
    assert len(stable_reference_diagnostic(images,reference,[0,1,2,3,4]))==0
