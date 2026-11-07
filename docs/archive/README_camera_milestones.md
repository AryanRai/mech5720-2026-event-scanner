# DAVIS240C camera sanity check

## Live agent control (local laptop)

For a persistent combined APS/events preview that an agent can inspect and control without reopening the camera, see [AGENT_CAMERA.md](AGENT_CAMERA.md). Start with `python scripts/camera_agent.py --serial 60008401`; use `python scripts/camera_ctl.py status` from the same virtual environment. Exposure, focus diagnostics, raw snapshots and bounded recordings are supported. No actuator/laser controls are exposed.

This initial milestone discovers a DAVIS and waits for one live event packet. Further acquisition, recording, and processing are not implemented yet.

In PowerShell, from this folder:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\check_camera.py
```

Use `--timeout 10` to wait longer or `--serial 60008401` to select a camera. Move a hand in the camera's field of view to generate events. A nonzero exit code and diagnostic indicate failure. A camera can report streams as available even when their delivery has not been verified. An open error does not uniquely establish that the device is busy: the original API error is printed to help diagnose it.

See [ENVIRONMENT.md](ENVIRONMENT.md) for this machine's observed results. The API is documented by [iniVation](https://dv-processing.inivation.com/master/reading_data.html).

## Milestone 2: live stream checks

Run one camera program at a time. The full check measures all streams for five seconds; use --timeout to change the duration:

```powershell
.\.venv\Scripts\python.exe scripts\check_camera.py --full
```

Point at a high-contrast scene and move your hand or camera. ON events appear red and OFF events blue. Press q or Escape to exit. Adjust the window with --window-us, for example 1000, 5000, 10000, 20000 or 50000.

```powershell
.\.venv\Scripts\python.exe scripts\live_events.py
```

Point at text or a checkerboard and adjust focus. Press s to save the unannotated grayscale image to outputs/frames/, or q to exit.

```powershell
.\.venv\Scripts\python.exe scripts\live_frames.py
```

Hold the camera still, then move and rotate it. Check that the printed acceleration and angular velocity change; stop with Ctrl+C, or add --duration 5 for a bounded run. The installed API's getAccelerations() and getAngularVelocities() return m/s² and rad/s, respectively.

```powershell
.\.venv\Scripts\python.exe scripts\live_imu.py
```

Both GUI programs accept --duration 3 --no-display for a bounded acquisition check. --serial selects a camera if more than one DAVIS is connected. Device-reported timestamps are printed without adjustment: the initial test observed frame timestamps on a different apparent scale or origin from events and IMU, so do not assume cross-stream synchronisation until investigated.

## Focus monitor before calibration

Start the relative sharpness monitor with:

```powershell
.\.venv\Scripts\python.exe scripts\live_frames.py --focus-monitor
```

For calibration readiness, provide your actual checkerboard **inner corners** (not squares). For example, a board with 10 squares across and 7 down has 9 by 6 inner intersections:

```powershell
.\.venv\Scripts\python.exe scripts\live_frames.py --focus-monitor --checkerboard-cols 9 --checkerboard-rows 6
```

Replace 9 and 6 with your printed board's counts. Rotate the focus ring slowly while watching the current/best sharpness ratio. Press `r` after changing the scene or board position to reset the best and history. Press `s` to save the untouched grayscale frame under `outputs/focus/`; `q` or Escape quits. The default viewer without `--focus-monitor` remains available.

Readiness is a heuristic, not a calibration or a guarantee of calibration quality. It requires a configured, fully detected board, 25 frames of stable sharpness, at least 90% detection, small corner-centroid movement, sufficient board span, low clipping, and five consecutive qualifying frames. Thresholds are empirical and scene dependent. Saturation warnings use 20% of pixels near either limit; the board-size heuristic requires the detected inner-corner bounding box to span at least 30% of both image dimensions. A missing board might be out of frame, blurred, too small, or use the wrong dimensions. Keep the board still and lighting consistent while focusing. The best score is a single-frame maximum and can be affected by noise; use `r` to restart if it becomes misleading. Readiness without specified dimensions is deliberately unavailable. Pose diversity and calibration accuracy still need separate assessment.

## Intrinsic calibration

Close other camera programs and start capture:

```powershell
.\.venv\Scripts\python.exe scripts\capture_calibration.py --checkerboard-cols 9 --checkerboard-rows 6 --square-size-mm 18
```

Use a rigid, flat board. Move it through the centre, sides and corners of the image; vary distance, in-plane rotation, and tilt left/right/up/down. Keep all outer squares visible and hold each pose still. Aim for 15-25 diverse images, not merely a large count. A 3x3 grid tracks accepted board **centres**, not full sensor corner coverage. Coverage and novelty are heuristics, not proof of a well-conditioned calibration. Check the board is fully visible yourself: the edge test estimates the outer edge from the inner corners and cannot guarantee it.

- Space saves a valid, sufficiently novel pose; rejected reasons appear in the preview and console.
- A toggles auto capture, requiring five stable detections and a two-second interval.
- C calibrates saved images (minimum ten). S saves a diagnostic screenshot. Q/Escape quits.
- Press R twice to reset only the current novelty/coverage guidance. Existing images and CSV records remain and still participate in calibration. This can permit duplicates; use it carefully.

The sharpness minimum of 20, clipping and pose thresholds are empirical and may need adjustment. Use `--min-sharpness` to set the absolute Laplacian-variance cutoff; inspect results manually for blur and exposure. Raw images and metadata are kept under `data/calibration/intrinsics`. Timestamps are preserved exactly as returned by the camera. Existing data are never deleted by the capture tool. Do not mix boards, cameras or resolutions in the same dataset. Move a completed dataset elsewhere before starting a different one.

To recalibrate offline, optionally excluding named files (repeat `--exclude`):

```powershell
.\.venv\Scripts\python.exe scripts\capture_calibration.py --calibrate --exclude image_EXAMPLE.png
```

Omit `--exclude` to use every saved view. Calibration overwrites the JSON, report and plot, but does not delete source images. Each view is re-detected; a failure requires explicit exclusion. The plot and report use per-view RMS pixel distance; the OpenCV overall RMS is also reported. Outlier labels are a heuristic, not automatic rejection. Inspect the result and perform a sensitivity check with and without suspect views. Capture more varied views if the fitted parameters or error are unstable.

After calibration, compare live frames, or supply `--image path\to\image.png` for a saved frame:

```powershell
.\.venv\Scripts\python.exe scripts\validate_calibration.py
```

The calibration file stores camera matrix, distortion, view extrinsics in millimetres, board dimensions and filenames; it is not a synchronization correction. Raw and corrected previews must have the same resolution as the calibration.

## Event recording and preliminary stripe pipeline

Run one camera program at a time. Close the calibration viewer before recording. The lens remains blurred; results are preliminary until it is replaced and the physical experiment is repeated.

```powershell
.\.venv\Scripts\python.exe scripts\record_capture.py test_capture --duration 10 --notes "describe scene and laser condition"
.\.venv\Scripts\python.exe scripts\replay_capture.py data\raw\test_capture.aedat4 --speed 1
.\.venv\Scripts\python.exe scripts\analyse_recording.py data\raw\test_capture.aedat4 --save-images
.\.venv\Scripts\python.exe scripts\detect_stripe_live.py
```

Recorder writes native AEDAT4 and a JSON sidecar; choose a new name for every recording. Replay speed 0 runs as fast as possible; speed 0.5 is half speed. Space pauses, n steps and q quits. Analysis writes window counts, observations, configuration and plots to `outputs/analysis/<recording>/`. The detector selects a high-density column band and fits a deterministic RANSAC line; it is intended for approximately vertical stripes and can mistake ordinary edges for stripes. Confidence is a heuristic, not a probability. No laser detection has yet been physically validated. The reported detection fraction includes empty windows within the observed event span.

The filters use polarity, a causal per-pixel refractory period and the number of distinct neighbouring pixels that fired recently. Tune via `analyse_recording.py --help`; default values are starting points, not calibrated optima. A line observation stores `[a,b,c]` for `a*x+b*y+c=0`, centroid, event timestamp in microseconds, inlier count, residual and heuristic confidence. The timestamp is the last event of the processed window, not a verified servo clock.

First physical test: use a white board and record three uniquely named captures: laser off and stationary; laser on and stationary; then a manually swept line. Label notes honestly. Compare event rates, retention and images. Detector inliers are not ground-truth signal; background rate and signal/background ratio require labelled measurements or a controlled baseline.

The frame stream has shown an initial timestamp near zero followed by epoch-scale timestamps. The recorder now drains and logs startup samples until two consecutive APS frames have timestamps at or above the API camera offset. Later uninitialized or large-jump APS timestamps stop the recording with an error. Stored timestamps are never modified; this gate does not prove cross-stream synchronization accuracy. The older hardware_sanity recordings contain the startup anomaly. `hardware_sanity_01` and `hardware_sanity_02` are physical camera connectivity tests, not labelled laser experiments.

To export a bounded interval after reading timestamps from analysis:

```powershell
.\.venv\Scripts\python.exe scripts\export_events.py data\raw\test_capture.aedat4 data\processed\subset.npz --start-us 1000000 --end-us 2000000
```

Replace those example timestamps with actual event timestamps. The compressed NPZ contains a structured array with timestamp, x, y and polarity.

Performance note: the causal filter is compiled with Numba, warmed before live acquisition. The 416,828-event test took 0.018 seconds in the warmed filter; end-to-end offline analysis including startup and plots took 2.17 seconds for 3.01 seconds of capture. Performance depends on event rate and scene; this is not a guarantee against live backlog or packet loss.

Inspect actual stored stream timestamps without changing them:

```powershell
.\.venv\Scripts\python.exe scripts\inspect_timestamps.py data\raw\hardware_sanity_02.aedat4
```

The first frame timestamp jump was reproduced on multiple starts. Three gated recordings excluded the startup anomaly and had no large frame timestamp jumps. Subsequent frame timestamps appear on the same scale as events and IMU; this is evidence of a startup anomaly, not proof of the cause or of synchronization accuracy. Preserve the original recording and exclude problematic frames explicitly in any future synchronized analysis.

Every new recording sidecar includes an automatic timestamp plausibility assessment. PASS means stream ranges overlap, their boundaries are within 500 ms, and the implemented monotonicity and jump checks passed. It does not mean the streams are aligned to a measured accuracy; APS exposure duration and real sensor latency are not corrected. A failed assessment is recorded and returns a nonzero exit code.
