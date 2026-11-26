# Verification checklist

## REQ-001 Input inspection
- [x] Implementation and verification complete
### Implementation
pdf_input.py, cli.py
### Verification
`.venv/bin/python -m pytest tests/test_req_001*.py` plus relevant integrated example and output inspection.

## REQ-002 Ordered stroke fonts
- [x] Implementation and verification complete
### Implementation
fonts.py, data/, scripts/fetch_fonts.py
### Verification
`.venv/bin/python -m pytest tests/test_req_002*.py` plus relevant integrated example and output inspection.

## REQ-003 PDF layout
- [x] Implementation and verification complete
### Implementation
pdf_input.py, geometry.py
### Verification
`.venv/bin/python -m pytest tests/test_req_003*.py` plus relevant integrated example and output inspection.

## REQ-004 SVG input
- [x] Implementation and verification complete
### Implementation
svg_input.py, geometry.py
### Verification
`.venv/bin/python -m pytest tests/test_req_004*.py` plus relevant integrated example and output inspection.

## REQ-005 Artifacts
- [x] Implementation and verification complete
### Implementation
artifacts.py (including interactive preview), scripts/check_ui.mjs
### Verification
`.venv/bin/python -m pytest tests/test_req_005*.py` plus relevant integrated example and output inspection.

## REQ-006 A1 mini calibration
- [x] Implementation and verification complete
### Implementation
profile.py, docs/CALIBRATION.md
### Verification
`.venv/bin/python -m pytest tests/test_req_006*.py` plus relevant integrated example and output inspection.

## REQ-007 G-code
- [x] Implementation and verification complete
### Implementation
gcode.py
### Verification
`.venv/bin/python -m pytest tests/test_req_007*.py` plus relevant integrated example and output inspection.

## REQ-008 Execution packaging
- [x] Implementation and verification complete
### Implementation
package.py
### Verification
`.venv/bin/python -m pytest tests/test_req_008*.py` plus relevant integrated example and output inspection.

## REQ-009 Independent validation
- [x] Implementation and verification complete
### Implementation
validate.py
### Verification
`.venv/bin/python -m pytest tests/test_req_009*.py` plus relevant integrated example and output inspection.

## REQ-010 Usable delivery
- [x] Implementation and verification complete
### Implementation
README.md, docs/PDF_CONTRACT.md, examples/, tests/, pyproject.toml
### Verification
`.venv/bin/python -m pytest tests/test_req_010*.py` plus relevant integrated example and output inspection.

## Reconciliation evidence

All requirement commands executed successfully. Exact commands, exit codes and counts: `docs/verification-results.json`. Total: 139 tests. JavaScript syntax and actual event handlers exercised with `node scripts/check_ui.mjs`. Two-page Japanese note and Matplotlib graph rendered and visually inspected. Wheel built, installed and exercised from an unrelated cwd. Runtime socket binding and physical printer execution are environment/hardware checks and are explicitly not claimed verified.
