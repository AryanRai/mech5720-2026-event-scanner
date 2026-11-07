"""Write evidence summary/register entries from actual retained result manifests."""
import csv
import hashlib
import json
from pathlib import Path
import urllib.request
from datetime import datetime,timezone

root=Path('.')
eventdir=Path('outputs/reconstruction/static_event_aps_20261103_02')
repeatdir=Path('outputs/reconstruction/shoe_static_repeatability_20261103_03')
boarddir=Path('outputs/calibration/static_event_aps_board_D_20261103_01')
timedir=Path('outputs/timing/static_repeat_pulses_20261103_01')
event=json.loads((eventdir/'comparison.json').read_text());repeat=json.loads((repeatdir/'repeatability.json').read_text());board=json.loads((boarddir/'validation.json').read_text());timing=json.loads((timedir/'audit.json').read_text())
with urllib.request.urlopen('http://127.0.0.1:8933/rig/status',timeout=4) as response:rig=json.load(response)
with urllib.request.urlopen('http://127.0.0.1:8931/status',timeout=4) as response:camera=json.load(response)
assert rig['fresh'] and not rig['active'] and not rig['controller']['laser'] and not rig['controller']['armed']
session=Path('outputs/static_checks/shoe_repeat_session_20261103_02')
register=Path('EXPERIMENT_RUN_REGISTER.csv')
with register.open(newline='',encoding='utf-8-sig') as f:reader=csv.DictReader(f);fields=reader.fieldnames;existing={r['run_id'] for r in reader}
rows=[]
for r in json.loads((session/'runs_with_correction.json').read_text()):
    if r['run_id'] in existing:continue
    row=dict.fromkeys(fields,'');d=Path('outputs/static_checks')/r['run_id']
    row.update(run_id=r['run_id'],block='P5/P6',status='completed_static_repeat' if r['command_us']!=1627 else 'retained_unfitted_command_no_depth',
        condition_id='shoe_repositioned_static_repeat',firmware_version='1.7',actual_exposure_ms=35,servo_min_us=r['command_us'],servo_max_us=r['command_us'],
        raw_aedat4_path=str(Path('data/raw')/(r['run_id']+'.aedat4')),feedback_log_path=str(d/'samples.csv'),status_log_path=str(d/'operation.json'),processed_output_path=str(repeatdir),
        notes=f"Acquisition repeat{r['repeat']}; stationary new shoe placement, frozenABC; events50ms ON/OFF, APS35ms lit frames; no independent accuracy;1627 excluded from depth; finaloff/disarm/release")
    rows.append(row)
with register.open('a',newline='',encoding='utf-8') as f:csv.DictWriter(f,fields).writerows(rows)
lines=['# Automated static results — 3 November 2026','',
    'This update supersedes earlier statements that no event-based3D or static event/APS comparison has been attempted. Continuous moving-stripe3D, independent absolute accuracy, calibrated servo angles, full-surface completeness, sweep-speed and ND performance remain unestablished.','',
    '## Saved-data static event reconstruction','',
    'Twenty existing shoe recordings were processed with event-only spatial extraction. The known1s pulse duration selects ON/OFF temporal candidates; no APS stripe mask guides event coordinates. The primary50ms window is exploratory, developed on these saved data. Both transition windows are used, so total event observation is100ms. APS pools selected lit frames at35ms exposure; no equal integration-time or speed claim.','',
    '| Event window per transition (ms) | Retained points | Contributing positions | Shared APS rows | x disagreement RMS (px) | Z disagreement RMS (mm) |','|---|---|---|---|---|---|']
for q in event['summary']:lines.append(f"| {q['window_ms']} | {q['points']} | {q['contributing_positions']} | {q['shared_aps_rows']} | {q['pixel_disagreement_rms']:.3f} | {q['depth_disagreement_rms_mm']:.3f} |")
lines+=['','All three settings retained0 corroborated row candidates over3440 sampled laser-off command-row opportunities. This is an internal temporal control, not a labelled false-positive study. Agreement with APS is not ground-truth accuracy. No full-surface completeness claim.','',
    f'Evidence: [{eventdir}/REVIEW.md]({eventdir}/REVIEW.md), comparison.json, event_points.csv, paired_disagreement.csv, stripe_comparison.png and event_reconstruction.png.','',
    '## Saved reserved-board comparison','',
    f"On339 shared command-row pairs over19 commands, equal-command common-row RMS against the posed board is **{board['summary']['Events']['equal_command_common_row_depth_rms_mm']:.2f}mm for events** and **{board['summary']['APS']['equal_command_common_row_depth_rms_mm']:.2f}mm for APS**. One command has no common retained rows. Both use the frozenABC planes and camera model; no refit/alignment. The reference is one reserved board pose with sharedK and reported18mm scale, not independent absolute ground truth. Detector temporal integration differs; these close values do not establish an event advantage. These are a different subset from the earlier8.63mm APS result. Do not replace denominators silently.",'',
    f'Evidence: {boarddir}/validation.json and board_event_aps.png.','',
    '## New repeated acquisitions','',
    'The user moved the shoe before the sequence. Its new position defines a separate condition; old shoe recordings are not repeat trials. Three acquisitions were completed at each fitted command1569,1590,1602,1626,1647us. An initial1627 command-selection error produced three records with no fitted plane; all retained, excluded from depth, and followed by three explicitly documented1626 correction captures. The protocol/correction record and original logs remain. An earlier interrupted session01 contains two completed pilots; its third attempt was refused before action. It is not included in repeat metrics.','',
    'Matched-support precision below uses the same rows in BOTH methods and all3 acquisitions. At each row compute sample SD of Z across3 acquisitions (ddof1), then root mean row variance within each command. Rows are correlated, not extra repeats; common-support selection favours detectable regions.','',
    '| Command (µs) | Common rows across both methods/all3 | APS repeatability (mm) | Event repeatability (mm) |','|---|---|---|---|']
for q in repeat['matched_support_stats']:lines.append(f"| {q['command_us']} | {q['common_rows_both_methods_all_three']} | {q['APS_depth_repeatability_mm']:.3f} | {q['Events_depth_repeatability_mm']:.3f} |")
lines+=['','No consistent winner across commands. APS retains more image rows with these methods/settings; event screening is stricter and temporal integration differs. Treat these as scene-stripe repeatability because the fixed rowROI may include background/target crossings after shoe repositioning.504 APS model-derived depths fall outside command-specific trainingZ ranges; none deleted. This is a range warning, not a ground-truth error. Full per-acquisition support/range checks and feedback warnings are retained.','',
    f"Before/after image phase-correlation shift is {repeat['reference_stability']['phase_correlation_shift_xy_px']}px, response{repeat['reference_stability']['response']:.4f}; no alignment applied. This supports image stability, not proof of a perfectly fixed optical plane.",'',
    f'Evidence: {repeatdir}/repeatability.json, row_repeatability.csv, points.csv, repeatability.png; acquisition protocol/logs in {session}.','',
    '## Fresh static pulse timing audit','',
    f"Fit an affine clock model to5 first-passON markers. Ten laterON predictions have RMS{timing['summary']['reserved_ON']['rms_ms']:.2f}ms and maximum absolute residual{timing['summary']['reserved_ON']['max_absolute_ms']:.2f}ms. FifteenOFF markers have RMS{timing['summary']['all_OFF']['rms_ms']:.2f}ms and maximum{timing['summary']['all_OFF']['max_absolute_ms']:.2f}ms. These include event peak/median selection, optical/polarity response and possible clock-model error; they are not isolated hardware latency or absolute timing uncertainty. Do not use this model for validated continuous reconstruction. Resets invalidate mappings.",'',
    f'Evidence: {timedir}/audit.json and timing_prediction.png.','',
    '## Reproduce offline','',
    'Use repository .venv/Scripts/python.exe and new output directories; no serial/camera ownership required for analysis.','',
    '```powershell',
    '.venv/Scripts/python.exe -m scripts.compare_static_events_aps --output outputs/reconstruction/NEW_event_compare',
    '.venv/Scripts/python.exe -m scripts.validate_static_events_board_d --output outputs/calibration/NEW_event_board',
    '.venv/Scripts/python.exe -m scripts.analyse_static_shoe_repeats --session outputs/static_checks/shoe_repeat_session_20261103_02 --output outputs/reconstruction/NEW_repeatability',
    '.venv/Scripts/python.exe -m scripts.audit_repeat_pulse_timing --output outputs/timing/NEW_pulse_audit',
    '.venv/Scripts/python.exe -m pytest tests/test_static_event_comparison.py -q','```','',
    'Four focused synthetic tests passed: event centroid/polarity, positive/negative ray-plane geometry, known-duration pulse pairing with early motion, finite board intersection/reference depth. No full-suite claim.','',
    'Final fresh service status: no active rig operation, laser off/disarmed, servo released in finalSTOP trace; camera live manual35ms, no recording. No lens/mount/firmware change, new ND hardware or physical target measurement was performed.','',
    'Next physical inputs needed for independent accuracy or attenuation: a measured matte reference/step target and documented ND levels. Continuous timing/motion needs further validation; no broad camera retake is indicated by this work.']
Path('AUTOMATED_STATIC_RESULTS_20261103.md').write_text('\n'.join(lines),encoding='utf-8')
handoff=Path('PROJECT_HANDOFF_CURRENT.md');prior=handoff.read_text(encoding='utf-8')
prefix='NEWEST 3Nov automated static evidence: read AUTOMATED_STATIC_RESULTS_20261103.md first. Static event candidate3D now exists:494points/20positions at50ms ON/OFF; shared455APSrows disagreement1.65mm (not accuracy). ReservedD common339rows/19commands event8.07mm vsAPS8.42mm, sharedK/scale, not event advantage. Fresh3acquisitions x5fittedcommands scene-repeatability in outputs/reconstruction/shoe_static_repeatability_20261103_03; user moved shoe BEFORE sequence, new condition. Original1627unfitted records retained and excluded;3additional1626captures used. Static pulse timing audit max~48ms prediction residual: continuous moving-event3D still unvalidated. Finaloff/disarm/release; camera35ms live not recording. Full report has logs/reproduction/limitations. Previous PPTXversion03 has NOT yet been updated with these new results; its no-event3D statements are superseded by this static preliminary evidence.\n\n'
if not prior.startswith(prefix):handoff.write_text(prefix+prior,encoding='utf-8')
files=[Path('scripts')/n for n in ['compare_static_events_aps.py','analyse_static_shoe_repeats.py','validate_static_events_board_d.py','audit_repeat_pulse_timing.py','run_static_shoe_repeats.py','correct_repeat_command.py']]
manifest=dict(created_utc=datetime.now(timezone.utc).isoformat(),model_sha256=event['model_sha256'],code_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
    final_controller=rig['controller'],camera={k:camera[k] for k in ['stale','actual_exposure_us','recording']},result_paths=[str(eventdir),str(repeatdir),str(boarddir),str(timedir)])
Path('outputs/reconstruction/automated_static_manifest_20261103.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps(dict(report='AUTOMATED_STATIC_RESULTS_20261103.md',registered_new_records=len(rows),final_laser=rig['controller']['laser'],final_armed=rig['controller']['armed'],camera_recording=camera['recording'])))
