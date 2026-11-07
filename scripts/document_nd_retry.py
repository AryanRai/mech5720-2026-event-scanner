"""Record the repeated ND reinsertion experiment without overwriting earlier evidence."""
import csv
import hashlib
import json
from pathlib import Path
import urllib.request
from datetime import datetime,timezone

out=Path('outputs/attenuation/nd_retry_repeats_20261103_01');d=json.loads((out/'comparison.json').read_text())
register=Path('EXPERIMENT_RUN_REGISTER.csv')
with register.open(newline='',encoding='utf-8-sig') as f:reader=csv.DictReader(f);fields=reader.fieldnames;existing={r['run_id'] for r in reader}
rows=[]
for run in d['filtered_runs']:
    if run in existing:continue
    folder=Path('outputs/static_checks')/run;trace=json.loads((folder/'summary.json').read_text());assert not trace['errors']
    assert json.loads((Path('data/raw')/(run+'.json')).read_text())['status']=='complete'
    row=dict.fromkeys(fields,'');row.update(run_id=run,block='P8',status='completed_exploratory_filter_config_comparison',condition_id='unknown_ND_reinsertion',firmware_version='1.7',actual_exposure_ms=35,
        servo_min_us=1626,servo_max_us=1626,raw_aedat4_path=str(Path('data/raw')/(run+'.aedat4')),feedback_log_path=str(folder/'samples.csv'),status_log_path=str(folder/'operation.json'),processed_output_path=str(out),
        notes='Three ND reinsertion trials vs2recent unfiltered controls. No motion;1s pulses. Residual~1px stripe offset; digital signal ratio not transmittance; frozen detector counts reported; no new depth/NDcurve/threshold claim; finaloff/disarm/release.')
    rows.append(row)
with register.open('a',newline='',encoding='utf-8') as f:csv.DictWriter(f,fields).writerows(rows)
rig=json.load(urllib.request.urlopen('http://127.0.0.1:8933/rig/status',timeout=4));camera=json.load(urllib.request.urlopen('http://127.0.0.1:8931/status',timeout=4))
assert rig['fresh'] and not rig['active'] and not rig['controller']['laser'] and not rig['controller']['armed'] and not camera['recording']
manifest=dict(created_utc=datetime.now(timezone.utc).isoformat(),filter_current_state='User reinserted unknown ND; secured/contained confirmed. Filter remains installed at end.',
    results=str(out/'comparison.json'),source_hashes={r['run_id']:r['raw_sha256'] for r in d['results']},
    analysis_code_sha256=hashlib.sha256(Path('scripts/analyse_nd_fixed_position.py').read_bytes()).hexdigest(),
    final_controller=rig['controller'],camera={k:camera[k] for k in ['stale','actual_exposure_us','recording']},
    final_stop='outputs/static_checks/nd_retry_finalstop_20261103_01.json',tests='6 focused synthetic tests passed; no full-suite claim')
(out/'manifest.json').write_text(json.dumps(manifest,indent=2))
lines=['# ND reinsertion retry — 3 November 2026','',
    'Three new fixed1626us /35ms APS /1s pulse acquisitions completed after user reinserted the unknown ND filter and confirmed secured/contained/unchanged mounts and shoe. No servo movement, firmware update, exposure change or additional physical adjustment was commanded.','',
    '**Exploratory filter-configuration evidence, not a calibrated attenuation curve or optical transmission measurement.** Current comparison uses the two recent filter-removed controls, not the old shifted historical baseline. Earlier failed/confounded attempts remain intact and are not pooled into the retry.','',
    '| Condition | Independent acquisitions | Frozen APS candidate rows | Frozen event candidate rows (50ms ON/OFF) | Camera signal mean ± sample SD (digital levels) |','|---|---|---|---|---|']
for q in d['condition_summary']:lines.append(f"| {q['condition']} | {q['independent_acquisitions']} | {q['primary_APS_rows_each']} | {q['primary_event_rows_each']} | {q['mean_camera_signal_levels']:.3f} ± {q['sample_sd_camera_signal_levels']:.3f} |")
lines+=['','The ND camera-signal mean is0.4296times the recent unfiltered mean in a fixed unfiltered-derived integration mask. This is NOT43% optical transmission: camera response/linearity and filter density remain uncalibrated, and spatial/surface-response confounds remain. Mean±SD refers to independent acquisition amplitudes, not correlated frame/event counts. No bright clipping was observed in this integration mask.','',
    'The apparent median stripe-coordinate changes relative to the first recent unfiltered control are−0.940,−0.952,−0.964px; RMS differences1.002,1.022,1.036px. The residual can include real displacement and intensity-dependent centroid/detection differences; no physical cause is established. These values are substantially smaller than the prior~14px historical-reference discrepancy but do not prove exact geometric equivalence. No independent plane calibration was performed after filter handling.','',
    'All3retry traces passed log integrity/completion/off/disarm/release checks without feedback-screen warnings. Frozen APS spatial/temporal detector and frozen event settings are unchanged. The primary50ms event detector retained0,1,0rows;20ms retained0,0,0;100ms retained0,1,0. Separate post-pilot stable-reference APS diagnostics are retained, not substituted for primary results. Candidate rows are not independently labelled true detections or surface completeness.','',
    'Interpretation: this configuration produces a repeatably weaker digital stripe signal and fewer retained rows with the selected detectors. APS retains substantially more rows than the selected event method here. This is an implementation/condition result, not evidence that event cameras intrinsically fail in dim light: detector screens and temporal integration differ (two50ms event windows versus pooled35ms APS lit frames), and there is no detector-independent label study or equal-integration comparison.','',
    'Only two configurations are available: no filter and one unknown filter. No calibrated multi-level ND curve, weakest-usable brightness, independent depth accuracy, event advantage or new calibrated ND point cloud is established. Do not reuse the old command-plane mapping for new depth claims until geometry is checked. Prior saved reconstruction/calibration evidence remains unchanged.','',
    'Current state: ND remains installed, controller off/disarmed/servo released, camera live manual35ms and no recording. No request for another filter removal is pending.','',
    '## Reproduce offline','',
    '```powershell',
    '.venv/Scripts/python.exe -m scripts.analyse_nd_fixed_position --baseline nd_removed_r1_1626_20261103_01 nd_removed_r2_1626_20261103_01 --filtered nd_retry_r1_1626_20261103_01 nd_retry_r2_1626_20261103_01 nd_retry_r3_1626_20261103_01 --output outputs/attenuation/NEW_RETRY_DIRECTORY',
    '.venv/Scripts/python.exe -m pytest tests/test_nd_fixed_position.py tests/test_static_event_comparison.py -q','```','',
    f'Evidence: {out}/comparison.json, REVIEW.md, manifest.json, filter_comparison.png, signal_traces.png and fixed_measurement_mask.png. Source raw files, sidecars, operation/feedback logs and finalSTOP are retained. Three register entries added. Presentationversion04 is unchanged; do not describe this as a completed calibrated ND study.']
Path('ND_RETRY_20261103.md').write_text('\n'.join(lines),encoding='utf-8')
h=Path('PROJECT_HANDOFF_CURRENT.md');prior=h.read_text(encoding='utf-8');prefix='NEWEST ND reinsertion retry3Nov: read ND_RETRY_20261103.md and outputs/attenuation/nd_retry_repeats_20261103_01.3new ND-on fixed1626us/35ms/1s captures vs2recent noNDcontrols. PrimaryAPS62/62/64rows; event50ms0/1/0. No feedbackwarnings. Digital signal ratio0.4296 is NOTtransmittance. Residual stripe offset~−0.95px vsrecentcontrols; oldgeometry still not validated for newdepth. Only2configs, no calibratedNDcurve/weakestlevel/new3D. ND remains INSTALLED; finaloff/disarm/release, camera35ms live not recording. No filter-removal request pending. Oldconfounded ND results preserved separately, not pooled. Presentationversion04 unchanged.\n\n'
if not prior.startswith(prefix):h.write_text(prefix+prior,encoding='utf-8')
print(json.dumps(dict(report='ND_RETRY_20261103.md',registered=len(rows),laser=rig['controller']['laser'],armed=rig['controller']['armed'],recording=camera['recording'])))
