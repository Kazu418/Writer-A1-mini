# Sources and third-party notices

## Stroke data

- **KanjiVG** — Ulrich Apel and contributors, copyright 2009–2026. https://github.com/KanjiVG/kanjivg / https://kanjivg.tagaini.net/
  - License: Creative Commons Attribution-ShareAlike 3.0. Full text: `src/plotnote/data/KANJIVG-LICENSE.txt`.
  - Source `kanji/` Git tree: `9457d21a0e90f0071ac73191f45aa5d9bcacc456` (retrieved 2026-11-24).
  - Bundled transformation: 6,984 standard five-hex-digit SVG filenames, retaining all `<path d>` values in document order. Alternate filename variants and stroke-number labels excluded. Paths normalized from 109-unit cells by the renderer. The derived glyph data remains CC BY-SA 3.0.
  - Stroke SVG/PDF outputs include an attribution notice. Preserve the license/attribution when distributing derived glyph/path data. This is a software notice, not a determination of the legal status of every physical page.
- **HersheyTextJS** — https://github.com/techninja/hersheytextjs, MIT license. Full text: `src/plotnote/data/HERSHEY-LICENSE.txt`.
  - Bundled `hersheytext.min.json` source blob: `1aa06c45ebf5d620b7709f26cf538a54bc5add45`.
  - Roman and Greek centerlines used with baseline/advance normalization.
- Math operators, Japanese punctuation and Unicode super/subscript placement in `fonts.py` are explicitly authored centerlines/transformations for this application.

## Runtime dependencies

- **PyMuPDF** (Artifex / contributors): https://pymupdf.readthedocs.io/ — AGPL or commercial licensing. Used for PDF extraction, PDF/PNG previews and Unicode text tracing.
- **fontTools**: https://github.com/fonttools/fonttools — MIT. SVG path parser and pen primitives.
- Python standard library for HTTP, JSON, ZIP, XML and CLI. `pytest` is a development dependency.

The PlotNote application code is licensed under AGPL-3.0-or-later. Third-party data retains its own license.

## Hardware and workflow references

- TeQiller, **A1 Plotter Module**: https://makerworld.com/ja/models/2433877-a1-plotter-module — model description supplied by the user. Hardware supports A1/A1 mini; its supplied start G-code explicitly targets A1 and is not incorporated.
- Bambu Lab **A1 mini technical specifications**: https://store.bblcdn.com/1531c9726f6b41fba4594d5b47966ee0.pdf — nominal 180×180×180mm envelope.
- **A1 Mini Pen Plotter**: https://github.com/Hansolox80/a1-mini-pen-plotter — reviewed documented calibration, path-order settings and Bambu G-code package layout. No start routine or machine-specific calibration copied.
- **BambuPlotter**: https://github.com/danieloquelis/BambuPlotter — reviewed same-holder calibration and manual-home-before-mounting workflow.
- **Handwriting Helper**: https://github.com/Aptimex/handwriting-helper — reviewed text-to-stroke/G-code architecture; no AI handwriting model or code incorporated.

These references do not certify this application's hardware compatibility. Generated paths and containers are tested locally; physical execution remains unverified.
