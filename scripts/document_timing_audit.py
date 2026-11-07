"""Preserve current-session timing acquisition outcomes and limitations."""
import csv
import hashlib
import json
from pathlib import Path
import urllib.request


def main():
    audit=Path('outputs/timing/current_session_20261103_01')
    review='''# Optical timing check, 3 November 2026

Visible laser transitions provide a physical reference shared by native camera events and controller LASER_ON/OFF logs. Two ON markers separated by 775.44 seconds fitted an affine clock mapping; a third pulse was excluded from fitting. Its ON residual is +0.120 ms and OFF residual +3.4615 ms. The other OFF residuals are -2.5453/-2.4263 ms. Relative rate difference is 57.73 ppm, estimated optically, not an oscillator certification.

This supports automating optical marker alignment, but does not establish an absolute timing uncertainty bound or moving-plane depth accuracy. The upper-90-row APS-difference marker ROI and event-burst median are exploratory. Event 10–90 percent spreads of roughly3–9ms are event distributions, not confidence intervals. Threshold, polarity and laser response contribute delay. Fit points have zero residual by construction; no numerical pass threshold was preregistered. Mapping expires after controller reset or camera clock discontinuity. One reserved pulse cannot establish broad robustness.

Historical data also yielded marker alignment, but its offset was invalidated by the later reset. Sessions were analysed separately. Current first request targeted1500 while actual command1667: refused before arm/emission; dark camera recording retained. Distinct captures02/03 used1667 without commanded travel. Both12s recordings completed;02trace clean/noADCwarning;03trace clean with ADCwarning retained. Final off/disarmed/released. These are timing observations, not a1667plane calibration.

Next: automate fixed-command plane acquisition at multiple positions with at leasttwo boardposes and anotherreservedpose. Then test a short bounded continuous sweep with optical endpoint markers, feedback interpolation and held-out geometry. Existing scanCLI automates recording/control; its3D interpretation remains to validate. Physical user work is board mounting/repositioning and objectswap.

Reproduce with scripts/audit_optical_timing.py and scripts/audit_current_timing.py using newoutputdirectories. audit.json retains hashes, edges, mapping and diagnostic residuals. No new wiring/firmware was required.
'''
    (audit/'REVIEW.md').write_text(review,encoding='utf-8')
    controller=json.load(urllib.request.urlopen('http://127.0.0.1:8933/rig/status'))['controller']
    camera=json.load(urllib.request.urlopen('http://127.0.0.1:8931/status'))
    (audit/'final_status.json').write_text(json.dumps(dict(controller=controller,camera={k:camera[k] for k in ('recording','stale','actual_exposure_us')}),indent=2))
    register=Path('EXPERIMENT_RUN_REGISTER.csv')
    with register.open(newline='',encoding='utf-8-sig') as f:
        reader=csv.DictReader(f); fields=reader.fieldnames; existing={r['run_id'] for r in reader}
    rows=[]
    for index in (1,2,3):
        run=f'timing_observe_20261103_{index:02d}'
        d=Path('outputs/static_checks')/run
        raw=Path(f'data/raw/timing_marker_20261103_{index:02d}.aedat4')
        summary=json.loads((d/'summary.json').read_text())
        outcome='Refused current-command mismatch; no emission' if index==1 else 'Optical timing marker only; no depth calibration'
        manifest=dict(run_id=run,raw=str(raw),sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),
                      camera=json.loads(raw.with_suffix('.json').read_text()),trace=summary,
                      interpretation=outcome,timing_audit=str(audit),final_controller=controller)
        (d/'manifest.json').write_text(json.dumps(manifest,indent=2))
        row=dict.fromkeys(fields,'')
        row.update(run_id=run,block='P4',status='refused_no_emission' if index==1 else 'optical_timing_marker',
                   condition_id='timing_marker',firmware_version='1.7',actual_exposure_ms=35,
                   servo_min_us=1667,servo_max_us=1667,raw_aedat4_path=str(raw),
                   status_log_path=str(d/'operation.json'),processed_output_path=str(audit),
                   notes=outcome+'; ADCwarning='+str(summary['feedback_screen_warning'])+'; finaloff/disarm/release')
        if run not in existing: rows.append(row)
    with register.open('a',newline='',encoding='utf-8') as f: csv.DictWriter(f,fields).writerows(rows)
    handoff=Path('PROJECT_HANDOFF_CURRENT.md'); prior=handoff.read_text(encoding='utf-8')
    marker='NEWEST Nov3 optical timing audit completed.'
    if not prior.startswith(marker):
        handoff.write_text(marker+' Current-session ON2markers775sbaseline fit; reservedthirdONresidual+0.120ms/OFF+3.4615ms. Not absolute timingbound or continuousdepthvalidation. See outputs/timing/current_session_20261103_01/REVIEW.md+audit.json; historicalmappinginvalidafterreset. First1500observe refused actual1667, retaineddarkcapture;02/03distinct1667timingcapturescomplete,03ADCwarning retained. Finaloff/disarm/release35msfresh. No1667plane; geometrycalibrationneeded; canautomatepositions/captures. All3manifests/registersaved.\n\n'+prior,encoding='utf-8')
    print(json.dumps(dict(controller=controller,exposure_us=camera['actual_exposure_us'],recording=camera['recording']),indent=2))


if __name__=='__main__': main()
