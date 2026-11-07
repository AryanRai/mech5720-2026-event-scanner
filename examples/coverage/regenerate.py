"""Standalone regeneration of fixed-mask image-space coverage; run beside main.tex."""
from pathlib import Path
import csv,hashlib,json
import cv2
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root=Path(__file__).resolve().parent;data=root/'repro_data';out=root/'regenerated_key_figure';out.mkdir(exist_ok=False)
definition=json.loads((data/'mask_definition.json').read_text());photo=data/'shoe_photo.png'
assert hashlib.sha256(photo.read_bytes()).hexdigest()==definition['source_photo_sha256']
image=cv2.imread(str(photo),0);mask=np.zeros(image.shape,np.uint8);cv2.fillPoly(mask,[np.array(definition['polygon_xy'],np.int32)],1)
fig,axes=plt.subplots(1,2,figsize=(10,4));results=[]
for ax,method,filename in zip(axes,['APS','Events'],['aps_points.csv','event_points.csv']):
 with (data/filename).open() as f:rows=list(csv.DictReader(f))
 if method=='Events':rows=[r for r in rows if float(r['window_ms'])==50]
 p=np.array([[float(r['pixel_x']),float(r['pixel_y'])] for r in rows]);bins=np.floor(p+.5).astype(int);occupied=np.zeros(image.shape,np.uint8);occupied[bins[:,1],bins[:,0]]=1
 numerator=int(np.count_nonzero((mask>0)&(occupied>0)));denominator=int(mask.sum());percent=100*numerator/denominator
 results.append(dict(method=method,unique_covered_bins=numerator,fixed_mask_pixels=denominator,image_space_coverage_percent=percent))
 ax.imshow(image,cmap='gray',vmin=0,vmax=255);ax.contour(mask,levels=[.5],colors=['orange'],linewidths=1);ax.scatter(p[:,0],p[:,1],s=2,c='cyan',marker='s');ax.set_title(f'{method}: {numerator}/{denominator} = {percent:.2f}%');ax.set_xlim(0,239);ax.set_ylim(130,20);ax.axis('off')
fig.suptitle('Image-space sample coverage, not 3D surface completeness');fig.tight_layout();fig.savefig(out/'coverage.png',dpi=180);plt.close(fig)
(out/'coverage.json').write_text(json.dumps(results,indent=2));print(json.dumps(results,indent=2))
