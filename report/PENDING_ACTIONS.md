# Replace report placeholders with evidence, not inferred success

## G1 — independently measured geometry (does not depend on continuous scanning)

Fill: target drawing/photo; measured step/board dimension; instrument and resolution; repeated physical readings; reference datum/normal; n acquisitions; signed bias/RMS/step-height error with units and repeat variation. Distinguish step-height accuracy from absolute camera-Z accuracy. Do not align every test to remove bias. Retain all failures/exclusions.

## G2 — continuous timing, motion and feedback-to-plane association

Fill: observable shared physical timing reference; fitted offset/rate and held-out prediction; latency/jitter interpretation; reset/discontinuity handling; measured feedback/plane mapping over travel; direction dependence and optical settling. Validate moving-stripe reconstruction on held-out geometry. PWM/ADC metadata and timestamp overlap are not sufficient.

## G3 — speed study (depends on G2)

Fill: tested durations/speeds, matched event/APS scene/motion/optics and evaluator, fixed expected-surface mask, independent sweeps per condition, RMS/bias/coverage and variation. Four durations and five repeats are a proposed design, not a faculty-mandated count. No curve or superiority claim until measured.

## G4 — calibrated attenuation and true3D completeness (not all dependent on G2)

Fill: ND labels or measured transmittance with measurement uncertainty/response limits; geometry-preserving insertion/removal checks; several levels; fixed acquisition/detector protocol; declared usability criterion. A static stepped-target attenuation study can proceed independently of continuous scanning if geometry is valid. Current0.43digitalratio is not transmittance. One unknown filter supplies only a configuration comparison, not a weakest-level curve.

For3D completeness, define a bounded independently known expected surface/grid and visibility rules, then a distance tolerance for recovered samples. Current image-space coverage remains a valid separately labelled metric; it does not become3Darea completeness by changing its name.

## G5 — build, scope and reproducibility verification

Fill: as-built baseline and datums/uncertainty; independently checked printed pitch/flatness; exact current lens/spacers/focus/iris; servo/controller/laser/driver labels and wiring; approved controls; actual cost/parts links; photographs and build pitfalls. Add controlled distance/ambient/material tests and a defined latency benchmark if pursued; honest uncompleted scope is acceptable.

Verify public/marker-access repository URL and coordinator arrangements, naming/topic/licence, stable data release, dependency versions, one-command key-figure reproduction and complete rebuild instructions. Do not change repository visibility or publish automatically. Confirm team roles/contributions, five-minute talk attendance and required AI attribution/retention.

## Delivery still outstanding

Send **only** the checked updated PPTX to the MECH57/MECH5720 WhatsApp group, with no caption or accompanying message. User explicitly authorised this. It was not attempted because the local browser gate continued to report disabled after the user reported enabling it. Do not claim it was sent; when access is restored, inspect the exact group before uploading and verify the attachment appeared once. No live Overleaf edit was made; this downloaded-template source ZIP is ready to upload.


## Revision 02, 3 November 2026

Added the separately recorded five-line demonstration (821 APS frames; 284,490 events), raw-source hashes, trace warnings at1602/1647us and explicit temporal-composite captions. This is not new calibrated depth. Corrected dataset traceability: original379points/5positions/10ms; later359points/4directly fitted positions/3ms; later1929points/21positions/interpolated intermediate planes/3ms; current960points/20positions/35ms. Original sparse overlay uses a later100ms reference photo for visibility; it is an illustrative overlay without independently validated cross-session registration, not a photo from the10ms recording. Continuous event-based3D remains unvalidated and future work. Unverified build/team/access items remain placeholders.


LIVE OVERLEAF UPDATE COMPLETE: project6ae7c03744c9b8a04aa627c3 now compiles project_report_revised.tex, with scanner_cad_review.png and five_line_demonstration.png uploaded at root. Existing iccp26_template.tex retained unchanged. Source backup retained in evidence/overleaf_before_update_20261103.zip. Live PDF downloaded, six pages visually checked, zero errors; one float-layout warning and underfull spacing diagnostics remain. Earlier statements that live Overleaf was untouched are historical. Outstanding scientific/build/team placeholders remain. WhatsApp delivery status is unchanged.
