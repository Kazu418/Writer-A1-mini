# Checklist
- [x] REQ-C01: current contact, no origin reset/home/heat/extrusion.
### Implementation
contact_test.py
### Verification
pytest tests/test_contact_test.py
- [x] REQ-C02: measured XY compensation, small central sentence.
### Implementation
contact_test.py and generated preview.
### Verification
Source/command coordinate comparison and rendered preview.
- [x] REQ-C03: lift-before-travel, relative Z, absolute XY, final +5mm.
### Implementation
Independent contact-test validator.
### Verification
Mutation tests and both air/contact variants.
- [x] REQ-C04: G-code/3MF packaging and operator instructions.
### Implementation
package.py, output/contact-test/.
### Verification
ZIP checksum/content roundtrip, existing package regressions, visual preview and documented starting-state requirement.

Reconciled: 154 pytest cases passed (15 new contact-test cases), including original absolute exporter regressions. Preview visually inspected. Both packages matched validated commands/checksums. Installed wheel matched generated commands. Physical startup and plotting remain unverified.
