"""Apply frozen shoe event settings to saved reserved board D; no hardware."""
import argparse
import hashlib
import json
from pathlib import Path
import cv2
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scripts.compare_static_events_aps import read_events,pulse_pair,event_rows,xyz


def evaluate(pixels,plane,obs,k,dist):
    if not len(pixels):return {},[]
    raysxy=cv2.undistortPoints(np.asarray(pixels,float).reshape(-1,1,2),k,dist).reshape(-1,2)
    rays=np.column_stack([raysxy,np.ones(len(raysxy))]);normal=np.array(obs['board_normal']);translation=np.array(obs['board_t_mm'])
    distances=normal@translation/(rays@normal);reference=rays*distances[:,None]
    rotation=cv2.Rodrigues(np.array(obs['board_rvec']))[0];local=(reference-translation)@rotation
    inside=(local[:,0]>=0)&(local[:,0]<=144)&(local[:,1]>=0)&(local[:,1]<=90)&(distances>0)
    pixels=np.asarray(pixels)[inside];reference=reference[inside]
    pred,valid=xyz(pixels,plane,k,dist);reference=reference[valid];pixels=pixels[valid]
    errors=pred[:,2]-reference[:,2]
    return dict(rows=len(errors),depth_rmse_mm=float(np.sqrt(np.mean(errors**2))) if len(errors) else None,
        signed_depth_bias_mm=float(np.mean(errors)) if len(errors) else None),[
            dict(pixel_x=float(q[0]),pixel_y=float(q[1]),estimated_Z_mm=float(z[2]),reference_Z_mm=float(r[2]),error_Z_mm=float(err))
            for q,z,r,err in zip(pixels,pred,reference,errors)]


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);args=p.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    mp=Path('outputs/calibration/dense_planes_ABC_20261103_01/planes.json');model=json.loads(mp.read_text());digest=hashlib.sha256(mp.read_bytes()).hexdigest()
    assert digest==json.loads((mp.parent/'frozen_model.json').read_text())['planes_sha256']
    planes={q['command_us']:q for q in model['planes'] if 'normal_camera' in q}
    intr=json.loads(Path(model['intrinsics']).read_text())['models']['primary_five_coefficient'];k=np.array(intr['camera_matrix']);dist=np.array(intr['distortion_coefficients'])
    validation=json.loads(Path('outputs/calibration/dense_planes_D_validation_20261103_01/validation.json').read_text())
    results=[]
    for r in validation['results']:
        if 'observation' not in r:continue
        command=r['command_us'];obs=r['observation'];raw=Path(obs['recording'])
        assert hashlib.sha256(raw.read_bytes()).hexdigest()==obs['raw_sha256']
        e=read_events(raw);on,off,pair=pulse_pair(e);a,_=event_rows(e,on,1,50);b,_=event_rows(e,off,0,50);lookup={int(q[1]):q[0] for q in b}
        events=np.array([q for q in a if int(q[1]) in lookup and abs(q[0]-lookup[int(q[1])])<=3]).reshape(-1,2)
        aps=np.array(obs['pixels']);aps=aps[(aps[:,1]>=20)&(aps[:,1]<=105)]
        em,ep=evaluate(events,planes[command],obs,k,dist);am,ap=evaluate(aps,planes[command],obs,k,dist)
        shared=set(q['pixel_y'] for q in ep)&set(q['pixel_y'] for q in ap)
        common={}
        for method,rows in [('Events',ep),('APS',ap)]:
            errors=[q['error_Z_mm'] for q in rows if q['pixel_y'] in shared]
            common[method]=dict(rows=len(errors),depth_rmse_mm=float(np.sqrt(np.mean(np.square(errors)))) if errors else None)
        results.append(dict(command_us=command,pair=pair,Events=em,APS=am,common_rows=common,event_measurements=ep,aps_measurements=ap,
            raw=str(raw),raw_sha256=obs['raw_sha256']))
    summary={}
    for method in ['Events','APS']:
        vals=[r['common_rows'][method]['depth_rmse_mm'] for r in results if r['common_rows'][method]['depth_rmse_mm'] is not None]
        summary[method]=dict(commands_with_shared_rows=len(vals),equal_command_common_row_depth_rms_mm=float(np.sqrt(np.mean(np.square(vals)))) if vals else None,
            total_retained_rows=sum(r[method].get('rows',0) for r in results),total_shared_rows=sum(r['common_rows'][method]['rows'] for r in results))
    limitations=('Reserved boardD excluded from plane fitting; event parameters developed on shoe data and applied unchanged here. D APS images/results had been inspected earlier, so this is not an untouched end-to-end test. '
        'Same per-command recordings/planes/K and rows20..105; only rays intersecting inner-corner board rectangle0..144 by0..90mm retained using existing board pose. '
        'APS uses previously retained board stripe pixels, events use ON/OFF corroborated50ms windows; temporal integration and detector screens differ. '
        'Common-row comparison restricts both methods to the same command/row pairs; can favour easy detections. '
        'One physical board pose, sharedK and reported18mm square scale; no independent absolute groundtruth, repeat uncertainty, refit, registration, speed or ND claim.')
    result=dict(model_sha256=digest,primary_window_ms=50,summary=summary,results=results,limitations=limitations)
    (args.output/'validation.json').write_text(json.dumps(result,indent=2))
    fig,ax=plt.subplots(figsize=(10,4.5))
    for method,color in [('Events','#e96b25'),('APS','#1685bc')]:
        valid=[r for r in results if r['common_rows'][method]['depth_rmse_mm'] is not None]
        ax.plot([r['command_us'] for r in valid],[r['common_rows'][method]['depth_rmse_mm'] for r in valid],'o-',label=method,color=color)
    ax.set(xlabel='Servo command (µs)',ylabel='Depth RMSE against posed board (mm)',title='Saved board D: event and APS errors on common rows');ax.legend();ax.grid(alpha=.2)
    fig.text(.5,.01,'One reserved pose; shared camera model/target scale. No refit or test alignment. Different temporal integration.',ha='center',fontsize=8)
    fig.tight_layout(rect=[0,.04,1,1]);fig.savefig(args.output/'board_event_aps.png',dpi=170);plt.close(fig)
    (args.output/'REVIEW.md').write_text('# Static event / APS reserved board comparison\n\n'+limitations+'\n\n'+json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
