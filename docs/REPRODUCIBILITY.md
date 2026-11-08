# Reproduce a key figure without the scanner

The coverage example includes real retained APS/event point coordinates, the matching grayscale photograph and fixed mask. It does not require DAVIS, Arduino, serial access, dv-processing, a running service or the full raw archive.

From the repository root, using Python 3.12 and the recorded offline dependency versions:

```powershell
python -m pip install -r requirements-offline.txt
python examples/coverage/regenerate.py
```

Outputs appear in `examples/coverage/regenerated_key_figure/`: `coverage.png` and `coverage.json`. The script verifies the photo SHA256 and refuses an existing output directory. Keep previous output and use a fresh checkout/copy for another run; do not overwrite evidence.

Expected results:

| Method | Unique occupied native pixels | Fixed mask pixels | Image-space coverage |
|---|---:|---:|---:|
| APS | 939 | 13715 | 6.8465184105% |
| Events, 50 ms windows | 478 | 13715 | 3.4852351440% |

The mask is manually selected, post-acquisition and approximate. It is the same denominator for both methods and includes unsampled parts of the body. This example regenerates image-space sample coverage, not true physical surface completeness, depth accuracy or detector precision.

## Retained inputs and provenance

- `examples/coverage/repro_data/aps_points.csv`: 960 retained APS intersections, including native pixel locations.
- `event_points.csv`: event-window variants; the generator selects only 50 ms.
- `shoe_photo.png`: laser-off DAVIS APS image from the earlier twenty-position condition.
- `mask_definition.json`: source hash and native polygon vertices.
- `results/MANIFEST.json`: checksums (LF-normalised for text, exact bytes for binary assets) of all included numerical evidence, images, report inputs and CAD review files.
- `results/evidence/`: immutable copied numerical summaries; original acquisition paths remain provenance, not download links.

Run `python scripts/verify_repository_evidence.py` to verify all curated files without hardware.

## Full native acquisition archive

The locally retained `.aedat4` files, sidecars and operation logs are not newly added en masse to Git. No stable public raw-data release URL has been established. Therefore the included example is independently runnable from the repository; reproducing *all* fitted planes, detectors and raw-data metrics is not yet repository-only reproducible. Do not claim otherwise.

Original analysis scripts live under `scripts/`. Several pilot/batch scripts hard-code historical paths and output names, or dispatch hardware. Read their source and `--help`; do not run capture scripts as offline examples. Saved-file calibration (`calibrate_recording.py`, `refine_calibration.py`) uses versioned output paths. Static event/APS and ND analyses require their named native recordings, frozen models and sidecars.

Historical global calibration plotting can overwrite a shared plot; use the versioned recording/refinement workflows. The October blurred intrinsics and superseded guided stills must not be mixed into the refined take06 model.

## Software verification

```powershell
python -m pytest -q
node tests/test_rig_dashboard.cjs
```

These are synthetic tests; they do not move the rig, validate laser controls, establish optical settling or prove physical synchronisation. The latest recorded run and scope are in [VERIFICATION.md](VERIFICATION.md). Recorded exact full-environment dependencies are in `requirements.txt`; the offline dependencies are in `requirements-offline.txt`.

## Report

`report/main.tex` is the reviewed 8 November report, based on Kailas's live Overleaf revision with scientific-claim and reproducibility corrections. The compiled PDF is `report/report_submission_20261108.pdf`; the earlier 3 November draft remains retained separately. Compile using the supplied unchanged `IEEEtran.cls`, BibTeX and pdfLaTeX. All body content fits within six pages including references in the checked output. The live Overleaf main file is `project_report_submission_20261108.tex` in project `6ae7c03744c9b8a04aa627c3`. Repository copies use `figures/` paths.

The ND signal figure is generated from retained condition means and sample SD values, without new acquisitions: `python scripts/regenerate_nd_summary_figure.py`. This figure does not estimate optical transmission. Figures and tables distinguish physical depth, image occupancy, repeatability and shared-calibration limitations. Team final review and remaining physical evidence are listed in `docs/KAILAS_SUBMISSION_CHECKLIST.md`.
