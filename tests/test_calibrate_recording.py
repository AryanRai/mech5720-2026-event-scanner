import importlib.util
from pathlib import Path
import numpy as np

spec = importlib.util.spec_from_file_location('offline_calibration', Path(__file__).resolve().parents[1]/'scripts/calibrate_recording.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def row(index, x, sharpness=100):
    return {'index':index,'sharpness':sharpness,'feature':np.array([x,.5,.4,.4,0,0,0])}


def test_no_candidates():
    assert module.select_diverse([]) == []


def test_duplicates_do_not_count_as_extra_poses():
    data = [row(0,.5,100),row(1,.5,150),row(2,.5,120)]
    assert [x['index'] for x in module.select_diverse(data)] == [1]


def test_diversity_selection_is_bounded_and_chronological():
    data = [row(3,.9),row(2,.5,200),row(1,.1),row(0,.3)]
    chosen = module.select_diverse(data,limit=3)
    assert len(chosen) == 3
    assert [x['index'] for x in chosen] == sorted(x['index'] for x in chosen)


def test_selection_does_not_mutate_input():
    data = [row(0,.1),row(1,.5),row(2,.9)]
    before = [x['feature'].copy() for x in data]
    module.select_diverse(data)
    assert all(np.array_equal(x['feature'],y) for x,y in zip(data,before))


def test_board_photometry_allows_black_squares():
    image = np.zeros((80,80),np.uint8)
    image[:,40:] = 160
    corners = np.array([[[0,0]],[[79,0]],[[79,79]],[[0,79]]],np.float32)
    metrics,reasons = module.board_photometry(image,corners)
    assert reasons == []
    assert metrics['contrast_p90_p10'] == 160


def test_board_photometry_rejects_bright_clipping_and_low_contrast():
    image = np.full((80,80),255,np.uint8)
    corners = np.array([[[0,0]],[[79,0]],[[79,79]],[[0,79]]],np.float32)
    _,reasons = module.board_photometry(image,corners)
    assert 'board ROI bright clipping' in reasons
    assert 'low board ROI contrast' in reasons


def test_background_does_not_determine_board_photometry():
    image=np.full((100,100),255,np.uint8)
    image[30:71,30:50]=0; image[30:71,50:71]=160
    corners=np.array([[[30,30]],[[70,30]],[[70,70]],[[30,70]]],np.float32)
    metrics,reasons=module.board_photometry(image,corners)
    assert reasons == []
    assert metrics['bright_fraction'] == 0
