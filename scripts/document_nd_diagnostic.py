"""Register actual ND diagnostic captures and preserve the inconclusive outcome."""
import csv
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import urllib.request

out=Path('outputs/attenuation/nd_bracketed_confounded_20261103_01');result=json.loads((out/'comparison.json').read_text())
register=Path('EXPERIMENT_RUN_REGISTER.csv')
with register.open(newline='',encoding='utf-8-sig') as f:reader=csv.DictReader(f);fields=reader.fieldnames;existing={r['run_id'] for r in reader}
rows=[]
for r in result['results']:
    if r['condition']=='no_filter' or r['run_id'] in existing:continue
    folder=Path('outputs/static_checks')/r['run_id'];trace=json.loads((folder/'summary.json').read_text());assert not trace['errors']
    sidecar=json.loads((Path('data/raw')/(r['run_id']+'.json')).read_text());assert sidecar['status']=='complete'
    row=dict.fromkeys(fields,'');row.update(run_id=r['run_id'],block='P8',status='completed_diagnostic_spatially_confounded',condition_id=r['condition'],firmware_version='1.7',actual_exposure_ms=35,
        servo_min_us=1626,servo_max_us=1626,raw_aedat4_path=str(Path('data/raw')/(r['run_id']+'.aedat4')),feedback_log_path=str(folder/'samples.csv'),status_log_path=str(folder/'operation.json'),processed_output_path=str(out),
        notes='Unknown ND. Static1s pulse; no servo movement.3filtered/2removed controls. Stripe displacement invalidates attenuation ratio and old-plane depth use; primary detectors unchanged; no weakest-level/NDcurve claim; finaloff/disarm/release.')
    rows.append(row)
with register.open('a',newline='',encoding='utf-8') as f:csv.DictWriter(f,fields).writerows(rows)
rig=json.load(urllib.request.urlopen('http://127.0.0.1:8933/rig/status',timeout=4));camera=json.load(urllib.request.urlopen('http://127.0.0.1:8931/status',timeout=4))
assert rig['fresh'] and not rig['active'] and not rig['controller']['laser'] and not rig['controller']['armed'] and not camera['recording']
manifest=dict(created_utc=datetime.now(timezone.utc).isoformat(),filter_marking='unknown',filter_current_state='User removed filter and confirmed reconnected/contained before control captures',
    captures=[r['run_id'] for r in result['results'] if r['condition']!='no_filter'],
    source_hashes={r['run_id']:r['raw_sha256'] for r in result['results']},
    code_sha256=hashlib.sha256(Path('scripts/analyse_nd_fixed_position.py').read_bytes()).hexdigest(),
    final_controller=rig['controller'],camera={k:camera[k] for k in ['actual_exposure_us','stale','recording']},
    final_stop_operation='nd_removed_shift_stop_20261103_01',
    no_new_depth_reconstruction=True,valid_attenuation_result=False,tests='6 focused synthetic tests passed; no full-suite claim')
(out/'manifest.json').write_text(json.dumps(manifest,indent=2))
lines=['# ND insertion/removal diagnostic — 3 November 2026','',
    '**Inconclusive as an attenuation experiment: stripe position changed.** No new calibrated depth reconstruction, optical transmission, weakest-usable-level claim or attenuation-performance curve was produced.','',
    'User confirmed filter secured, hands clear and transmitted/reflected beams contained. Unknown filter marking. No servo move was requested: all five new acquisitions used existing1626us command, manual35ms APS exposure and bounded1s laser pulse. Three filtered recordings completed; after user removed only the filter and confirmed readiness, two control recordings completed. Planned third control was not acquired after the large displacement was found. All captures passed saved controller-trace integrity checks and completed recordings; finalSTOP confirmed off/disarm/release.','',
    '| Condition | n acquisitions | Frozen APS candidate rows | Frozen event candidate rows |','|---|---|---|---|']
for q in result['condition_summary']:lines.append(f"| {q['condition']} | {q['independent_acquisitions']} | {q['primary_APS_rows_each']} | {q['primary_event_rows_each']} |")
lines+=['','The earlier unfiltered records are historical comparison data, not interleaved controls. The filtered stripe had an apparent median horizontal change of about−2.15px versus the old baseline under the separate stable-reference diagnostic. Filter-removed control stripes are about+14px versus that baseline. These are image-coordinate comparisons, not an independent calibrated plane-shift measurement. Filter handling, pose/servo variation and optical displacement remain confounded; no cause is established. All3filtered runs had feedback-screen warnings; prior1626baselines and filter-removed controls did not.','',
    'The old fixed integration mask measured28.660±0.189digital levels without the filter versus14.292±0.071with it (mean±sampleSD,n3each). The numeric ratio0.499 is a signal ratio in the OLD mask, not optical transmittance. The filter-removed stripe subsequently missed much of that mask, demonstrating why mask-based ratios cannot isolate attenuation here. Do not label this filterND0.3,50%transmission or one stop. Camera response/linearity was not calibrated.','',
    'Frozen detector outputs are retained, including the first filtered APS failure. A separate post-pilot diagnostic used median first1.5s dark reference and fixed-mask pulse selection with unchanged spatial thresholds. It retained62,61,61APSrows for filtered trials; this diagnoses temporal/reference selection sensitivity and does not replace primary results. Event20/50/100ms sensitivity is retained in comparison.json. No threshold was silently lowered or failure removed.','',
    '## Current geometry and next measurement','',
    'The filter is removed; rig off/disarmed/released; camera live35ms, not recording. Current command-to-plane geometry must be rechecked before new depth claims because the stripe no longer matches its historical position. Earlier saved calibrations/reconstructions remain unchanged evidence of their own acquisitions; this is not a reason for broad intrinsic-camera retakes.','',
    'A valid follow-up requires a stable filter insertion arrangement that does not disturb the projector/mounts, or measurement of any filter-induced plane change. Verify removal restores stripe geometry before interpreting paired brightness/support as attenuation performance. Additional documented levels are still needed for a curve; current data do not establish a weakest level.','',
    '## Retained evidence','',
    f'{out}/comparison.json, manifest.json, REVIEW.md, filter_comparison.png, signal_traces.png and fixed_measurement_mask.png. Raw AEDAT4/sidecars and all operation/sample logs are retained under data/raw and outputs/static_checks. The register contains all5new runs. Initial pilot/failed analysis outputs remain; newest bracketed result supersedes their interpretation.','',
    'Reproduce offline into a new output directory:','',
    '```powershell',
    '.venv/Scripts/python.exe -m scripts.analyse_nd_fixed_position --filtered nd_unknown_r1_1626_20261103_01 nd_unknown_r2_1626_20261103_01 nd_unknown_r3_1626_20261103_01 --control nd_removed_r1_1626_20261103_01 nd_removed_r2_1626_20261103_01 --output outputs/attenuation/NEW_DIRECTORY',
    '.venv/Scripts/python.exe -m pytest tests/test_nd_fixed_position.py tests/test_static_event_comparison.py -q','```','',
    'Existing presentationversion04 remains the delivered deck; this diagnostic has not been added as a successful ND experiment.']
Path('ND_DIAGNOSTIC_20261103.md').write_text('\n'.join(lines),encoding='utf-8')
h=Path('PROJECT_HANDOFF_CURRENT.md');prior=h.read_text(encoding='utf-8');prefix='NEWEST ND diagnostic3Nov: read ND_DIAGNOSTIC_20261103.md and outputs/attenuation/nd_bracketed_confounded_20261103_01.3unknownND captures and2filter-removed controls at1626us/35ms/1s, all raw/logs retained,5registerentries. Insertion apparent stripe−2px, removal~+14px versus historical baseline: geometry confounded, no valid attenuation ratio/NDcurve/depth reconstruction.0.499 old-mask digital signal ratio is NOTtransmittance. Filter removed, finaloff/disarm/release, camera35ms live not recording. Do NOT assume current old command-plane mapping valid for newdepth; check geometry first. Prior saved static event/APS results retained. No broad intrinsic retake required. Presentationversion04 unchanged by this diagnostic.\n\n'
if not prior.startswith(prefix):h.write_text(prefix+prior,encoding='utf-8')
print(json.dumps(dict(report='ND_DIAGNOSTIC_20261103.md',new_register_rows=len(rows),condition_summary=result['condition_summary'],current_laser=rig['controller']['laser'],current_armed=rig['controller']['armed'])))
