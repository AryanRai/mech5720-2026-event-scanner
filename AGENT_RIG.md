# Agent control: Codex, Claude and other local CLI agents

This follows `../analysis/cam.py` from the Pi labs: keep the viewer/hardware owner alive and use a separate command-line client for status, exposure, captures and diagnostics. Unlike the original Pi code, operations here have IDs, a journal and explicit uncertain-outcome handling. No provider-specific SDK or separate agent service is required.

## Ownership and enablement

- DAVIS owner: `scripts/camera_agent.py`, port 8931. Existing `AGENT_CAMERA.md` remains authoritative for camera operation and optical limits.
- Combined dashboard/API: `scripts/scanner_dashboard_server.py`, port 8933. Launch hidden with repo `.venv/Scripts/pythonw.exe -u scripts/scanner_dashboard_server.py`, stdout/stderr redirected to logs. Do not start another instance if its status responds.
- Arduino owner: **one Chrome dashboard**, Web Serial, COM13 at 115200. Never open serial from another process while connected. Selecting Connect resets this Uno and centres it at 1500 us; ensure clearance.
- In http://127.0.0.1:8933/scanner_dashboard.html connect COM13, then check **Allow local agent control (contained rig)**. This is a session-only actuator opt-in; never auto-connect or restore it after reload. Manual dashboard stays usable between agent operations. STOP interrupts; unchecking the opt-in stops an active agent operation.

The user confirmed a controlled environment and clear beam path on 2026-11-02. Recheck after physical changes; that statement is not proof of future containment or calibrated travel limits.

## CLI (from repo root)

```
.venv/Scripts/python.exe scripts/rig_ctl.py status
.venv/Scripts/python.exe scripts/rig_ctl.py camera diagnostics
.venv/Scripts/python.exe scripts/rig_ctl.py camera exposure 20000
.venv/Scripts/python.exe scripts/rig_ctl.py camera auto on
.venv/Scripts/python.exe scripts/rig_ctl.py camera --request-id view_001 snapshot view_001
.venv/Scripts/python.exe scripts/rig_ctl.py camera --request-id camera_run_001 record camera_run_001 --duration 10
.venv/Scripts/python.exe scripts/rig_ctl.py camera record-stop
.venv/Scripts/python.exe scripts/rig_ctl.py --request-id feedback_001 --contained read 100
.venv/Scripts/python.exe scripts/rig_ctl.py --request-id move_001 --contained move 1500
.venv/Scripts/python.exe scripts/rig_ctl.py --request-id pulse_001 --contained --arm pulse 1
.venv/Scripts/python.exe scripts/rig_ctl.py --request-id sweep_001 --contained --arm sweep 1480 1520 1000
.venv/Scripts/python.exe scripts/rig_ctl.py --request-id scan_001 --contained --arm scan 1480 1520 1000
.venv/Scripts/python.exe scripts/rig_ctl.py --request-id stop_001 stop
.venv/Scripts/python.exe scripts/rig_ctl.py operation scan_001
```

Use fresh unique IDs for intentional new operations. **Never replay an uncertain command under a new ID.** Inspect its operation and hardware first. Reusing the same ID and identical payload returns its saved state without dispatching again; a changed payload is refused. Journal survives server restarts; unfinished operations become unknown, not replayable. A newly generated token is read from ignored `.runtime/rig.json`; do not print, share or commit it.

Agent envelope: 1100–1900 us moves/sweeps; ascending sweep 100–10000 ms; laser pulse 1–5 seconds; feedback 1–1000 reads. No raw serial command endpoint, indefinite emission, automatic reset/reconnect, firmware upload, interlock bypass or arbitrary register writes. Every emitting request requires `--contained --arm`; the browser checks the real firmware interlock/window before arming. Operations start disarmed/off and finish stop + status with off/disarm confirmation. Servo is released at the end; physical feedback position after release is not guaranteed held.

`scan` starts a bounded DAVIS recording, dispatches one sweep, saves the Arduino result under `outputs/rig_runs/ID`, then stops/finalizes camera recording. Native events, APS and IMU are in `data/raw/rig_ID.aedat4`; sidecar has timestamp plausibility audit. This is **host-coordinated acquisition, not calibrated clock synchronization**. Firmware optical markers must be matched in the DAVIS stream and validated before time/angle reconstruction. Camera capture failures prevent starting the sweep; after uncertain dispatch inspect the operation ID rather than rerunning.

## Observe → diagnose → act → verify

1. `status`: check fresh browser heartbeat, firmware v1.3, feedback present, interlock, laser and camera freshness/stream counts.
2. `camera diagnostics` / snapshot: inspect actual image, clipping, exposure and relative focus. Keep physical target/lighting fixed. No automatic lens/iris adjustment or unsupported gain controls.
3. `read`, then small `move`: inspect ADC changes and repeatability before widening any physical travel. Status ADC is oversampled (~4x); `read` mean/std is raw ADC. Neither is calibrated degrees.
4. Use a short pulse/scan only with verified beam containment. Inspect operation result `stop_confirmed`, errors and raw S/E lines; `OK sweep` means accepted, **not finished**. Browser waits for DONE/ABORTED.
5. Review camera sidecar/native timestamps and marker visibility. High event rate alone is not stripe detection or a successful 3D scan.

The single-flight mailbox refuses stale/offline/disabled/busy clients and competing browser owners. Browser claims each operation once. A lost network response is not a reason to resend. Raw lines (up to 3000 per bounded operation) and final telemetry are in `outputs/agent_control/rig_operations.jsonl`. The limit is sufficient for the current 200 Hz Uno/10 s envelope; do not silently extend durations/sample rates without revisiting limits.

## Safety and limits

Host/browser control is not safety-rated. If Chrome/USB fails during a pulse, the firmware's existing 60-second manual timeout is the fallback, not the requested 1–5 second host bound. Sweep firmware remains independently bounded by its duration; no firmware safety changes were made. Keep physical power disconnect available, contain reflections, and never point at eyes or the sensor. Command-position windows do not verify actual beam position. Feedback is sampled for diagnosis, not closed-loop laser gating. Existing firmware settle timeouts warn but do not abort. Do not claim position calibration or physical time synchronization from this interface.

Reload/update procedure: STOP and confirm off, Disconnect in dashboard, restart only the identified dashboard server, reload, then user reconnects COM13 and re-enables local agents. Do not steal a serial connection from Chrome. No action should occur merely on opening the page or importing CLI modules.

## Verification

### Static acquisition and optical observation (v1.7 deployed)

See `P3_OPTICAL_OBSERVATION_20261102.md` for current deployment and evidence.
Physical v1.7 supports strict `static CURRENT_US` and separate `observe CURRENT_US`.
Observation records electrical amplitude/drift screen failure as a warning; it
does not claim stability. Count/pre-light gap checks and all interlock/arm/STOP/
deadline/off/release controls remain. Require fresh `static=1` / `observe=1` as
appropriate. Historical P3_STATIC_CAPTURE document describes earlier versions.
Do not upload while Chrome owns serial.

### Prepared P2 diagnostic extension (2 November 2026)

`rig_ctl.py --request-id UNIQUE --contained probe 1500 1510 1000` is a
laser-OFF diagnostic for prepared firmware v1.4. It never arms or pulses the
laser. Both endpoints and the initial command must be in 1100–1900 us (physical
clearance still required); target hold is 100–3000 ms. Source is reached directly,
with no hidden 60 us preroll. A 500 ms released baseline and 500 ms held source
precede the source-to-target ramp and target hold. Sampling is 100 Hz; every F
line brackets a single ADC block with controller timestamps and reports its
first raw read, sum, count, divisor and attachment/laser state. Block mean is
sum/count, existing feedback scale is floor(sum/divisor). Neither is degrees.
The firmware checks an 8 s deadline and releases the servo on completion or
abort. These are software controls, not safety-rated hardware protection.

The browser refuses this operation unless fresh firmware status advertises
`probe=1`, and verifies off/disarm/release at the end. Host receive timestamps
are separate browser-session monotonic milliseconds, not camera alignment.
Export a journal operation without hardware access using:

```
.venv/Scripts/python.exe scripts/analyse_servo_probe.py --request-id UNIQUE --output outputs/feedback_tests/NEW_DIRECTORY
```

Firmware was subsequently uploaded and flash-verified after explicit user
authorization; the dashboard/server were restarted/reloaded. After user reconnect,
three small laser-off probes passed log integrity and final release checks.
Feedback variation remains unresolved; see the physical diagnostic review in
`outputs/feedback_tests/p2_v14_session_20261102/REVIEW.md`. See
`P2_LOGGING_UPDATE_20261102.md` for deployment and validation status. Follow the
existing STOP/disconnect/reload/user-reconnect procedure; do not reset or upload
while Chrome owns serial. No real trace or settling result is implied by tests.

See `AGENT_RIG_TEST_20261102.md` for the real laser-off feedback/move/DAVIS recording smoke test and explicit unverified emitting paths. Run `.venv/Scripts/python.exe -m pytest -q` and `node tests/test_rig_dashboard.cjs` for synthetic regression checks.
