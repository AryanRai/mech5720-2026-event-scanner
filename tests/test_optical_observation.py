import numpy as np
from scripts.analyse_optical_observation import stripe_measurement


def test_absent_stripe_and_known_translation():
    dark = np.zeros((180, 240), dtype=np.uint8)
    assert stripe_measurement(dark, dark) is None
    left = dark.copy(); left[30:130, 100:103] = 180
    right = dark.copy(); right[30:130, 104:107] = 180
    a, b = stripe_measurement(left, dark), stripe_measurement(right, dark)
    assert abs(b['x_at_row70']-a['x_at_row70']-4) < 1e-8
    assert a['clipped_fraction'] == 0
    left[30:130, 100:103] = 255
    assert stripe_measurement(left, dark)['clipped_fraction'] == 1


def test_interrupted_stripe_on_black_squares_and_short_blob():
    dark = np.zeros((180, 240), dtype=np.uint8)
    interrupted = dark.copy()
    for first in (35,65,95):
        interrupted[first:first+15, 100:103] = 180
    assert stripe_measurement(interrupted, dark) is not None
    short = dark.copy(); short[40:75, 100:103] = 180
    assert stripe_measurement(short, dark) is None
