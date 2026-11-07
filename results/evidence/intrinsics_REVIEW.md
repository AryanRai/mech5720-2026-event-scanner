# Take 6: refined camera-intrinsics result

## Outcome

**The existing recording was sufficient to obtain a substantially cleaner working intrinsic-calibration candidate. No new pictures were taken.** The original raw recording, images, first fit and reserved-view membership remain unchanged. Nothing was installed into the live camera/default calibration path.

| Quantity | Original audit fit | Refined candidate |
|---|---:|---:|
| Training views | 20 | 17 |
| Reserved views | 5 | Same 5 |
| Training RMS reprojection error | 0.6832 px | 0.2351 px |
| Reserved per-view RMS range | 0.1776-2.5315 px | 0.1990-0.2965 px |

Errors are **native 240 x 180 image pixels**, not millimetres. Refined values describe corner redetection plus the documented pre-fit exclusions; the training counts differ, so this is not a pure single-factor detector benchmark.

## What was corrected

The old conventional detector/refinement displaced some corner observations, visibly including frame 181 and several reserved images. All original 25 candidate images were re-detected using OpenCV's sector-based checkerboard detector, uniformly applied at 4x interpolation with accurate/exhaustive search. Coordinates were mapped back to native pixel centres. A separate 2x redetection checked localisation consistency; a projective grid check flagged malformed grids before fitting. No synthetic corner positions were substituted and no points were hand-painted.

The pre-fit gates were: cross-scale disagreement p95 <=0.5 px and maximum <=1 px; grid/homography residual p95 <=1 px and maximum <=2 px. These are disclosed diagnostic heuristics, not externally mandated calibration limits. Homography residual can include actual lens distortion. They were specified before observing the refined model's error, not adjusted to lower its RMS.

Three training images were excluded, with original files retained:

- **445:** disagreement between detector scales, on a relatively small target image.
- **714, 736:** projective-grid/corner-anomaly check failed.

Frame 181 was retained after image-based redetection: its training residual changed from about 2.76 px in the old fit to 0.19 px. All five original reserved images were retained and redetected; none was removed to improve the reported result. The corrected-corner contact sheet was visually inspected, including the formerly misplaced corners. `corner_audit.json` stores native coordinates, image hashes, detector diagnostics, split and exclusions.

## Model and sensitivity

Primary five-coefficient model (same model family as original):

```text
K = [307.0201,   0,       115.7638]
    [  0,     306.8715,   104.0087]
    [  0,       0,         1     ]
distortion [k1,k2,p1,p2,k3] =
[-0.282449, 0.553498, 0.00364074, 0.00104239, -0.898634]
```

Removing one training view at a time produced fx 305.90-307.60 px, fy 305.68-307.43 px, cx 113.21-116.79 px and cy 101.64-106.47 px. These are sensitivity ranges, **not independent confidence intervals**.

A secondary model fixing k3 to zero gave nearly identical training error (0.23515 px), reserved errors (0.19979-0.29660 px), and focal lengths (307.006 / 306.859 px). This is evidence that the main intrinsics are not changing dramatically with this particular model simplification; it does not establish higher-order distortion accuracy throughout unobserved image regions. The primary model was not chosen by minimising reserved errors.

## What this supports, and what it does not

- Supports using the saved candidate for the **next offline geometry/calibration stage**, with the same optical configuration and resolution. No more full retakes are justified merely by the former global dark-pixel rejection rule.
- Reserved images were already viewed during the earlier diagnosis. They remain excluded from fitting, but are **not an untouched final test set**. Their board poses were fitted for evaluation with fixed intrinsics.
- This is camera-intrinsic evidence, **not independent depth accuracy**, laser-plane calibration, servo-angle calibration or physical timing alignment.
- Target pitch is user-reported 18 mm. Verify printed geometry/flatness and measurement uncertainty before making metric claims; corner fit alone cannot validate the physical target.
- Current physical lens/focus/spacer configuration must match the recording before applying this model. Replugging USB alone is not an optical recalibration, but physical remounting or refocusing can invalidate the candidate.
- Some training frames are temporally adjacent; per-view residuals and leave-one-view-out sensitivity are not independent experimental repeats. A later physical depth/geometry validation must remain separate.

## Reproduce and files

```powershell
.venv/Scripts/python.exe scripts/refine_calibration.py --source outputs/calibration/take06_replug_boardroi_20261102 --output outputs/calibration/NEW_REFINEMENT_DIRECTORY
```

The output directory must not already exist. No hardware is opened.

- `refined_intrinsics.json`: full models, original/refined metrics, split, exclusions and sensitivity results.
- `corner_audit.json`: image hashes, original frame IDs, corrected corner observations and exclusion reasons.
- `refined_corner_contact_sheet.png`: visual corner audit; includes excluded candidates for transparency.
- `reprojection_comparison.png`: per-view error comparison, with native pixel units.

Underlying raw SHA256: `34ea3e8d2833488ba435543e07fdaea1f5fbde5f967f01df735692e6f04ddf49`.
Detector/reference: https://docs.opencv.org/4.13.0/d9/d0c/group__calib3d.html (sector-based checkerboard and camera calibration functions). The installed local library reports OpenCV 5.0.0; this audit records the actual local computations rather than assuming documentation version equivalence.

Verification: 15 focused calibration/refinement tests passed. The full suite had 75 passes and one Windows loopback connection-abort failure (`test_loopback_http_token_origin_and_get`); that unchanged test passed on an isolated rerun. No security settings or unrelated control code were changed. Raw recording hash was rechecked and matches the source above.

**Next:** use this versioned candidate for the projector-plane calibration workflow and validate reconstructed known geometry, after checking current optics match and measuring the printed target/ground truth. Do not claim scanner success from the sub-pixel reprojection error alone. Hardware operation remains subject to `AGENT_RIG.md` and approved laser controls.
