# Implementation plan

## Change Type
Enhancement — new local application.

## Task List

- Task 1: REQ-001 Input inspection. Files: pdf_input.py, cli.py. Dependencies: none. Success: requirement demonstrable through tests/test_req_001*.py and integrated CLI run.

- Task 2: REQ-002 Ordered stroke fonts. Files: fonts.py, data/, scripts/fetch_fonts.py. Dependencies: geometry/data model before consumers. Success: requirement demonstrable through tests/test_req_002*.py and integrated CLI run.

- Task 3: REQ-003 PDF layout. Files: pdf_input.py, geometry.py. Dependencies: geometry/data model before consumers. Success: requirement demonstrable through tests/test_req_003*.py and integrated CLI run.

- Task 4: REQ-004 SVG input. Files: svg_input.py, geometry.py. Dependencies: geometry/data model before consumers. Success: requirement demonstrable through tests/test_req_004*.py and integrated CLI run.

- Task 5: REQ-005 Artifacts. Files: artifacts.py (SVG/PDF/PNG and embedded HTML preview), scripts/check_ui.mjs. Dependencies: geometry/data model before consumers. Success: requirement demonstrable through tests/test_req_005*.py, JavaScript playback gate and integrated CLI run.

- Task 6: REQ-006 A1 mini calibration. Files: profile.py, docs/CALIBRATION.md. Dependencies: geometry/data model before consumers. Success: requirement demonstrable through tests/test_req_006*.py and integrated CLI run.

- Task 7: REQ-007 G-code. Files: gcode.py. Dependencies: geometry/data model before consumers. Success: requirement demonstrable through tests/test_req_007*.py and integrated CLI run.

- Task 8: REQ-008 Execution packaging. Files: package.py. Dependencies: geometry/data model before consumers. Success: requirement demonstrable through tests/test_req_008*.py and integrated CLI run.

- Task 9: REQ-009 Independent validation. Files: validate.py. Dependencies: geometry/data model before consumers. Success: requirement demonstrable through tests/test_req_009*.py and integrated CLI run.

- Task 10: REQ-010 Usable delivery. Files: README.md, docs/, examples/, tests/, pyproject.toml, requirements-lock.txt, scripts/bootstrap.sh, scripts/create_example.py, scripts/check_ui.mjs, server.py, data/workbench.html, PlotNote.command, plotnote launcher. Dependencies: completed pipeline. Success: requirement demonstrable through tests/test_req_010*.py, JavaScript interaction gate, wheel build/install, installed CLI, and integrated real-PDF run.

## Analysis Report
PASS: REQ-001 through REQ-010 appear in specification, task list, and verification checklist. Dependency order: model/geometry/fonts/profile, importers, artifact/export validation, CLI/docs/integration. No requirement lacks a planned gate. Optional network printer control intentionally outside user-requested file conversion scope.
