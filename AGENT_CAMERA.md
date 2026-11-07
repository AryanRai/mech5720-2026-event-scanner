# DAVIS agent control and live preview

This is the camera equivalent of the Pi-camera `analysis/cam.py` workflow: **one running camera process**, with a separate agent-facing command tool. The preview stays open while commands inspect or change the camera. No Arduino, servo or laser control is exposed.

## Start / resume

From this repository in PowerShell:

```powershell
.venv/Scripts/python.exe scripts/camera_agent.py --serial 60008401
```

The native window shows APS grayscale, recent ON/OFF events, actual exposure, clipping, session-relative focus score and recording state. Keyboard: `q`/Escape closes and releases the camera; `s` saves a raw snapshot; `r` resets the focus baseline; `a` toggles auto exposure. Keep this window open while using the CLI. Close any older viewer first—only one process can normally own the camera.

Use `--no-display` for headless operation; `--port` changes the loopback port. Default is **127.0.0.1:8931**, never a LAN listener. This is not a stream to a remote assistant service: images stay on this laptop unless explicitly shared.

### Chrome preview / keeping the service alive between agent turns

Open **http://127.0.0.1:8931/** in Chrome. This read-only page shows live APS/events, exposure and focus metrics, and an explicit disconnected/stale indicator. It sends no actuator or camera-control commands. Use `camera_ctl.py` for controls.

The old foreground command session did not survive between agent turns on this machine. The browser preview therefore uses a separate background owner, launched with `Start-Process` and `pythonw.exe --no-display`, not a turn-bound terminal process. Before starting another owner, try `camera_ctl.py status` and check the existing process/listener. If it is healthy, reuse it. After a confirmed stop, a PowerShell launch from the repo is:

```powershell
Start-Process -FilePath "$PWD/.venv/Scripts/pythonw.exe" -ArgumentList @('-u','scripts/camera_agent.py','--serial','60008401','--no-display') -WorkingDirectory "$PWD" -WindowStyle Hidden
```

Use the Ally Chrome-extension backend to open/select that URL; do not silently switch to another browser or expose the server on the LAN. The service still requires this laptop and camera to remain powered and connected. Stop with `camera_ctl.py shutdown` when done.

## Agent commands

```powershell
.venv/Scripts/python.exe scripts/camera_ctl.py status
.venv/Scripts/python.exe scripts/camera_ctl.py diagnostics
.venv/Scripts/python.exe scripts/camera_ctl.py exposure 20000
.venv/Scripts/python.exe scripts/camera_ctl.py auto on
.venv/Scripts/python.exe scripts/camera_ctl.py focus
.venv/Scripts/python.exe scripts/camera_ctl.py focus 9 6
.venv/Scripts/python.exe scripts/camera_ctl.py --request-id capture_example_01 snapshot focus_example_01 --notes "fixed target before focus adjustment"
.venv/Scripts/python.exe scripts/camera_ctl.py --request-id record_example_01 record camera_check_example_01 --duration 5 --notes "laser off, scene description"
.venv/Scripts/python.exe scripts/camera_ctl.py record-stop
.venv/Scripts/python.exe scripts/camera_ctl.py operation record_example_01
.venv/Scripts/python.exe scripts/camera_ctl.py shutdown
```

- `exposure` selects manual mode; 100–500000 microseconds are accepted. This is an input guard, not a guarantee the hardware applies every value exactly. Status distinguishes **requested** exposure from the latest frame's **actual** exposure. Auto/manual changes reset relative focus history and are refused during recording.
- `focus` resets the comparison baseline; optional inner-corner counts enable checkerboard diagnostics. No pattern configured means there can be **no calibration readiness assessment**. Changing scene, distance, iris, lighting or exposure invalidates a before/after focus comparison—reset the baseline.
- `status` reports stream totals, rates, last-arrival ages, stale-frame flag, initialization and errors. A stale cached image is not a live camera. `diagnostics` returns a bounded recent metric history, not an unlimited log.
- `snapshot` saves the **unannotated** APS PNG, a recent event visualization and JSON metadata under `outputs/agent_control/NAME`. The event rendering is not a guaranteed time-aligned APS pair. Existing names are not overwritten. You can inspect the raw image with the image-viewing tool.
- `record` starts an asynchronous, bounded native AEDAT4 capture (0.1–300 s) while keeping preview live. The command's success means **started**, not finished: check `status.recording`, `status.last_recording`, the sidecar and/or run `scripts/inspect_timestamps.py` on the finished file. Frames, events and IMU are drained by the same owner, not separate competing capture processes.
- Recordings require fresh APS data and two consecutive initialized frame timestamps. Timestamp changes are **not corrected**. Backwards/uninitialized/large-jump frame timestamps stop and flag the recording. Sidecar audits cover stream presence, ordering and overlap; a PASS does **not** measure physical synchronization, latency, exposure midpoint or Arduino clock alignment.
- `record-stop` finalizes an active recording. Shutdown/quit finalizes an in-progress file as interrupted, not complete. Disk/write errors are reported; data already saved are preserved.

## Uncertain outcomes and local security

Each command prints a request ID **before posting**. If a call times out after submitting, inspect `operation ID`; never invent a new ID and repeat a capture blindly. Repeating exactly the same request with the same ID returns its saved outcome without executing again. Using an existing ID with a different payload is refused. Idempotency is per process/session, not durable across restart: after a restart also inspect output files. Do not rerun the same recording/snapshot name as a cleanup tactic.

The runtime descriptor `.runtime/camera.json` contains a per-run local token. Do not publish it. `.runtime/` is ignored by Git. HTTP writes require the token and a loopback Host; browser-origin writes are rejected. The server does not execute shell commands, accept arbitrary file paths, expose register writes or provide actuator commands.

Read-only endpoints: `/status`, `/diagnostics`, `/frame.jpg`, `/events.jpg`, `/operations/ID`. Use CLI for controls instead of browser scripting.

## Focusing procedure / honest limits

1. Keep the laser off. Aim at a stationary, evenly illuminated checkerboard or printed text; hold target, camera and iris fixed.
2. Watch the **left grayscale image**, not just the score. Rotate only the actual focus ring slowly; physical focus/iris and lens spacers cannot be adjusted by software.
3. Compare fine edges under stable exposure/lighting. Long exposures can create motion blur; short exposures in dim light can hide detail. Noise, scene changes and clipping can inflate or depress the score. A relative score of 100% merely means best **this session**, not sharp focus.
4. If no sharp setting exists, verify the Fujinon C-mount lens / DAVIS CS-mount spacer with an informed physical inspection. Do not force the lens, expose/touch the sensor or add a second adapter blindly.
5. After optical changes, acquire a new diverse checkerboard dataset. This service does not implement intrinsic calibration, servo/plane calibration, line optics or 3D reconstruction. Use the repository's existing calibration tools after quitting this owner, or extend deliberately.

The event pane is raw activity, **not labelled laser detection**. The existing stripe detector is not validated on the point laser. High event counts or lines in background-only data are not scanner success.

## Verified locally

The control-plane tests are synthetic; they do not prove USB hardware behavior. Run `.venv/Scripts/python.exe -m pytest -q`. Hardware smoke-test outcomes are recorded in `LOCAL_SETUP_ARYAN_20261030.md`.
