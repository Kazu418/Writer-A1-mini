# Plan

## Change Type
Enhancement: current-contact test export.

## Task List
- REQ-C01/C02/C03: `src/plotnote/contact_test.py`, `tests/test_contact_test.py`; validate constrained relative-Z dialect and exact source geometry; reject altered reference, offsets, modes, bounds, heaters and extrusion.
- REQ-C04: Extract shared OPC container writer in `package.py` while retaining the original absolute-profile validation gate. Generate local test assets in `output/contact-test/`. Verify package reads, thumbnails, checksum and no normal start macros.

## Analysis Report
PASS: all four requirements have implementation and verification gates. The existing absolute-Z exporter remains strict. Relative-Z validation tracks height above the manually established contact reference; no unknown absolute Z is invented.
