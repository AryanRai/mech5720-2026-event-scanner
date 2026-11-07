# Evidence status and remaining work

Last scientific evidence reviewed: 3 November 2026. Repository packaging review: 7 November 2026.

## Demonstrated

- Team-built scanner mechanics and camera/controller integration.
- Versioned candidate intrinsics and twenty static command-indexed light planes.
- Partial APS and static-event shoe profiles; reserved-board errors with explicit shared-calibration limitation.
- Actual APS comparison, repeated static acquisitions, fixed-mask image occupancy, optical-edge timing diagnostics and an unknown-filter configuration experiment.
- A self-contained repository example regenerating the coverage figure from included retained coordinates/photo/mask.

## Pending independently of continuous scanning

- Independently measured board/step dimensions, datums and uncertainty; repeated absolute/signed/step errors.
- True 3D surface completeness with a bounded expected reference surface.
- Known/measured attenuation levels, geometry-preserving controls and a declared usability criterion.
- Exact component/optics labels, actual driver/wiring, approved controls, as-built dimensions, costs and complete rebuild verification.
- Controlled ambient/material/distance robustness and a processing-latency benchmark.
- Stable remote native-data archive and agreed licence.

## Continuous-scanning blocker

Continuous event-based 3D reconstruction is not yet demonstrated. The camera--servo timing and moving light-plane mapping are insufficiently validated to assign every event a reliable plane during motion. Matching timestamp ranges, host arrival time, PWM and nominal ADC conversions do not solve this. Validate observable shared timing, held-out prediction, reset handling, direction dependence and moving geometry first. The continuous speed-performance experiment depends on that validation.

## Repository administration

The public standalone submission repository is `AryanRai/mech5720-2026-event-scanner`, with topic `mech5720`. It contains the reviewed project snapshot from private-fork commit `bdf07ec54bdb55d9ba90c700ac1893e37c0c7c85`, retaining team attribution without copying private Git history. The original repository and the private fork remain unchanged. A project-wide licence is still unresolved; public visibility alone does not establish open-source reuse rights. The project is a draft evidence package, not a claim that every rubric criterion is complete.
