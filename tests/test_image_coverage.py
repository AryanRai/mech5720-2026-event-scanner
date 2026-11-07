import numpy as np
from scripts.measure_image_coverage import occupancy,coverage


def test_duplicate_centres_do_not_inflate_coverage():
    occupied,screen=occupancy([[1,1],[1.1,1.1],[2,2],[-1,2],[float('nan'),0]],(4,4))
    assert occupied.sum()==2
    assert screen['nonfinite_centres']==1
    assert screen['out_of_image_centres']==1
    mask=np.zeros((4,4),np.uint8);mask[1:3,1:3]=1
    q=coverage(mask,occupied)
    assert q['expected_mask_native_pixels']==4
    assert q['covered_native_pixels']==2
    assert q['coverage_percent']==50


def test_tolerance_is_clipped_to_fixed_mask_and_empty_denominator_explicit():
    occupied,_=occupancy([[1,1]],(3,3));mask=np.ones((3,3),np.uint8)
    assert coverage(mask,occupied,1)['covered_native_pixels']==5
    assert coverage(mask,occupied,2)['covered_native_pixels']==9
    assert coverage(mask*0,occupied)['coverage_percent'] is None
