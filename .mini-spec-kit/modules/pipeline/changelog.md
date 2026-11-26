# Changelog — 2026-11-24

Implemented the complete PDF/SVG to ordered Japanese pen-stroke pipeline, physical-size SVG/PDF/PNG/HTML previews, A1 mini calibrated coordinate compensation, raw G-code and Bambu 3MF packaging, independent G-code parser, CLI, local workbench and Japanese operation/PDF contracts. Bundled 6,984 KanjiVG glyphs and Hershey fonts with licenses and provenance.

Corrected Unicode super/subscript placement, hidden/clipped/white text handling, invalid geometry, SVG page overflow, Matplotlib zero-area fill/stroke ticks, and playback restart at the end. Use a serial HTTPServer because PyMuPDF does not support multiple threads.

Verification: 139 requirement-mapped pytest cases passed, including every bundled Japanese glyph, real Matplotlib PDF, rotations, clipping, invalid profiles/commands, corrupted checksums, multipage conversion and in-memory HTTP uploads/exports. UI JavaScript interaction checks, lint and shell syntax passed. Distribution wheel successfully built and installed; installed CLI converted the Japanese sample from /private/tmp and rejected an uncalibrated export.

Limits: actual macOS browser/socket runtime is not verified in this restricted execution environment; binding localhost returns Operation not permitted. Bambu Studio import and physical plotting are unverified. Device-specific XY/Z values require owner measurement. These limitations are documented and are not represented as software or hardware certification.
