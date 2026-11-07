"""Fit preliminary per-command planes using the disclosed compact-board screen."""
import hashlib
import csv
import json
from pathlib import Path
import cv2
import dv_processing as dv
import numpy as np
from scripts.fit_static_plane import corners, fit_plane, intersect_board

COMMANDS=[1520,1536,1569,1585,1602,1618,1634,1651,1667]


def extract(pose,command,matrix,distortion):
    prefix=pose if pose.startswith('dense_board_') else 'multiplane_'+pose
    before=Path('outputs/agent_control')/(prefix+('_ref_20261103_02' if pose=='D' else '_ref_20261103_01'))/'aps.png'
    after=Path('outputs/agent_control')/(prefix+('_after_20261103_02' if pose in ('dense_board_A','dense_board_B') else '_after_20261103_01'))/'aps.png'
    c,diagnostic=corners(cv2.imread(str(before),0));b,_=corners(cv2.imread(str(after),0))
    if np.linalg.norm(c-b[::-1],axis=1).mean()<np.linalg.norm(c-b,axis=1).mean():b=b[::-1]
    motion=float(np.linalg.norm(c-b,axis=1).max())
    if motion>.5:raise ValueError('Board moved >0.5px')
    obj=np.zeros((54,3));obj[:,:2]=np.mgrid[0:9,0:6].T.reshape(-1,2)*18
    ok,rv,tv=cv2.solvePnP(obj,c.astype(float),matrix,distortion)
    if not ok:raise ValueError('Pose failed')
    rotation=cv2.Rodrigues(rv)[0]
    projected=cv2.projectPoints(obj,rv,tv,matrix,distortion)[0].reshape(-1,2)
    reproj=float(np.sqrt(np.mean(np.sum((projected-c)**2,axis=1))))
    if reproj>.5:raise ValueError('Reprojection >0.5px')
    hull=np.zeros((180,240),np.uint8)
    cv2.fillConvexPoly(hull,cv2.convexHull(c.astype(np.float32)).astype(np.int32),1)
    hull=cv2.dilate(hull,np.ones((13,13),np.uint8))>0
    suffix='02' if pose=='E2' and command==1602 else '01'
    if pose=='dense_board_A':
        suffix='02' if command in (1594,1602) else '03' if command==1606 else '01'
    if pose=='dense_board_B' and command in (1631,1610):suffix='02'
    if pose=='dense_board_C' and command==1635:suffix='02'
    if pose=='dense_board_D' and command==1631:suffix='02'
    run=f'{prefix}_{command}_20261103_'+suffix
    raw=Path('data/raw')/(run+'.aedat4')
    tracepath=Path('outputs/static_checks')/run/'summary.json'
    trace=json.loads(tracepath.read_text())
    if trace['errors']:raise ValueError('Invalid trace')
    reader=dv.io.MonoCameraRecording(str(raw));frames=[]
    while True:
        frame=reader.getNextFrame()
        if frame is None:break
        frames.append(frame.image.copy())
    reference=np.median(np.stack(frames[:3]),axis=0)
    perrow={};selected=[];clips=[]
    for i,frame in enumerate(frames):
        delta=frame.astype(float)-reference
        mask=(delta>40)&(frame>60)&hull
        column=int(mask.sum(axis=0).argmax())
        mask[:,:max(0,column-8)]=False;mask[:,column+9:]=False
        yy,xx=np.where(mask)
        if len(np.unique(yy))<15 or np.ptp(yy)<40:continue
        selected.append(i);clips.append(float(np.mean(frame[mask]>=250)))
        for y in np.unique(yy):
            x=np.flatnonzero(mask[y]);perrow.setdefault(int(y),[]).append(float(np.average(x,weights=delta[y,x])))
    if len(selected)<5:raise ValueError('Fewer than5qualifyingframes')
    if max(clips)>.01:raise ValueError('Clipping >1%')
    pixels=np.array([(float(np.median(v)),y) for y,v in sorted(perrow.items()) if len(v)>=len(selected)/2])
    xyz=intersect_board(pixels,matrix,distortion,rotation,tv)
    local=(xyz-tv.ravel())@rotation
    inside=(local[:,0]>=-18)&(local[:,0]<=162)&(local[:,1]>=-18)&(local[:,1]<=108)
    if inside.sum()<15:raise ValueError('Fewerthan15onboardpoints')
    return dict(pose=pose,command_us=command,recording=str(raw),raw_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),
                board_before=str(before),board_after=str(after),board_motion_max_px=motion,
                corner_diagnostic=diagnostic,board_reprojection_rms_px=reproj,board_rvec=rv.ravel().tolist(),
                board_t_mm=tv.ravel().tolist(),board_normal=rotation[:,2].tolist(),
                selected_frames=selected,clipped_fraction_max=max(clips),pixels=pixels[inside].tolist(),
                points_camera_mm=xyz[inside].tolist(),lit_feedback=trace['phase_statistics']['lit_hold'],
                feedback_warning=trace['feedback_screen_warning']),xyz[inside]


def main():
    out=Path('outputs/calibration/multiplane_AB_20261103_01');out.mkdir(parents=True,exist_ok=False)
    intrpath=Path('outputs/calibration/take06_refined_20261102/refined_intrinsics.json')
    intr=json.loads(intrpath.read_text())['models']['primary_five_coefficient']
    matrix=np.array(intr['camera_matrix']);distortion=np.array(intr['distortion_coefficients'])
    results=[]
    for command in COMMANDS:
        try:
            a,pa=extract('A2',command,matrix,distortion);b,pb=extract('B',command,matrix,distortion)
            normal,offset,spread=fit_plane([pa,pb])
            results.append(dict(command_us=command,status='PRELIMINARY_TRAINING_FIT_NOT_VALIDATED',
                                normal_camera=normal.tolist(),offset_mm=offset,weighted_spread_mm=spread.tolist(),
                                training_orthogonal_rms_mm=[float(np.sqrt(np.mean((p@normal+offset)**2))) for p in (pa,pb)],
                                observations=[a,b]))
        except Exception as exc:results.append(dict(command_us=command,status='REJECTED',reason=str(exc)))
    result=dict(intrinsics=str(intrpath),planes=results,
                detector='Compactboard screen frozen afterA2 beforeB; delta>40 APS>60 expandedcornerhull13px dominantcolumn+/-8 >=15rows span40 >=5frames <=1%clipping; physicalboardextent screen. Exploratory/adaptive, not independentdetectorvalidation.',
                limitations='Two boardposes only, user18mm scale and candidateK shared. Trainingresidual is not depthaccuracy. ADCwarnings retained; mechanicalplane stability unresolved. Need reserved thirdboardpose beforeobjectdepth claims. No degrees or feedbacktoplaneinterpolation fitted; no continuoussweep validation.')
    path=out/'planes.json';path.write_text(json.dumps(result,indent=2))
    (out/'frozen_model.json').write_text(json.dumps(dict(planes_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),purpose='Frozenbeforethirdpose; no testrefit'),indent=2))
    lines=['# Preliminary multicommand planes, 3 November 2026','',
           'Separate static laser planes fitted at the commands below using two board poses. No third-pose validation yet. Training orthogonal residuals are not depth accuracy. The earlier1500held-out depth bias remains unresolved.','',
           '| Command (us) | Outcome | Training orthogonal RMS A/B (mm) |','|---|---|---|']
    for r in results:
        rms=r.get('training_orthogonal_rms_mm')
        lines.append(f"| {r['command_us']} | {r['status']} | {rms if rms else r.get('reason')} |")
    lines+=['',result['detector'],'',result['limitations'],'',
            'All source acquisitions are retained with camera sidecars, controller traces, warnings and final off/disarm/release. Nine positions captured in each pose;1553 first-pose request was refused and omitted from fitting. Board motion is measured between35ms reference snapshots. Planes.json is hash-frozen before a thirdboardpose.','',
            'Next: change only the board tilt or distance, keep camera/servo/laser/base fixed, and capture the same usable commands for model-fixed validation. Do not apply a constant11mm correction or refit the held-out points then claim test accuracy.']
    (out/'REVIEW.md').write_text('\n'.join(lines),encoding='utf-8')
    register=Path('EXPERIMENT_RUN_REGISTER.csv')
    with register.open(newline='',encoding='utf-8-sig') as f:
        reader=csv.DictReader(f);fields=reader.fieldnames;existing={r['run_id'] for r in reader}
    rows=[]
    for command in COMMANDS:
        run=f'multiplane_B_{command}_20261103_01';d=Path('outputs/static_checks')/run
        row=dict.fromkeys(fields,'')
        row.update(run_id=run,block='P3',status='second_board_pose_candidate',condition_id='multiplane_poseB',
                   firmware_version='1.7',actual_exposure_ms=10,servo_min_us=command,servo_max_us=command,
                   raw_aedat4_path=f'data/raw/{run}.aedat4',feedback_log_path=str(d/'samples.csv'),
                   status_log_path=str(d/'operation.json'),processed_output_path=str(out),
                   notes='Two-pose training only; warnings retained in manifest; finaloff/disarm/release; no heldoutdepthclaim')
        if run not in existing:rows.append(row)
    with register.open('a',newline='',encoding='utf-8') as f:csv.DictWriter(f,fields).writerows(rows)
    handoff=Path('PROJECT_HANDOFF_CURRENT.md');prior=handoff.read_text(encoding='utf-8')
    handoff.write_text('NEWEST Nov3 poseB ninecommands acquired, preliminarypercommandfits frozen in outputs/calibration/multiplane_AB_20261103_01/planes.json+frozen_model.json+REVIEW.md. Read percommand status; rejectedfits notusable. Two-boardpose training ONLY, no thirdposeaccuracy; ADCwarningsretained. SourceB_ref/after snapshots, allraw/manifests/registersaved. Need thirdBOARDpose withrigfixed to validatefrozenplanes; no fullobjectreconstruction yet. Existing1500~11mmtestbias remains. Finaloff/disarm/release35ms restored.\n\n'+prior,encoding='utf-8')
    print(json.dumps([dict(command_us=r['command_us'],status=r['status'],training_rms_mm=r.get('training_orthogonal_rms_mm'),reason=r.get('reason')) for r in results],indent=2))


if __name__=='__main__':main()
