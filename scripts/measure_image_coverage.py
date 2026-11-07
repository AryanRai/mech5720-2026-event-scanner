"""Fixed photo-mask image-space sample coverage, NOT3D surface completeness."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import cv2
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def occupancy(pixels,shape):
    """Rasterise each finite centre to nearest native bin; duplicate hits count once."""
    result=np.zeros(shape,np.uint8);pixels=np.asarray(pixels,float).reshape(-1,2)
    finite=np.isfinite(pixels).all(axis=1);p=np.floor(pixels[finite]+.5).astype(int)
    valid=(p[:,0]>=0)&(p[:,0]<shape[1])&(p[:,1]>=0)&(p[:,1]<shape[0])
    p=p[valid];result[p[:,1],p[:,0]]=1
    return result,dict(input_centres=len(pixels),nonfinite_centres=int((~finite).sum()),out_of_image_centres=int((~valid).sum()))


def disk(radius):
    y,x=np.mgrid[-radius:radius+1,-radius:radius+1]
    return (x*x+y*y<=radius*radius).astype(np.uint8)


def coverage(mask,occupied,radius=0):
    measured=cv2.dilate(occupied,disk(radius)) if radius else occupied
    denominator=int(np.count_nonzero(mask));numerator=int(np.count_nonzero((mask>0)&(measured>0)))
    return dict(covered_native_pixels=numerator,expected_mask_native_pixels=denominator,
                coverage_percent=100*numerator/denominator if denominator else None,
                support_radius_px=radius)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--mask',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    definition=json.loads(args.mask.read_text());photo=Path(definition['source_photo'])
    assert hashlib.sha256(photo.read_bytes()).hexdigest()==definition['source_photo_sha256']
    image=cv2.imread(str(photo),0);mask=np.zeros(image.shape,np.uint8)
    cv2.fillPoly(mask,[np.array(definition['polygon_xy'],np.int32)],1)
    shared=mask.copy();shared[:20]=0;shared[106:]=0
    args.output.mkdir(parents=True,exist_ok=False)
    sources={'APS':Path('outputs/reconstruction/shoe_further2_20261103_02_roi/points.csv'),
             'Events':Path('outputs/reconstruction/static_event_aps_20261103_02/event_points.csv')}
    results=[];arrays={};rasters={}
    for method,source in sources.items():
        with source.open(newline='') as f:rows=list(csv.DictReader(f))
        if method=='Events':rows=[r for r in rows if float(r['window_ms'])==50]
        pixels=np.array([[float(r['pixel_x']),float(r['pixel_y'])] for r in rows])
        occupied,screen=occupancy(pixels,image.shape);arrays[method]=pixels;rasters[method]=occupied
        integer=np.floor(pixels+.5).astype(int)
        valid=(integer[:,0]>=0)&(integer[:,0]<image.shape[1])&(integer[:,1]>=0)&(integer[:,1]<image.shape[0])
        inside=int(sum(bool(mask[y,x]) for x,y in integer[valid]))
        boundary=[]
        for radius in [1,2]:
            for change,changed in [('eroded',cv2.erode(mask,disk(radius))),('dilated',cv2.dilate(mask,disk(radius)))]:
                boundary.append(dict(mask_change=change,boundary_radius_px=radius,**coverage(changed,occupied)))
        results.append(dict(method=method,source=str(source),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            retained_centres=len(pixels),centres_inside_body_mask=inside,centres_outside_body_mask=len(pixels)-inside,
            unique_observed_bins_whole_image=int(occupied.sum()),screen=screen,
            whole_body=coverage(mask,occupied),shared_processing_rows=coverage(shared,occupied),
            boundary_sensitivity=boundary,
            footprint_tolerance_sensitivity=[coverage(mask,occupied,r) for r in [1,2]],
            note='Radius0 is primary measured native-bin coverage. Radius1/2 figures are tolerance-footprint sensitivity, not additional measured points or interpolated3D.'))
    limitation=('Image-space sample coverage of the visible main shoe body, not physical3D surface-area completeness, accuracy, recognisability or unseen-side coverage. '
        'Denominator is a manually outlined fixed native240x180photo mask; excludes loose laces above the main body and background/stand. '
        'Mask is approximate and post-acquisition, not independently labelled or preregistered. Same mask for APS/events. '
        'Primary numerator is unique rounded native pixel bins containing retained stripe centres; duplicates do not inflate coverage. '
        'One acquisition per static command; correlated pixels/events are not independent repeats. '
        'Original20positions/35msAPS frames and50ms event ON+OFF windows use unequal temporal integration and detector screens. '
        'No alignment, depth filtering, fitted surface, gap filling or mesh. Old shoe placement only; not the later repositioned/ND scene. '
        'Both methods were processed only on rows20..105; full-body denominator retains the excluded lower-body region to expose unsampled portions. '
        'Coverage does not certify that candidates are true laser detections; independent3D groundtruth/completeness remains pending.')
    output=dict(status='FIXED_MASK_IMAGE_SPACE_SAMPLE_COVERAGE',mask_definition=str(args.mask),mask_sha256=hashlib.sha256(args.mask.read_bytes()).hexdigest(),
        photo=str(photo),photo_sha256=definition['source_photo_sha256'],results=results,limitations=limitation)
    (args.output/'coverage.json').write_text(json.dumps(output,indent=2))
    cv2.imwrite(str(args.output/'shoe_body_mask.png'),mask*255);cv2.imwrite(str(args.output/'shared_rows_mask.png'),shared*255)
    fig,axes=plt.subplots(1,2,figsize=(12,5))
    for ax,r in zip(axes,results):
        ax.imshow(image,cmap='gray',vmin=0,vmax=255);ax.contour(mask,levels=[.5],colors=['#ff8a25'],linewidths=1)
        pixels=arrays[r['method']];ax.scatter(pixels[:,0],pixels[:,1],s=4,c='#00c9f2',marker='s')
        ax.set_xlim(0,239);ax.set_ylim(179,0);ax.set_title(f"{r['method']}: {r['whole_body']['coverage_percent']:.2f}% native-bin coverage")
        ax.set(xlabel='Native pixel x',ylabel='Native pixel y')
    fig.suptitle('Fixed visible-shoe-body mask; image-space samples, not3D surface completeness')
    fig.tight_layout();fig.savefig(args.output/'image_coverage.png',dpi=170);plt.close(fig)
    lines=['# Fixed-mask image-space sample coverage','',limitation,'',
        '| Method | Retained centres | Centres inside mask | Unique covered body bins | Fixed body denominator | Image-space coverage | Same-processing-row coverage |',
        '|---|---|---|---|---|---|---|']
    for r in results:
        m=r['whole_body'];lines.append(f"| {r['method']} | {r['retained_centres']} | {r['centres_inside_body_mask']} | {m['covered_native_pixels']} | {m['expected_mask_native_pixels']} | {m['coverage_percent']:.3f}% | {r['shared_processing_rows']['coverage_percent']:.3f}% |")
    lines+=['','## Mask boundary sensitivity','',
        '| Method | Mask change | Boundary radius (px) | Coverage |','|---|---|---|---|']
    for r in results:
        for q in r['boundary_sensitivity']:lines.append(f"| {r['method']} | {q['mask_change']} | {q['boundary_radius_px']} | {q['coverage_percent']:.3f}% |")
    lines+=['','Tolerance footprint radius1/2 results are retained separately in coverage.json. They must not be reported as extra reconstructed surface.','',
        'Reproduce with repository Python and a new output directory:',
        '```powershell',f'.venv/Scripts/python.exe -m scripts.measure_image_coverage --mask {args.mask.as_posix()} --output outputs/coverage/NEW_DIRECTORY','```']
    (args.output/'REVIEW.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps([dict(method=r['method'],whole_body=r['whole_body'],shared_processing_rows=r['shared_processing_rows']) for r in results],indent=2))


if __name__=='__main__':main()
