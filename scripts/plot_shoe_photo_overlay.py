"""Overlay retained measured stripe coordinates on the laser-off shoe photograph."""
import hashlib
import json
from pathlib import Path
import shutil
import cv2
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    reconstruction=Path('outputs/reconstruction/dense_shoe_interpolated_20261103_02_sensitive')
    source=Path('outputs/agent_control/dense_shoe_photo_20261103_02/aps.png')
    same_exposure=Path('outputs/agent_control/dense_shoe_photo_20261103_01/aps.png')
    before=Path('outputs/agent_control/dense_shoe_ref_20261103_01/aps.png')
    out=Path('outputs/presentation/shoe_photo_overlay_20261103_01');out.mkdir(parents=True,exist_ok=False)
    image=cv2.imread(str(source),0)
    if image.shape!=(180,240):raise ValueError('Unexpected image coordinates')
    points=np.loadtxt(reconstruction/'points.csv',delimiter=',',skiprows=1)
    first=cv2.imread(str(before),0).astype(np.float32)
    last=cv2.imread(str(same_exposure),0).astype(np.float32)
    shift,response=cv2.phaseCorrelate(first,last)
    difference=np.abs(first-last)
    shutil.copyfile(source,out/'shoe_normal_100ms.png')
    shutil.copyfile(same_exposure,out/'shoe_normal_35ms.png')
    fig,axes=plt.subplots(1,2,figsize=(11,4.9))
    for ax in axes:
        ax.imshow(image,cmap='gray',vmin=0,vmax=255);ax.set_xlim(-.5,239.5);ax.set_ylim(179.5,-.5);ax.axis('off')
    axes[0].set_title('Laser-off DAVIS photograph (100 ms)')
    scatter=axes[1].scatter(points[:,1],points[:,2],c=points[:,5],cmap='turbo',s=5,alpha=.85,linewidths=0)
    axes[1].set_title('Retained stripe pixels coloured by estimated depth')
    fig.subplots_adjust(left=.025,right=.89,top=.86,bottom=.18,wspace=.08)
    cax=fig.add_axes([.92,.25,.017,.46]);fig.colorbar(scatter,cax=cax,label='Estimated camera Z (mm)')
    fig.suptitle('Shoe image and exploratory scan coverage',fontsize=15)
    fig.text(.5,.055,'1,929 retained stripe points • native pixel coordinates; no image warp or depth alignment\nInterpolated laser planes / unverified depth • coloured region shows sampled area, not full-object coverage',ha='center',fontsize=9)
    fig.savefig(out/'shoe_photo_and_overlay.png',dpi=200)
    plt.close(fig)
    fig,ax=plt.subplots(figsize=(7,5.25))
    ax.imshow(image,cmap='gray',vmin=0,vmax=255)
    ax.scatter(points[:,1],points[:,2],c=points[:,5],cmap='turbo',s=5,alpha=.8,linewidths=0)
    ax.axis('off');fig.subplots_adjust(0,0,1,1);fig.savefig(out/'shoe_depth_overlay.png',dpi=160)
    result=dict(photograph=str(source),photo_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                photograph_exposure_us=100000,comparison_photo_exposure_us=35000,
                points_csv=str(reconstruction/'points.csv'),points_sha256=hashlib.sha256((reconstruction/'points.csv').read_bytes()).hexdigest(),
                points=len(points),coordinate_mapping='Retained native stripe pixel_x/pixel_y directly; no scaling/warp/registration transform applied.',
                same_exposure_motion_diagnostic=dict(phase_correlation_shift_xy_px=list(shift),response=response,
                                                      absolute_difference_mean_levels=float(difference.mean()),
                                                      absolute_difference_p99_levels=float(np.percentile(difference,99))),
                limitations='Overlay uses the same observed stripe coordinates that generated the 3D points: useful provenance/coverage illustration, not independent geometric validation. Estimateddepth is provisional from unvalidated interpolatedplanes, sourcecalibrationerror, and objectdistanceoutsideobservedboardrange. Photograph100ms differs from3ms laserexposure. Only visible sampledregion reconstructed; no fullshoeclaim. Phasecorrelation is an image-stabilitydiagnostic, not independent calibration or a guarantee ofrigidity.')
    (out/'manifest.json').write_text(json.dumps(result,indent=2))
    (out/'README.md').write_text('# Shoe photograph and measured stripe overlay\n\nThe normal100ms laser-off photo is retained byte-for-byte as shoe_normal_100ms.png, alongside35ms sourcephoto. Overlay colours the1929retained measured native stripe coordinates by provisional reconstructedZ. No object/image alignment was applied. The side-by-side panel shows how little of the shoe is sampled and supports an honest partial-scan explanation.\n\nThis is not independentdepthvalidation: projectionback to inputpixels is inherent in ray-plane reconstruction. Show alongside the calibrationerrorplots and label exploratoryinterpolatedplanes. Reproduce with scripts/plot_shoe_photo_overlay.py into a newfolder.\n',encoding='utf-8')
    h=Path('PROJECT_HANDOFF_CURRENT.md');prior=h.read_text(encoding='utf-8')
    h.write_text('NEWEST normalshoeAPSphotos saved35ms+100ms (raw100msclearer), exposure35msrestored. Measurednativepixeloverlay1929points/provisionaldepth: outputs/presentation/shoe_photo_overlay_20261103_01/{shoe_normal_100ms.png,shoe_photo_and_overlay.png,shoe_depth_overlay.png,manifest.json,README.md}. NOwarp/depthalignment; illustratesprovenance/partialcoverage NOTindependentaccuracy. Sameexposurephasecorrelationdiagnostic saved. Laserremainedoff/disarmed.\n\n'+prior,encoding='utf-8')
    print(json.dumps(result['same_exposure_motion_diagnostic'],indent=2))


if __name__=='__main__':main()
