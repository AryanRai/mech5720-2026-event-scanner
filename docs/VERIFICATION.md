# Verification record â€” 7 November 2026

- Full local Python suite: **117 passed, 1 failed** in25.45s. The failure was `test_loopback_http_token_origin_and_get`, Windows `ConnectionAbortedError/WinError10053` while checking rejected HTTP requests.
- The unchanged failed test was rerun alone: **1 passed** in0.89s. This is not a claim of one clean full118-test run.
- `node tests/test_rig_dashboard.cjs`: PASS with fake serial, including executor actions, disabled/interlock refusal, abort and final-off/status checks. Synthetic only.
- `python examples/coverage/regenerate.py`: source hash passed; reproduced APS939/13715 andEvents478/13715 exactly. Offline, no device access.
- Full-suite failure did not justify changing authentication, Origin checks, local security settings or weakening tests. None was changed.

A clean exported-tree check and link/manifest audit are recorded below after running them. No physical capture, motion, emission or firmware upload was performed during this repository update.

## Exported Git tree verification

An export of the selected Git index was tested in a separate scratch directory, without the local working outputs or new raw acquisitions. The exported tree passed **118 Python tests in17.37s**, reproduced both coverage numerators/denominator and passed all58curated-file checksums. The earlier117pass/1failure local run and isolated passing rerun remain recorded above. Documentation local-link checks passed. Staged-path review excludes runtime tokens, bulk raw data, scratch/authoring outputs and WhatsApp invite links; a credential-pattern scan found no matches. CAD STEP is treated as a binary asset; its source geometry is preserved.


## Submission report verification, 8 November 2026

The live Overleaf main is `project_report_submission_20261108.tex`, revised from the teammate's current source with earlier files preserved. The final PDF has six pages including references, no unresolved drafting placeholders and zero compiler errors. All six pages were rendered and inspected; the ND axis label was corrected and rechecked. One IEEE float-layout warning and underfull spacing diagnostics remain, with no observed clipping or overlap. Every figure/table is referenced.

Coverage reproduction passed again: APS 939/13715 (6.8465184105%), events 478/13715 (3.4852351440%). All 60 curated evidence files passed checksums. No hardware operations or new measurements were performed. Code functionality was unchanged; no new full-suite run is claimed. Author approval, complete as-built verification and stable full raw-data release remain outstanding. See `KAILAS_SUBMISSION_CHECKLIST.md`. No Canvas submission was made.


## Final licence and submission package, 8 November 2026

MIT LICENSE added at the publisher's explicit instruction for original project software and accompanying software documentation, preserving third-party notices and contributor attribution. The live Overleaf main and repository source now state this licence and retain the clickable public repository URL. The exported PDF remains six pages including references, with zero compiler errors and the previously recorded float/underfull diagnostics. The changed sixth page was rendered and visually checked: no overlap or clipping. PDF annotation inspection confirms the clickable repository URL, and text checks find the MIT notice and no drafting placeholders. No new measurements or hardware operations occurred. Canvas submission and author declarations have not been performed.

The final staged tree was exported into a new separate directory and checked without working-output dependencies: coverage regeneration reproduced APS 939/13715 and events 478/13715, and all 60 evidence checksums passed. Existing Python dependencies were reused; this is not an independently provisioned second-computer installation or a new full test-suite run.


## Visual report revision, 8 November 2026

The live Overleaf main is now `project_report_submission_visuals_20261108.tex`; earlier sources remain preserved. Added the documented static pipeline, actual five-line APS/event inputs, intrinsic corner-refinement comparison and an ND photograph/signal composite. Existing point clouds, coverage, reserved-board error, repeatability, timing and hardware figures remain. All twelve figures and one table are referenced; all graphic inputs exist. The compiled PDF has seven total pages: all body content and attribution fit on pages 1–6, and page 7 contains references only. All seven pages were rendered and visually inspected without observed clipping or overlap. Overleaf reports zero errors, zero warnings and ten underfull-box informational diagnostics. Scientific values and limitations remain unchanged; no new hardware operation or measurement occurred. No new full test-suite run is claimed.

All 62 curated evidence checksums passed after the PDF and figure update. Figure/table references and graphic paths passed; `git diff --check` passed.
