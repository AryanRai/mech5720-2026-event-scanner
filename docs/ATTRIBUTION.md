# Attribution and documentation references

University of Sydney, MECH5720, 2026: **Event-Based Structured-Light 3D Scanner**.

Team: Aryan Rai, Aditya Solanki, Kailas Viswanathan Anilkumar, Nadeen Periyasamy and The Son Le. Proposal responsibilities: geometry/calibration/evaluation; DAVIS/filtering/reconstruction; mechanics; embedded control/timing/feedback; experiments/ground truth/statistics, respectively. These are proposal roles, not a verified final contribution statement; all members contributed to integration/report/talk.

## Source provenance

This public snapshot derives from Aditya Solanki's original team scanner repository and the updated private fork `AryanRai/mech5720-2026-structured-light`, commit `bdf07ec54bdb55d9ba90c700ac1893e37c0c7c85`. It preserves the existing team code, retained evidence and attribution. Private Git history is not included; authorship is not claimed by the publisher alone.

## Scientific foundations

- Matsuda, Cossairt and Gupta, MC3D, 2015: motion-contrast sensing with scanned illumination.
- Muglikar, Gallego and Scaramuzza, ESL, 2021: event-based structured light and spatio-temporal consistency.
- Gallego et al., Event-based Vision: A Survey, 2022.
- Zhang, A Flexible New Technique for Camera Calibration, 2000.

Full bibliographic entries and links are retained in [report/references.bib](../report/references.bib). Their performance is not attributed to this prototype. Lab reports are contextual course references; no lab numerical result is reused as a project measurement.

## Software, CAD and illustrations

The project uses iniVation dv-processing, OpenCV, NumPy, Matplotlib, Arduino tooling and Python/JavaScript libraries under their respective licences. The supplied IEEEtran class retains its original notice. The downloaded ICCP skeleton is credited in `report/main.tex`. Existing firmware notes are retained as historical upstream documentation; the authoritative interpretation of ADC/PWM is in the build guide.

OpenAI Codex assisted software, analysis, documentation, CAD preparation and illustrations. Team members must review final contributions and AI attribution against unit rules and retain drafts/research/AI materials for the required period. CAD renderings are intended design; the triangulation diagram is conceptual. Photographs and scientific plots are retained evidence with explicit provenance.

## Don's repository examples

Read from the [Ed post "Github sites", 3 November 2026](https://edstem.org/au/courses/38151/discussion/3699857), reviewed 7 November:

- [One Pixel BLE Camera](https://github.com/aboudou/onepixelblecamera): hardware photographs, bill of materials, firmware/assembly explanation, demonstrations and explicit limitations.
- [PlenoptiCam](https://github.com/hahnec/plenopticam): clear overview/results, installation and usage paths, example datasets and citation information.

We use these as documentation-structure references. No code, images, measured results or licence from either project is copied into this scanner.

## Licensing status

At the repository publisher's instruction on 8 November 2026, original project software and accompanying software documentation are distributed under the [MIT License](../LICENSE), copyright 2026 MECH5720 Event-Based Structured-Light Scanner contributors. This records the publisher's licence selection, not a claim that separate consent from every contributor was independently verified. Third-party software, dependencies, the supplied IEEEtran/ICCP template, course materials and other separately attributed content retain their existing terms and notices; the MIT grant does not override those terms or grant rights in content the contributors do not own. Team authorship and attribution are preserved.
