"""Register retained multicommand captures and earlier positioning failures."""
import csv
import json
from pathlib import Path


def main():
    p=Path('EXPERIMENT_RUN_REGISTER.csv')
    with p.open(newline='',encoding='utf-8-sig') as f:
        reader=csv.DictReader(f);fields=reader.fieldnames;existing={r['run_id'] for r in reader}
    runs=[]
    for i in (1,2):
        runs.append((f'multiplane_A_obs1667_20261103_{i:02d}',f'multiplane_A_1667_20261103_{i:02d}',1667,
                     'recording_ended_before_light' if i==1 else 'stripe_outside_board'))
    for command in [1520,1536,1553,1569,1585,1602,1618,1634,1651,1667]:
        run=f'multiplane_A2_{command}_20261103_01'
        runs.append((run,run,command,'first_board_pose_candidate'))
    rows=[]
    for run,rawname,command,outcome in runs:
        d=Path('outputs/static_checks')/run
        if not (d/'summary.json').exists(): continue
        summary=json.loads((d/'summary.json').read_text())
        if summary['errors']:outcome='refused_before_observation'
        raw=Path('data/raw')/(rawname+'.aedat4')
        manifest=d/'manifest.json'
        if not manifest.exists():
            manifest.write_text(json.dumps(dict(run_id=run,camera=json.loads(raw.with_suffix('.json').read_text()),
                                               trace=summary,outcome=outcome),indent=2))
        row=dict.fromkeys(fields,'')
        row.update(run_id=run,block='P3',status=outcome,condition_id='multiplane_poseA',firmware_version='1.7',
                   actual_exposure_ms=10,servo_min_us=command,servo_max_us=command,
                   raw_aedat4_path=str(raw),feedback_log_path=str(d/'samples.csv'),
                   status_log_path=str(d/'operation.json'),processed_output_path=str(d),
                   notes='First board pose only; no plane fit. ADCwarning='+str(summary['feedback_screen_warning'])+'; finaloff/disarm/release')
        if run not in existing: rows.append(row)
    with p.open('a',newline='',encoding='utf-8') as f:csv.DictWriter(f,fields).writerows(rows)
    handoff=Path('PROJECT_HANDOFF_CURRENT.md');old=handoff.read_text(encoding='utf-8')
    handoff.write_text('NEWEST automated poseA2 acquired9commands1520,1536,1569,1585,1602,1618,1634,1651,1667us with12snativecapture/1sobserveeach at10ms;1553refuseddashboardbusy BEFOREobservation, darkcapture preserved, not replayed. Allraw/manifests/registerretained; feedbackwarningsmustremain. Refmultiplane_A2_ref_20261103_01 full54corners; aftermultiplane_A2_after_20261103_01; boardmotion/screen outputs/calibration/multiplane_A2_screen_20261103_01/screen.json. Compactboard newscreen exploratory/disclosed, oldscreen retained. ONEposeonly NOnewplanesfitted. EarlierA1667trial01missedlightwindow/trial02stripeoutsideboardretained. Nextphysical tiltBOARDonly~10-15deg withfull54visible; rigfixed; laserunplugduringtouch. Currentexposure35msrestored/offdisarmedreleased.\n\n'+old,encoding='utf-8')
    print('Registered',len(rows),'new runs')


if __name__=='__main__':main()
