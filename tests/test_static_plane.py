import cv2
import numpy as np
import pytest
from scripts.fit_static_plane import intersect_board, fit_plane
from scripts.validate_static_plane import fixed_plane_residuals


def test_ray_board_intersection_includes_distortion_and_tilt():
    matrix = np.array([[300., 0, 120], [0, 300, 90], [0, 0, 1]])
    distortion = np.array([-.2, .1, .003, -.002, 0])
    rv = np.array([.1, .2, 0.])
    rotation = cv2.Rodrigues(rv)[0]; translation = np.array([20., -10, 400])
    board = np.array([[0., 0, 0], [100, 50, 0], [-20, 80, 0]])
    expected = board @ rotation.T + translation
    pixels = cv2.projectPoints(board, rv, translation, matrix, distortion)[0]
    actual = intersect_board(pixels, matrix, distortion, rotation, translation)
    np.testing.assert_allclose(actual, expected, atol=1e-4)


def test_plane_from_two_lines_and_collinear_refusal():
    y = np.linspace(-50, 50, 12)
    groups = [np.column_stack((np.full(len(y), x), y, np.full(len(y), 2*x+300))) for x in (-20, 40)]
    normal, offset, _ = fit_plane(groups)
    for g in groups:
        np.testing.assert_allclose(g @ normal+offset, 0, atol=1e-10)
    with pytest.raises(ValueError):
        fit_plane([groups[0], groups[0]])


def test_frozen_plane_keeps_depth_bias_instead_of_aligning_it_away():
    matrix = np.array([[300., 0, 120], [0, 300, 90], [0, 0, 1]])
    pixels = np.array([[100., 70], [130, 90], [140, 120]])
    normal = np.array([0., 0, 1])
    board = intersect_board(pixels, matrix, np.zeros(5), np.eye(3), np.array([0., 0, 400]))
    metrics, predicted, errors, _ = fixed_plane_residuals(pixels, board, matrix, np.zeros(5), normal, -410)
    assert metrics['signed_depth_bias_mm'] == 10
    assert metrics['depth_rmse_mm'] == 10
    np.testing.assert_allclose(errors, 10)
    np.testing.assert_allclose(predicted[:, 2], 410)
