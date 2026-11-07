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

Coverage reproduction passed again: APS 939/13715 (6.8465184105%), events 478/13715 (3.4852351440%). All 60 curated evidence files passed checksums. No hardware operations or new measurements were performed. Code functionality was unchanged; no new full-suite run is claimed. Author approval, licence agreement, complete as-built verification and stable full raw-data release remain outstanding. See `KAILAS_SUBMISSION_CHECKLIST.md`. No Canvas submission was made.
