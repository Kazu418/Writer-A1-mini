import argparse
from dataclasses import asdict
import json
from pathlib import Path
from contextlib import nullcontext
import sys
from . import __version__
from .artifacts import write_artifacts
from .fonts import glyph_paths, datasets, SYMBOLS, GREEK, SUPERSCRIPT, SUBSCRIPT, use_personal_font
from .gcode import generate, effective_profile
from .model import PlotNoteError, Page, Stroke
from .package import build_package, read_package
from .pdf_input import load_pdf
from .profile import Profile
from .svg_input import parse_svg
from .validate import validate_gcode


def load_input(path):
    path = Path(path)
    if path.suffix.lower() == ".pdf":
        return load_pdf(path)
    if path.suffix.lower() == ".svg":
        p = parse_svg(path)
        p.validate()
        return [p]
    raise PlotNoteError("Input must be .pdf or .svg")


def export_pages(pages, profile, out, *, homed=False, air_mm=0):
    # Build and validate everything before creating any output.
    payload = []
    for page in pages:
        code, p, report = generate(page, profile, homed=homed, air_mm=air_mm)
        payload.append((code, build_package(code, page, p), report))
    out = Path(out)
    if out.exists():
        raise PlotNoteError(f"Output already exists: {out}")
    out.mkdir(parents=True)
    for i, (code, package, report) in enumerate(payload, 1):
        (out / f"page-{i:03d}.gcode").write_text(code)
        (out / f"page-{i:03d}.gcode.3mf").write_bytes(package)
    p = effective_profile(profile, air_mm)
    p.save(out / "effective-profile.json")
    (out / "validation.json").write_text(
        json.dumps(
            {"air_run_mm": air_mm, "pages": [r for _, _, r in payload]}, indent=2
        )
        + "\n"
    )
    return out


def calibration_page(profile):
    profile.validate(require_calibrated=False)
    x0, y0, x1, y1 = profile.reachable_page_rect()
    pad = 5
    x0 += pad
    y0 += pad
    x1 -= pad
    y1 -= pad
    if x1 - x0 < 25 or y1 - y0 < 25:
        raise PlotNoteError("Reachable area is too small for a calibration target")
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    strokes = [
        Stroke([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]),
        Stroke(
            [
                (cx - 10, cy - 10),
                (cx + 10, cy - 10),
                (cx + 10, cy + 10),
                (cx - 10, cy + 10),
                (cx - 10, cy - 10),
            ]
        ),
        Stroke([(cx - 3, cy), (cx + 3, cy)]),
        Stroke([(cx, cy - 3), (cx, cy + 3)]),
    ]
    return Page(profile.paper_width, profile.paper_height, strokes)


def parser():
    p = argparse.ArgumentParser(
        prog="plotnote",
        description="PDF/SVGから日本語の筆順を保持したA1 mini用ペン軌跡を作成",
    )
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="command", required=True)
    for name in ("inspect", "convert", "export"):
        s = sub.add_parser(name)
        s.add_argument("input", type=Path)
        s.add_argument('--personal-font', type=Path, help='確認済み本人筆跡の字庫（PDF文字用、欠字はエラー）')
        if name != "inspect":
            s.add_argument(
                "-o", "--output", required=True, type=Path, help="新規出力ディレクトリ"
            )
        if name == "convert":
            s.add_argument("--pen-width", type=float, default=0.3)
        if name == "export":
            s.add_argument("--profile", required=True, type=Path)
            s.add_argument(
                "--homed",
                action="store_true",
                help="ペンなしで事前にホーム位置を確定する運用を確認",
            )
            s.add_argument(
                "--air-mm", type=float, default=0, help="空描き時の追加Z高さ (0..10 mm)"
            )
    s = sub.add_parser("profile")
    q = s.add_subparsers(dest="action", required=True)
    a = q.add_parser("init")
    a.add_argument("-o", "--output", type=Path, required=True)
    a = q.add_parser("show")
    a.add_argument("input", type=Path)
    s = sub.add_parser("calibration")
    s.add_argument("--profile", type=Path, required=True)
    s.add_argument("-o", "--output", type=Path, required=True)
    s = sub.add_parser("validate")
    s.add_argument("input", type=Path)
    s.add_argument("--profile", required=True, type=Path)
    s = sub.add_parser("fonts")
    s.add_argument("--check", help="対応を確認する文字列")
    s.add_argument("--list", action="store_true", help="対応文字一覧をJSON出力")
    sub.add_parser("doctor")
    s = sub.add_parser("serve")
    s.add_argument("--port", type=int, default=8765)
    s.add_argument("--workspace", type=Path, default=Path("jobs"))
    return p


def run(args):
    if args.command in ("inspect", "convert", "export"):
        font_path = getattr(args, 'personal_font', None)
        context = use_personal_font(json.loads(font_path.read_text())) if font_path else nullcontext()
        with context:
            pages = load_input(args.input)
        if args.command == "inspect":
            return {"valid": True, "pages": [p.summary() for p in pages]}
        if args.command == "convert":
            if not 0.05 <= args.pen_width <= 2:
                raise PlotNoteError("Pen width must be 0.05..2 mm")
            return {
                "output": str(write_artifacts(pages, args.output, args.pen_width)),
                "pages": len(pages),
            }
        return {
            "output": str(
                export_pages(
                    pages,
                    Profile.load(args.profile),
                    args.output,
                    homed=args.homed,
                    air_mm=args.air_mm,
                )
            ),
            "pages": len(pages),
        }
    if args.command == "profile":
        if args.action == "init":
            if args.output.exists():
                raise PlotNoteError("Profile already exists; refusing overwrite")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            Profile().save(args.output)
            return {
                "profile": str(args.output),
                "calibrated": False,
                "next": "Read docs/CALIBRATION.md; enter measured values.",
            }
        p = Profile.load(args.input)
        return {"profile": asdict(p), "reachable_page_rect_mm": p.reachable_page_rect()}
    if args.command == "calibration":
        p = Profile.load(args.profile)
        return {
            "output": str(
                write_artifacts([calibration_page(p)], args.output, p.pen_width)
            )
        }
    if args.command == "validate":
        code = (
            read_package(args.input)
            if args.input.name.endswith(".3mf")
            else args.input.read_text()
        )
        return validate_gcode(code, Profile.load(args.profile))
    if args.command == "fonts":
        if args.check is not None:
            errors = []
            for c in dict.fromkeys(args.check):
                try:
                    glyph_paths(c)
                except PlotNoteError as e:
                    errors.append(str(e))
            if errors:
                raise PlotNoteError("\n".join(errors))
            return {"supported": True, "characters": len(args.check)}
        kvg, _ = datasets()
        chars = (
            set(kvg)
            | set(SYMBOLS)
            | set(GREEK)
            | set(SUPERSCRIPT)
            | set(SUBSCRIPT)
            | set(chr(i) for i in range(32, 127))
        )
        return {
            "count": len(chars),
            "characters": "".join(sorted(chars))
            if args.list
            else "Use --list or --check TEXT",
        }
    if args.command == "doctor":
        import pymupdf, fontTools

        kvg, h = datasets()
        return {
            "plotnote": __version__,
            "python": sys.version.split()[0],
            "pymupdf": pymupdf.VersionBind,
            "fonttools": fontTools.__version__,
            "japanese_glyphs": len(kvg),
            "hershey_fonts": len(h),
            "offline_ready": True,
        }
    if args.command == "serve":
        from .server import serve

        serve(args.port, args.workspace)


def main(argv=None):
    try:
        result = run(parser().parse_args(argv))
        if result is not None:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (PlotNoteError, OSError, ValueError) as e:
        print(f"plotnote: {e}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
