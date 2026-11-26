# Current-contact test

## Requirements
- REQ-C01: Use the user's physically established current paper contact as the relative Z reference. Never assume absolute Z=0, reset coordinates, home, heat or extrude.
- REQ-C02: Compensate measured pen offset X=0, Y=-30.8mm. Draw only one 5mm-em sentence near the bed centre, inside nominal nozzle/pen limits.
- REQ-C03: Raise the pen before XY motion, use relative Z-only moves and absolute XY-only moves, finish 5mm above initial contact, and independently compare all drawing strokes against the source.
- REQ-C04: Provide contact and air-run G-code/3MF, preview and clear instructions requiring the same physical contact reference before every run. Package checksum and content must match validated G-code.

This is a one-off current-state test, not a replacement for the full notebook's absolute-Z calibration. No printer command is sent by software.
