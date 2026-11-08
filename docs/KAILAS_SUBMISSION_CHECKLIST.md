# MECH5720 submission checklist for Kailas

Prepared 8 November 2026. Based on the faculty Major Project brief (21 September 2026), the live Canvas Major Project rubric reviewed 7 November, the team feedback-servo/ND pitch and retained 2-3 November results. This is a plan for improving the evidence, not a prediction or guarantee of full marks. No new experiment was performed during this revision.

## 1. Finish these before submitting: no new experiment needed

- [ ] Review the revised Overleaf main file `project_report_submission_20261108.tex`. It incorporates the current `iccp26_template.tex` revision rather than overwriting it. Keep the downloaded pre-edit source ZIP as a backup.
- [ ] Every author reads and approves the final paper, authorship and AI attribution. Check the wording of reported servo/laser identities and verbal advice against the team's records. Reported advice is not independent verification of optical class or electrical design.
- [ ] Use the PUBLIC repository https://github.com/AryanRai/mech5720-2026-event-scanner in the paper and submission. It is standalone, with the required unit/year name and `mech5720` topic. The similarly named structured-light repository remains a private fork.
- [x] MIT LICENSE added at the publisher's instruction on 8 November 2026 for original software/documentation, with existing third-party notices preserved. All authors should review licensing scope during final approval; independent contributor consent is not asserted.
- [ ] Complete the parts list using actual purchases: precise product links, quantities and actual cost where available. Retain reported/unverified labels as such. Do not substitute proposed R4/Class 1 parts for the installed R3/reported Class 3 line module.
- [ ] Make a fresh checkout on another computer/account and run `python -m pip install -r requirements-offline.txt`, `python examples/coverage/regenerate.py`, and `python scripts/verify_repository_evidence.py`. Expected unique bins: APS 939/13715 (6.8465%); events 478/13715 (3.4852%). Record versions, commands and output. Do not run hardware scripts for this check.
- [ ] Publish the recordings needed for key calibration, board, repeatability, timing and ND results at a stable public archive if too large for Git. Include checksums, run/configuration IDs, frozen models, exclusions, scripts and exact regeneration commands. The current coverage example is self-contained; the complete raw-data pipeline is not yet repository-only reproducible.
- [ ] Confirm the final PDF has at most SIX body pages, excluding references. All captions must explain the condition, units, method and meaning of uncertainty. Every figure/table must be cited and explained in the main text. No red placeholders, broken citations, clipped plots or unsupported claims.
- [ ] Submit ONE group PDF through Canvas with the public repository link. Confirm the correct group and upload, then check the submission receipt. This workflow does not submit the assignment or accept declarations on the team's behalf. Do not infer an extension or late-penalty exemption; check the actual course arrangements.
- [ ] Retain drafts, research materials and AI outputs for one year under the course rules. Complete the required peer assessment. Do not treat a mark estimate from an assistant as a marking decision.

## 2. Rubric map: what the strongest evidence would require

The live rubric has SIX report criteria totalling 75 project points, converted to 15 unit marks. It is not five equally weighted categories. The talk contributes the remaining 25 project points (5 unit marks).

| Report criterion | Max | Present evidence | Highest-value remaining action |
|---|---:|---|---|
| Principle of operation | 11 | Ray-plane model, camera calibration, explicit static fallback, cited academic precedent | Check definitions/units, explain error sources, preserve the distinction between command and physical angle |
| Design and implementation | 15 | Physical custom mounts/cradle/pedestal, controller, dashboard, acquisition and reconstruction | Verify as-built datums, optics, actual wiring/driver/interlock and parts; add a labelled assembly/wiring figure |
| Experimental rigour | 11 | Frozen A-C model, reserved D, controls, repeats, retained exclusions/failures | Add independently measured geometry and repeat whole acquisitions; record measurement resolution and uncertainty |
| Results and analysis | 15 | Point clouds, APS/event comparison, fixed-mask coverage, repeatability and negative ND result | Independent signed depth/step errors plus repeat variation; controlled comparisons with a fixed expected-surface denominator |
| Reproducibility | 11 | Public code, CAD, photos, curated evidence, hashes and runnable coverage example | Full stable data release, precise rebuild instructions and independent fresh-checkout verification |
| Presentation | 12 | ICCP two-column structure, quantitative abstract, figures and limitations | Verify final six-page body, concise writing, clear plots/captions, references and no placeholders |

Exemplary evidence is the target, not a guarantee. Honest negative results are acceptable. Completing the proposal exactly is different from satisfying the rubric: the static fallback was allowed, but moving an unfinished experiment into future work does not produce its missing evidence.

## 3. Best next physical work: independent geometry first

This is the strongest next improvement to rigour/results and does NOT require continuous scanning. Keep camera/laser/servo mounts fixed. Measure a matte stepped target or independently positioned boards with a suitable instrument. Record the drawing/photo, step dimensions, instrument resolution, repeated readings, datums and uncertainty. An arbitrary shoe has no independent reference depth.

Freeze calibration and detectors before evaluation. Acquire repeated independent scans of the reference target using the validated static protocol and actual APS/event data from the same conditions. Three or more trials is a useful small start; five is preferable if practical, not a faculty-mandated count. Keep failed detections and report support. Do not count pixels/events as repeats.

Report signed bias, depth RMS and/or step-height error in mm for each trial, plus across-trial variation with a clearly defined SD/range. Step-height accuracy and absolute camera-Z accuracy are different claims. Do not independently align each test cloud to erase bias. The existing reserved-D result shares K and the reported 18 mm scale; it cannot become independent ground truth by relabelling it. Measuring the board now does not prove historical flatness or pose.

## 4. Remaining proposed experiments, in practical order

1. **As-built verification:** check printed pitch and flatness; baseline/datums and uncertainty; actual lens/rings/focus/iris; servo/controller/laser labels; electrical supply/driver/interlock and approved controls. Use dated photos and an actual wiring diagram. Nominal CAD dimensions are not measurements. Recheck current rig readiness before any operation.
2. **Attenuation:** use a fixed filter holder and documented ND values or independently measured transmission. Obtain several levels plus no-filter controls while verifying unchanged stripe/geometry. Freeze exposure, detector settings and a predeclared usability rule. Repeat acquisitions; plot error/coverage/detection versus attenuation with units and repeat variation. The 0.4296 digital ratio is NOT measured transmittance. A static experiment can proceed before continuous scanning works.
3. **Physical completeness:** define the independently known bounded target surface and visible reference grid before testing. Declare tolerance and visibility rules, then report the fraction recovered for both methods. Keep current image-bin coverage separately labelled; it is not 3D surface-area completeness.
4. **Continuous timing and motion:** establish an observable physical reference in both clocks, fit offset/rate, validate held-out predictions and resets, and verify feedback/plane association during motion. The current 47.55 ms residual combines clock and optical/selection effects; it is not isolated jitter. Any hardware sync wiring needs verified voltage/interface compatibility; do not connect an assumed 5 V output directly to DAVIS.
5. **Speed study only after step 4:** use the same scene, optics, motion and evaluation support for event and actual APS processing. Repeat complete sweeps at a few feasible durations and plot error/coverage with repeat variation. Four durations/five repeats is a proposed design, not a compulsory count. Unequal integration must be disclosed.
6. **Optional robustness/latency:** test one controlled variable at a time (distance, ambient illumination, material), retain dark/specular failures, and define whether latency means processing time or end-to-end acquisition. Benchmark on the stated computer; do not call the static 12 s recording length processing latency.

## 5. Claims that must remain bounded

- 8.63 mm is equal-command RMS on one reserved pose, NOT mean absolute error or independent absolute accuracy. The matched 8.42 mm APS / 8.07 mm event subset has a different denominator. It has no independent repeated-test confidence interval.
- 960 APS and 494 event points are sparse partial shoe profiles, not a complete shoe. Their 1.65 mm disagreement does not prove either is accurate; both share calibration.
- 6.85% / 3.49% means fixed-mask native image-bin occupancy, not physical area completeness or detection precision.
- The repeatability table uses n=3 acquisitions per command. Its ray-wise SD metric is precision, not accuracy or uncertainty on the separate board RMS.
- 379 points/5 positions used 10 ms APS; 359/4 directly fitted and 1929/21 interpolated previews used 3 ms; current 960/20 used 35 ms. These changed conditions cannot isolate a density benefit.
- The unknown-ND test is a geometry-confounded configuration comparison. Fewer event candidates do not establish a general event-camera low-light limit.
- Static event reconstruction is demonstrated. Continuous event-based reconstruction, speed advantage and a calibrated attenuation threshold are not.

## 6. Talk requirements, if any delivery remains

Five minutes plus two minutes Q&A. All team members must attend their talk and the whole session under Don's clarification. Show the physical contribution, one actual measurement, APS/event results and limitations. The talk rubric is clarity 7, presentation 6, evidence 8, accuracy of claims 4. Report edits cannot retroactively change an already delivered talk.

Sources: faculty brief pp. 4-5; Canvas https://canvas.sydney.edu.au/courses/74043/assignments/727913; supplied 1 November clarification; retained feedback-servo/ND pitch. Team final approval and all new measurements remain outstanding actions, not completed claims.
