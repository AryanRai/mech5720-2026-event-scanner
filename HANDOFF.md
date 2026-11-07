# MECH5720 DAVIS240C project handoff

Last updated 30 October 2026 (Australia/Sydney). This is an engineering handoff, not a claim that the scanner or calibration is complete.

## Prompt for a new assistant chat

> Continue the MECH5720 Event-Based Structured-Light 3D Scanner project in this repository. Read HANDOFF.md and README.md, inspect and test the existing implementation, and use the physical DAVIS240C when available. The immediate priority is to determine why the Fujinon lens image is blurred, establish whether the required C-to-CS adapter is installed, and obtain a sharp image. Then acquire a fresh checkerboard calibration and, when the laser is available, perform the three controlled recordings and validate stripe detection. Do not claim successful physical calibration or laser detection without actual results. Preserve raw measurements and do not silently apply timestamp corrections. Ask me for physical actions and monitor the camera programmatically where possible. Do not implement servo control, projector calibration or 3D reconstruction unless explicitly requested later. The target is a practical demo, with honest limitations.

## Goal and boundaries

The proposed eventual system sweeps a weak laser line using a positional servo, captures DAVIS events and later combines timestamped stripe observations with servo angle and calibration for 3D. Current scope is camera acquisition, recording, replay, event filtering, stripe candidates and diagnostics. Servo integration, projector/light-plane calibration, and depth reconstruction are not implemented.

## Hardware and optical diagnosis

- Camera: iniVation DAVIS240C, serial 60008401, 240 x 180 events and APS. Actual events, grayscale APS and IMU have all been received. Windows; dv-processing 2.0.4.
- Lens marking from user photos: FUJINON DF6HA-1B, 6 mm, f/1.2, C-mount. Manufacturer specifications: manual focus and iris, f/1.2-f/16, 1/2-inch format, minimum working distance 100 mm from the front of the lens. https://www.rmaelectronics.com/content/Fujinon-Lens-PDF/FUJINON_FAMV_Brochure_EN_170310.pdf
- DAVIS240 guide identifies a CS-mount camera, requiring an adapter for C-mount lenses: https://docs.inivation.com/_static/hardware_guides/davis240.pdf. A 5 mm C-mount lens to CS-mount camera ring is the usual spacer. The photographs do not establish whether one is already fitted. The user found a loose hollow threaded ring in the camera case; dimensions, external thread and identity are unconfirmed. Do not assume it is the adapter or add a second spacer blindly.
- The user reports the back lens ring changes brightness, while the front ring moves the lens in/out. They swept focus and reported that the current image was the sharpest obtainable. Images remained markedly blurred. This supports an optics/focus/spacing concern but does not prove a defective lens. Ask lecturer Don or a knowledgeable person to check seating and mount spacer; avoid forcing rings or touching the sensor.
- Long auto-exposure and low illumination complicated tests: exposures varied around 60-237 ms; fixed 10/30 ms trial images were near black and 80 ms dark under then-current conditions. Focus and iris adjustments and changing lighting were not a controlled experiment. Some earlier frames detected 54/54 corners despite visible blur; that does not establish calibration quality.
- The user expects step-by-step physical prompts and wants the viewer open while an assistant inspects camera frames programmatically. `scripts/lens_diagnostic.py` writes a rolling `outputs/lens_diagnostic/latest.png` and `live_metrics.csv`; the running process may still have exclusive access. That log is transient and isn't included in this handoff. Only one camera application can normally access the device at once. Restart the script if needed. Be careful: logging samples continue until q/Escape or process termination.

## Calibration target and current dataset

Print `output/pdf/checkerboard_9x6_A4.pdf` on A4 at 100%, measure squares; 10 x 7 squares, 9 x 6 inner corners, 18 mm nominal squares. Four raw views in `data/calibration/intrinsics/images` and capture metadata are real physical images but visibly blurry. They are not an accepted calibration. No intrinsic matrix or report from a physical calibration has been obtained. After lens/mount changes, collect a new dataset separately, do not mix old and new optics. The capture tool uses the existing dataset directory and will load its previous list: move/archive the entire existing dataset explicitly before a new session, preserving the old files and metadata.

## What exists

- `event_camera/camera.py` opens and selects DAVIS via official API; `scripts/check_camera.py --full` tests all streams.
- `scripts/live_events.py`, `live_frames.py` (optional focus mode), `live_imu.py` provide live checks. `scripts/capture_calibration.py` collects and calibrates; `validate_calibration.py` shows undistortion after a valid calibration.
- `scripts/record_capture.py` records native AEDAT4 events, APS and IMU plus JSON metadata. It drains startup samples until two APS timestamps are consistent with the camera offset and logs discarded samples. It audits plausibility and flags failures; timestamps are not adjusted. `scripts/inspect_timestamps.py` audits existing files. In early physical recordings, first APS timestamp was near zero while later frames/events/IMU used epoch-scale timestamps. This was reproduced; gated recordings did not exhibit that jump. Matching timestamp scales and overlap do NOT prove physical alignment, latency, exposure timing, or accuracy.
- `scripts/replay_capture.py` replays events; `scripts/export_events.py` exports a selected interval to NPZ. `scripts/analyse_recording.py` produces per-window CSV, observations, summary and plots. `scripts/detect_stripe_live.py` visualises raw/filtered events and candidate lines.
- `event_camera/filters.py` implements polarity, refractory and causal local support, compiled with Numba. `stripe_detector.py` implements histogram candidate band and seeded RANSAC line. It is an initial heuristic for approximately vertical/moderately sloped lines: background edges can generate false positives, and confidence is not a probability. No physical laser stripe has yet been validated.
- Recorded files in `data/raw` are genuine camera connectivity/timestamp tests; laser condition is unspecified or no laser. They are not controlled laser experiments and detections must not be represented as laser performance. Diagnostic outputs are preliminary; the event timestamps in the earlier `hardware_sanity_*` files include the startup frame anomaly.
- The filter alone processed the 416,828-event hardware recording in ~0.018 s after compilation on the original machine. Full analysis took ~2.17 s for 3.01 s of recording. These are point benchmarks, not real-time or no-loss guarantees.

## Setup and commands

From a Windows PowerShell prompt in the repo:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\check_camera.py --full
.\.venv\Scripts\python.exe scripts\lens_diagnostic.py
.\.venv\Scripts\python.exe scripts\capture_calibration.py --checkerboard-cols 9 --checkerboard-rows 6 --square-size-mm 18
.\.venv\Scripts\python.exe scripts\record_capture.py NAME --duration 10 --notes "describe physical scene"
.\.venv\Scripts\python.exe scripts\replay_capture.py data\raw\NAME.aedat4 --speed 1
.\.venv\Scripts\python.exe scripts\analyse_recording.py data\raw\NAME.aedat4 --save-images
.\.venv\Scripts\python.exe scripts\inspect_timestamps.py data\raw\NAME.aedat4
```

Use new names for recordings. The camera can be busy if a viewer is open; quit it before opening another capture. See README for arguments and keyboard controls. Original environment used Python 3.13.14; tests last passed 16/16 on 30 October. Verify afresh on the new machine.

## Next actions for the demo

1. Inspect whether the loose ring is truly the correct 5 mm spacer and whether the camera already has one. Set a stable, evenly illuminated board and adjust iris and focus. Verify actual frame sharpness; do not assume hardware fault solely from the image.
2. After any optical changes, lock focus and capture 15-25 diverse, sharp physical checkerboard images. Assess per-view and overall reprojection error and undistortion; retain and explicitly exclude bad views. No reliable calibration is yet available.
3. When laser hardware arrives, record three labelled experiments: stationary laser off, laser stationary on, and manual sweep. Compare baseline and signal, test detector visually and quantitatively, tune filter parameters, and retain a recorded replay for the demo. Never call arbitrary background edge candidates laser signal.
4. Physical timestamp alignment requires a shared time reference or controlled event; current audit only establishes plausibility. Avoid claiming precise synchronization or 3D capability.

## Known limitations

Filtering/line fitting currently makes no claim of confirmed structured-light isolation. Detection metric includes empty windows within the event span; no verified background rate or signal-to-background ratio exists. No actual projector, servo, or 3D calibration has been done. Live performance and drops vary with scene and have not been formally bounded. Inspect existing code and tests before relying on it.
