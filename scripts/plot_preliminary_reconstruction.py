"""Make a presentation figure from retained frozen-model held-out results."""
import json
from pathlib import Path
import cv2
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    source = Path('outputs/calibration/static_plane1500_C_validation_20261102_01/validation.json')
    data = json.loads(source.read_text())
    obs = data['observation']
    reference = np.asarray(obs['points_camera_mm'])
    reconstructed = np.asarray(data['predicted_points_camera_mm'])
    rotation = cv2.Rodrigues(np.asarray(obs['board_rvec']))[0]
    translation = np.asarray(obs['board_t_mm'])
    u, w = np.meshgrid(np.linspace(-18, 162, 11), np.linspace(-18, 108, 8))
    board = np.stack([u, w, np.zeros_like(u)], axis=-1) @ rotation.T + translation
    plt.rcParams.update({'font.size': 11, 'axes.spines.top': False, 'axes.spines.right': False})
    fig = plt.figure(figsize=(12, 6.3), facecolor='white')
    ax = fig.add_subplot(121, projection='3d')
    ax.plot_wireframe(board[:, :, 0], board[:, :, 2], -board[:, :, 1], color='#b5bdc5', alpha=.45, linewidth=.6)
    ax.scatter(reference[:, 0], reference[:, 2], -reference[:, 1], c='#147d92', s=20, label='Stripe on posed reference board')
    ax.scatter(reconstructed[:, 0], reconstructed[:, 2], -reconstructed[:, 1], c='#d25c30', s=22, marker='x', label='Reconstructed stripe')
    ax.set(xlabel='Camera X (mm)', ylabel='Camera Z / depth (mm)', zlabel='−Camera Y (mm)', title='Actual data: one static laser stripe')
    ax.view_init(elev=23, azim=-62)
    ax.legend(loc='upper left', fontsize=8)
    ax.set_box_aspect((1, 1, 1))
    profile = fig.add_subplot(122)
    profile.scatter(np.asarray(obs['pixels'])[:, 1], data['depth_errors_mm'], s=25, color='#d25c30')
    profile.axhline(0, color='#64748b', linewidth=1)
    profile.set(xlabel='Image row (pixels)', ylabel='Reconstructed minus reference depth (mm)',
                title='Held-out position: systematic depth bias', ylim=(-2, 16))
    profile.grid(alpha=.15)
    profile.text(.04, .94, 'Depth RMSE: 11.02 mm\nSigned bias: +10.91 mm\nUnchanged-pose repeat bias: +11.02 mm',
                 transform=profile.transAxes, va='top', fontsize=11,
                 bbox=dict(facecolor='#f1f5f9', edgecolor='none', pad=10))
    fig.suptitle('Preliminary 3D reconstruction — frozen plane tested at a new board position', fontsize=16, y=.98)
    fig.text(.5, .035, 'APS stripe reconstruction • 39 correlated row points from one pose • shared camera calibration and reported 18 mm target scale\nNo test alignment or model refit • reference is not independent absolute ground truth • full-object/event reconstruction pending',
             ha='center', fontsize=9, color='#475569')
    fig.subplots_adjust(top=.86, bottom=.2, left=.025, right=.98, wspace=.2)
    output = Path('outputs/presentation/preliminary_reconstruction_20261102')
    output.mkdir(parents=True, exist_ok=False)
    fig.savefig(output/'preliminary_reconstruction.png', dpi=200)
    fig.savefig(output/'preliminary_reconstruction.pdf')
    (output/'SPEAKER_NOTES.md').write_text('''# Preliminary reconstruction result

“We calibrated a static laser plane from stripe observations at two board poses, then froze that model and reconstructed a stripe at a new board position. This held-out check produced 11.02 mm depth RMSE and +10.91 mm bias against the camera-posed checkerboard. An unchanged-pose repeat gave +11.02 mm bias, suggesting a repeatable discrepancy at this position. The cause remains unresolved. Our next step is to check mechanical rigidity and calibration generalisation before evaluating sweep speed and attenuation.”

This is actual APS stripe data and ray–plane reconstruction, not a full object scan or an event-based performance result. The 39 row points are correlated, not 39 experimental repeats. The posed-board reference shares camera intrinsics and reported 18 mm target scale; independent absolute accuracy is unestablished. The observed error is a limitation to report, not a demonstrated acceptable specification. Do not subtract a constant bias or refit the test set and claim held-out success.

Source: outputs/calibration/static_plane1500_C_validation_20261102_01/validation.json. Repeat: outputs/calibration/static_plane1500_C_repeat_20261102_01/validation.json. Regenerate with .venv/Scripts/python.exe -m scripts.plot_preliminary_reconstruction into a new output directory (script refuses overwrite).
''', encoding='utf-8')
    print(output.resolve())


if __name__ == '__main__':
    main()
