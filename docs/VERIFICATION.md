# Verification record â€” 7 November 2026

- Full local Python suite: **117 passed, 1 failed** in25.45s. The failure was `test_loopback_http_token_origin_and_get`, Windows `ConnectionAbortedError/WinError10053` while checking rejected HTTP requests.
- The unchanged failed test was rerun alone: **1 passed** in0.89s. This is not a claim of one clean full118-test run.
- `node tests/test_rig_dashboard.cjs`: PASS with fake serial, including executor actions, disabled/interlock refusal, abort and final-off/status checks. Synthetic only.
- `python examples/coverage/regenerate.py`: source hash passed; reproduced APS939/13715 andEvents478/13715 exactly. Offline, no device access.
- Full-suite failure did not justify changing authentication, Origin checks, local security settings or weakening tests. None was changed.

A clean exported-tree check and link/manifest audit are recorded below after running them. No physical capture, motion, emission or firmware upload was performed during this repository update.

## Exported Git tree verification

An export of the selected Git index was tested in a separate scratch directory, without the local working outputs or new raw acquisitions. The exported tree passed **118 Python tests in17.37s**, reproduced both coverage numerators/denominator and passed all58curated-file checksums. The earlier117pass/1failure local run and isolated passing rerun remain recorded above. Documentation local-link checks passed. Staged-path review excludes runtime tokens, bulk raw data, scratch/authoring outputs and WhatsApp invite links; a credential-pattern scan found no matches. CAD STEP is treated as a binary asset; its source geometry is preserved.
