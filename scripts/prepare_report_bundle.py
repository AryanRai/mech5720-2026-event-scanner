"""Assemble a versioned ICCP source bundle from verified retained project evidence."""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile
import csv
import cv2
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root=Path('.');out=root/'outputs/report/iccp_draft_20261103_01';out.mkdir(parents=True,exist_ok=False)
(out/'figures').mkdir();(out/'evidence').mkdir();(out/'template_original').mkdir()
template=Path('C:/Users/buzza/Downloads/5720_Project_Report.zip');z=zipfile.ZipFile(template)
for name in ['IEEEtran.cls','iccp26_template.tex','references.bib']:
    destination=out/name if name=='IEEEtran.cls' else out/'template_original'/name
    destination.write_bytes(z.read(name))
shutil.copy2(template,out/'template_original/5720_Project_Report.zip')
figures={
 'printed_mounts.jpg':'outputs/presentation/talk_photos_build/assets/printed_mounts.jpg',
 'assembled_rig.jpg':'outputs/presentation/talk_photos_build/assets/assembled_rig.jpg',
 'stripe_on_shoe.jpg':'outputs/presentation/talk_photos_build/assets/laser_stripe_shoe.jpg',
 'coverage.png':'outputs/coverage/shoe_image_coverage_20261103_01/image_coverage.png',
 'board_comparison.png':'outputs/calibration/static_event_aps_board_D_20261103_01/board_event_aps.png',
 'repeatability.png':'outputs/reconstruction/shoe_static_repeatability_20261103_03/repeatability.png',
 'timing.png':'outputs/timing/static_repeat_pulses_20261103_01/timing_prediction.png',
 'nd_comparison.png':'outputs/attenuation/nd_retry_repeats_20261103_01/filter_comparison.png',
 'dashboard.jpg':'outputs/presentation/talk_photos_build/assets/dashboard.jpg'}
for name,source in figures.items():shutil.copy2(source,out/'figures'/name)
for letter in 'ABCD':shutil.copy2(f'outputs/agent_control/dense_board_{letter}_ref_20261103_01/aps.png',out/'figures'/f'pose_{letter}.png')
sources=[
 'outputs/calibration/take06_refined_20261102/refined_intrinsics.json',
 'outputs/calibration/dense_planes_ABC_20261103_01/planes.json',
 'outputs/calibration/dense_planes_D_validation_20261103_01/validation.json',
 'outputs/calibration/static_event_aps_board_D_20261103_01/validation.json',
 'outputs/reconstruction/static_event_aps_20261103_02/comparison.json',
 'outputs/reconstruction/shoe_static_repeatability_20261103_03/repeatability.json',
 'outputs/coverage/shoe_image_coverage_20261103_01/coverage.json',
 'outputs/attenuation/nd_retry_repeats_20261103_01/comparison.json',
 'outputs/timing/static_repeat_pulses_20261103_01/audit.json']
evidence={}
for i,source in enumerate(sources,1):
    dest=out/'evidence'/f'{i:02d}_{Path(source).name}';shutil.copy2(source,dest)
    evidence[source]=dict(bundle_file=dest.name,sha256=hashlib.sha256(Path(source).read_bytes()).hexdigest())
manifest=dict(template=str(template),template_sha256=hashlib.sha256(template.read_bytes()).hexdigest(),
    figures={name:dict(source=source,sha256=hashlib.sha256(Path(source).read_bytes()).hexdigest()) for name,source in figures.items()},evidence=evidence,
    source_scope='Existing measured data only. No hardware operation, fabricated results or project/account publication performed by report assembly.')
(out/'evidence/source_manifest.json').write_text(json.dumps(manifest,indent=2))
# Equal-axis physical-coordinate plots from actual retained points.
with Path('outputs/reconstruction/shoe_further2_20261103_02_roi/points.csv').open() as f:aps=list(csv.DictReader(f))
with Path('outputs/reconstruction/static_event_aps_20261103_02/event_points.csv').open() as f:events=[r for r in csv.DictReader(f) if float(r['window_ms'])==50]
arrays=[np.array([[float(r[k]) for k in ['X_mm','Z_mm','Y_mm']] for r in rows]) for rows in [aps,events]]
combined=np.concatenate(arrays);low=combined.min(axis=0);high=combined.max(axis=0)
fig=plt.figure(figsize=(9,4.2))
for i,(name,a) in enumerate(zip(['APS:960 points','Static events:494 points'],arrays),1):
    ax=fig.add_subplot(1,2,i,projection='3d');ax.scatter(a[:,0],a[:,1],-a[:,2],s=4,c=a[:,1],cmap='viridis',vmin=low[1],vmax=high[1])
    ax.set(xlabel='X (mm)',ylabel='Z (mm)',zlabel='-Y (mm)',title=name,xlim=(low[0],high[0]),ylim=(low[1],high[1]),zlim=(-high[2],-low[2]))
    ax.set_box_aspect(np.maximum(high-low,1));ax.view_init(elev=24,azim=-62)
fig.tight_layout();fig.savefig(out/'figures/paired_clouds.pdf');plt.close(fig)
print(out.resolve())
