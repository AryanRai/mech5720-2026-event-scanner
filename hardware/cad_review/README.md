# DAVIS240C scanner — review assembly

Open DAVIS240C_Scanner_Review.step in SolidWorks after extracting this ZIP. Units: mm.

The design retains the plain flat base, upright rear camera-frame style and separate servo support from your uploaded Scanner_Preview.png. It combines these with the newly approved raised studded object holder. The old 400 x 1000 mm footprint is superseded by the compact two-section layout.

## What is supplied now

- DAVIS240C_Scanner_Review.step: the complete positioned assembly, with 37 named components and 65 solids. It is not one fused printable object.
- DAVIS240C_Scanner_Preview.png: render of this actual CAD geometry, not an AI concept picture.
- build_review.py and render_review.py: editable regeneration source (CadQuery 2.7, NumPy, Pillow). The builder also generates individual STEP/STL files when run.
- validation.json: component inventory, bounding boxes and geometry checks.

This is a STEP assembly compatible with SolidWorks, not a native SLDASM/SLDPRT file. STEP contains the named component geometry and positions but no native sketches, feature history or assembly mates. The import result depends on your SolidWorks settings. You can save imported geometry to native SolidWorks format and add new features; the original source parameters remain in build_review.py.

## Seven custom components (one of each)

1. Camera/laser base: 240 x 220 x 8 mm plate, 240 x 240 mm including its locating tongues.
2. DAVIS upright camera bracket, underside mounting shoe and supporting ribs, made as one part.
3. Fixed servo bracket.
4. Rotating laser cradle.
5. Lower laser clamp.
6. Upper laser clamp.
7. Object base with integrated pedestal and four studs: 240 x 220 mm footprint, 60.3 mm overall height.

Once you approve the assembly and confirm interfaces, these seven parts can be supplied as individual STEP files for CAD and STL files for slicing. Camera, lens, servo, horn, laser, real LEGO plate, minifigure and screws are purchased/reference components and must not be printed from this assembly.

## Connections and movement

The camera and servo supports bolt onto the blue base. The camera attaches through its underside tripod mounting point; the rear frame preserves the requested appearance and has a large opening behind the exposed circuit boards. It does not reuse the old Pi-camera case screw pattern.

Only the servo horn, orange cradle, clamp and laser rotate. The camera and object stay fixed. The model shows one scan angle and contains no motion mates.

Two bottom lap tongues on the blue base enter matching underside pockets in the green base. Two M4-like joining screws, washers and nuts clamp the sections together. Proposed joint clearance is 0.3 mm each side and above the tongues. Repeatability and stiffness must be checked on printed parts; reassembly can change optical calibration.

The object pedestal is a solid 18 x 18 mm column rising 50.5 mm above its base. Proposed stud geometry is 8 mm pitch, 4.8 mm diameter and 1.8 mm height. These are initial design targets, not verified print tolerances. A real plate clips onto the printed studs and holds the figure. There is no retaining wall or recess. Print a small stud-fit coupon before committing to the full base.

## Dimensions and hardware still to confirm

DAVIS240C published overall dimensions are H56 x W62 x D28 mm, with a quarter-inch tripod mount. The camera reference model uses this envelope with simplified housing/boards. It is not manufacturer CAD. Its optical centre is placed nominally 33.25 mm above the underside using the DAVIS drawing. The mounting shoe's screw position, contact surface, screw engagement and connector clearance need comparison with your physical camera. The screw is shown as a smooth envelope, not a usable thread model. The drawing places the bottom mount near the centre; the model uses a provisional centred interface.

The lens is an assumed 32 mm diameter envelope protruding 35 mm from the camera front. Your actual lens may differ. Current lens-front to nominal holder-centre distance is about 225 mm. Focus, field of view and scan coverage have not been established. Final distance must be set using the actual lens and a test image.

Servo body is provisionally 22.9 x 12.2 x 28.5 mm, with unverified shaft and ear locations. The horn is a placeholder disc with 12 mm fixing pitch. Laser is assumed diameter12 x length40 mm. The proposed split clamp has a 12.1 mm bore and 0.6 mm split gap. Check all against your actual servo, horn and laser before manufacturing. Fasteners have no threads or drive details; their final lengths and types are not specified by these envelopes.

The target mannequin and real LEGO plate reference are approximate representations, not accurate LEGO models. They are included only for layout review.

## Layout

Assembled base footprint: 240 x 440 mm. Camera/servo axis baseline: 130 mm. Camera and laser centre height: 82.5 mm from base underside. Camera axis XY=(-45,-45), servo axis XY=(85,-45), nominal holder centre=(0,225). Both aim toward the object at the displayed reference angle. The figure's feet use the rear stud row, 4 mm behind the plate centre.

## Checks performed

- Every generated component passed the CAD kernel validity check.
- Each of the seven custom components contains exactly one solid.
- Exported STEP reopened with the expected 65 solids.
- No custom-part pair overlap above 0.01 cubic mm in the shown position.
- No camera-envelope/bracket overlap in the shown position.

These checks do not verify thread engagement, print tolerances, full servo motion, mechanical strength or optical performance. The base footprints require sufficient printer build area and brim clearance. The parts have not been sliced, and weight/time limits have not been checked. This is the requested review model, not a fabrication release.

## Camera sources

Manufacturer DAVIS240 datasheet, physical dimensions on page2:
https://inivation.com/wp-content/uploads/2019/08/DAVIS240.pdf

Manufacturer DAVIS240C specifications, dimensions and tripod mount on page1:
https://inilabs.com/wp-content/uploads/2017/07/DVS-Specifications.pdf
