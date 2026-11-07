"""Publication-size plots from retained numerical evidence; no hardware access."""
from pathlib import Path
import csv,json,shutil
import cv2
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

out=Path('outputs/report/iccp_draft_20261103_01');figdir=out/'figures'
plt.rcParams.update({'font.size':8,'axes.titlesize':8,'axes.labelsize':8,'xtick.labelsize':7,'ytick.labelsize':7,'legend.fontsize':7,'font.family':'DejaVu Serif','pdf.fonttype':42})
board=json.loads(Path('outputs/calibration/static_event_aps_board_D_20261103_01/validation.json').read_text())
fig,ax=plt.subplots(figsize=(3.35,2.05))
for method,color,marker in [('Events','#da5b17','o'),('APS','#087fb5','s')]:
 rows=[r for r in board['results'] if r['common_rows'][method]['depth_rmse_mm'] is not None]
 ax.plot([r['command_us'] for r in rows],[r['common_rows'][method]['depth_rmse_mm'] for r in rows],marker+'-',color=color,lw=.8,ms=2,label=method)
ax.set(xlabel='Command (µs)',ylabel='Depth RMS (mm)');ax.set_xticks([1569,1590,1610,1631,1647]);ax.grid(alpha=.2);ax.legend();fig.tight_layout(pad=.3);fig.savefig(figdir/'board_compact.pdf');plt.close(fig)
rep=json.loads(Path('outputs/reconstruction/shoe_static_repeatability_20261103_03/repeatability.json').read_text())
fig,ax=plt.subplots(figsize=(3.35,1.85))
for method,color in [('APS','#087fb5'),('Events','#da5b17')]:
 ax.plot([r['command_us'] for r in rep['matched_support_stats']],[r[method+'_depth_repeatability_mm'] for r in rep['matched_support_stats']],'o-',color=color,lw=.8,ms=3,label=method)
ax.set(xlabel='Command (µs)',ylabel='Repeatability (mm)');ax.set_xticks([1569,1590,1602,1626,1647]);ax.grid(alpha=.2);ax.legend();fig.tight_layout(pad=.3);fig.savefig(figdir/'repeat_compact.pdf');plt.close(fig)
t=json.loads(Path('outputs/timing/static_repeat_pulses_20261103_01/audit.json').read_text())
fig,ax=plt.subplots(figsize=(3.35,1.85))
for edge,color,marker in [('LASER_ON','#087fb5','o'),('LASER_OFF','#da5b17','x')]:
 rows=[r for r in t['edges'] if r['edge']==edge];ax.plot([r['controller_elapsed_us']/1e6 for r in rows],[r['prediction_residual_us']/1000 for r in rows],marker+'-',color=color,lw=.8,ms=2,label=edge.replace('LASER_',''))
ax.axhline(0,c='black',lw=.4);ax.set(xlabel='Controller elapsed time (s)',ylabel='Prediction residual (ms)');ax.legend();ax.grid(alpha=.2);fig.tight_layout(pad=.3);fig.savefig(figdir/'timing_compact.pdf');plt.close(fig)
with Path('outputs/reconstruction/shoe_further2_20261103_02_roi/points.csv').open() as f:aps=list(csv.DictReader(f))
with Path('outputs/reconstruction/static_event_aps_20261103_02/event_points.csv').open() as f:events=[r for r in csv.DictReader(f) if float(r['window_ms'])==50]
arrays=[np.array([[float(r[k]) for k in ['X_mm','Z_mm','Y_mm']] for r in rows]) for rows in [aps,events]];combined=np.concatenate(arrays);lo=combined.min(axis=0);hi=combined.max(axis=0)
fig=plt.figure(figsize=(6.8,2.75))
for i,(name,a) in enumerate(zip(['APS: 960 points','Static events: 494 points'],arrays),1):
 ax=fig.add_subplot(1,2,i,projection='3d');ax.scatter(a[:,0],a[:,1],-a[:,2],s=2,c=a[:,1],cmap='viridis',vmin=lo[1],vmax=hi[1]);ax.set(xlabel='X (mm)',ylabel='Z (mm)',zlabel='-Y (mm)',title=name,xlim=(lo[0],hi[0]),ylim=(lo[1],hi[1]),zlim=(-hi[2],-lo[2]));ax.set_box_aspect(np.maximum(hi-lo,1));ax.view_init(elev=24,azim=-62);ax.tick_params(pad=0,labelsize=6);ax.xaxis.labelpad=-1;ax.yaxis.labelpad=-1;ax.zaxis.labelpad=-1
fig.subplots_adjust(left=.02,right=.97,bottom=.13,top=.9,wspace=.0);fig.savefig(figdir/'paired_clouds.pdf',bbox_inches='tight',pad_inches=.06);plt.close(fig)
maskdef=json.loads(Path('outputs/coverage/shoe_mask_20261103_01/mask_definition.json').read_text());image=cv2.imread(maskdef['source_photo'],0);mask=np.zeros(image.shape,np.uint8);cv2.fillPoly(mask,[np.array(maskdef['polygon_xy'],np.int32)],1)
fig,axes=plt.subplots(1,2,figsize=(6.8,2.25))
for ax,name,rows in zip(axes,['APS: 6.85%','Events: 3.49%'],[aps,events]):
 p=np.array([[float(r['pixel_x']),float(r['pixel_y'])] for r in rows]);ax.imshow(image,cmap='gray',vmin=0,vmax=255);ax.contour(mask,levels=[.5],colors=['#ff8a25'],linewidths=.6);ax.scatter(p[:,0],p[:,1],s=1,c='#00c9f2',marker='s');ax.set_xlim(0,239);ax.set_ylim(130,20);ax.set_title(name);ax.axis('off')
fig.tight_layout(pad=.2);fig.savefig(figdir/'coverage_compact.pdf');plt.close(fig)
(out/'repro_data').mkdir();shutil.copy2('outputs/reconstruction/shoe_further2_20261103_02_roi/points.csv',out/'repro_data/aps_points.csv');shutil.copy2('outputs/reconstruction/static_event_aps_20261103_02/event_points.csv',out/'repro_data/event_points.csv');shutil.copy2(maskdef['source_photo'],out/'repro_data/shoe_photo.png');shutil.copy2('outputs/coverage/shoe_mask_20261103_01/mask_definition.json',out/'repro_data/mask_definition.json')
print('Rendered publication-size figures and retained minimal key-figure inputs.')
