# PlotNote pipeline specification

## Scope
PDF text and vector notes to ordered pen strokes on A1 mini. All pages processed; no raster conversion.

## Requirements

### REQ-001 [NEW] Input inspection
CLI inspects every PDF page for size, Unicode text, vector content, images, annotations, rotation and unsupported paint effects; aggregate precise page diagnostics before export.

### REQ-002 [NEW] Ordered stroke fonts
Japanese kanji/kana, ASCII, Greek and common math symbols use centerline strokes. Preserve individual stroke order/direction; unsupported glyphs cause explicit errors with Unicode and location.

### REQ-003 [NEW] PDF layout
Replace text at original character positions and orientations using character advance and font metrics. Preserve vector lines, rectangles, curves, graph paths, transforms and clipping; reject unsupported effects. No implicit scaling or cropping.

### REQ-004 [NEW] SVG input
Support physical units/viewBox, groups/transforms and standard path/line/polyline/polygon/rect/circle/ellipse primitives. SVG text requires explicit conversion or rejection. No external resources/scripts.

### REQ-005 [NEW] Artifacts
Produce multipage ordered stroke SVG, faithful path PDF/PNG and standalone interactive HTML preview showing pen-up travel and stroke playback; metadata includes counts and diagnostics.

### REQ-006 [NEW] A1 mini calibration
Profile stores measured XY offset (pen minus nozzle), paper lower-left, physical paper size, safe nozzle bounds, pen contact/lift heights and feed rates; validate finite numbers and limits. Supply calibration template, guide and air-run mode.

### REQ-007 [NEW] G-code
Export ordered strokes with Y inversion, measured offset compensation, safe lift before XY movement, final lift. Fail if any nozzle or pen path exits calibrated reachable area. No homing/heating/extrusion/probing.

### REQ-008 [NEW] Execution packaging
Export raw G-code and .gcode.3mf with content types, relationships, model metadata, plate G-code and checksum; do not send to printer. Explain manual homing, mounting, paper placement and per-page runs.

### REQ-009 [NEW] Independent validation
Parse all generated motion and enforce command allowlist, numeric finiteness, bounds, feed rates, no unlifted XY travel, no out-of-profile Z; invalid profiles/files cannot export.

### REQ-010 [NEW] Usable delivery
Installable CLI with Japanese documentation, PDF authoring contract including exact page dimensions/orientation, supported characters/symbol list, examples, reproducible setup and automated regression tests.

## Acceptance
All automated checklist gates pass; Japanese mathematical example visually reviewed; export verified by independent parser. Physical printing is explicitly unverified until the owner performs calibration and air-run.
