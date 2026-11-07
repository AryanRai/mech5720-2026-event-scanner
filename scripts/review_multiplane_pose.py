"""Exploratory full-board stripe screening for the compact multicommand target."""
import json
from pathlib import Path
import cv2
import dv_processing as dv
import numpy as np
from scripts.fit_static_plane import corners


def main():
    folder=Path('outputs/calibration/multiplane_A2_screen_20261103_01')
    folder.mkdir(parents=True,exist_ok=False)
    before=Path('outputs/agent_control/multiplane_A2_ref_20261103_01/aps.png')
    after=Path('outputs/agent_control/multiplane_A2_after_20261103_01/aps.png')
    c,diagnostic=corners(cv2.imread(str(before),0)); b,_=corners(cv2.imread(str(after),0))
    if np.linalg.norm(c-b[::-1],axis=1).mean()<np.linalg.norm(c-b,axis=1).mean(): b=b[::-1]
    motion=float(np.linalg.norm(c-b,axis=1).max())
    hull=np.zeros((180,240),np.uint8)
    cv2.fillConvexPoly(hull,cv2.convexHull(c.astype(np.float32)).astype(np.int32),1)
    hull=cv2.dilate(hull,np.ones((13,13),np.uint8))>0
    results=[]
    for command in sorted([1520,1536,1553,1569,1585,1602,1618,1634,1651,1667]):
        run=f'multiplane_A2_{command}_20261103_01'
        raw=Path('data/raw')/(run+'.aedat4')
        trace_path=Path('outputs/static_checks')/run/'summary.json'
        if not raw.exists() or not trace_path.exists():
            results.append(dict(command_us=command,status='NOT_ACQUIRED')); continue
        trace=json.loads(trace_path.read_text())
        if trace['errors']:
            results.append(dict(command_us=command,status='REFUSED_NO_OBSERVATION',trace_errors=trace['errors'])); continue
        reader=dv.io.MonoCameraRecording(str(raw)); frames=[]
        while True:
            frame=reader.getNextFrame()
            if frame is None: break
            frames.append(frame.image.copy())
        reference=np.median(np.stack(frames[:3]),axis=0)
        perrow={}; selected=[]; clips=[]; peaks=[]
        for i,frame in enumerate(frames):
            delta=frame.astype(float)-reference
            mask=(delta>40)&(frame>60)&hull
            column=int(mask.sum(axis=0).argmax())
            mask[:,:max(0,column-8)]=False;mask[:,column+9:]=False
            yy,xx=np.where(mask)
            if len(np.unique(yy))<15 or np.ptp(yy)<40: continue
            selected.append(i); clips.append(float(np.mean(frame[mask]>=250)))
            peaks.append(float(delta[mask].mean()))
            for y in np.unique(yy):
                x=np.flatnonzero(mask[y]);perrow.setdefault(int(y),[]).append(float(np.average(x,weights=delta[y,x])))
        pixels=[(float(np.median(v)),y) for y,v in sorted(perrow.items()) if len(v)>=len(selected)/2]
        trace=json.loads((Path('outputs/static_checks')/run/'summary.json').read_text())
        results.append(dict(command_us=command,recording=str(raw),qualifying_frame_count=len(selected),
                            frames=selected,pixels=pixels,screened_clipping_max=max(clips,default=None),
                            feedback_warning=trace['feedback_screen_warning'],trace_errors=trace['errors'],
                            status='CANDIDATE_REQUIRES_GEOMETRY_REVIEW' if len(selected)>=5 and len(pixels)>=15 and max(clips,default=1)<=.01 and motion<=.5 else 'SCREEN_REJECTED'))
    result=dict(board_before=str(before),board_after=str(after),corner_diagnostic=diagnostic,board_motion_max_px=motion,
                detector='Exploratory compact-board screen developed after first1667 capture: expandedinnercorner hull13px; delta>40 APS>60; dominantcolumn+/-8;>=15litrows span>=40px, >=5frames, <=1%clipping. Frozen for subsequentposeanalysis; not detectorprecision validation.',
                observations=results,limitation='One boardpose only. No laserplanes fitted. Correlatedframes/rows not independentrepeat trials. Candidatepixels need ray-board geometry/physicalextent screening before fit. Oldscreen retained separately.')
    (folder/'screen.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(dict(board_motion_max_px=motion,results=[{k:r.get(k) for k in ('command_us','qualifying_frame_count','screened_clipping_max','status','feedback_warning')} for r in results]),indent=2))


if __name__=='__main__':main()
