"""Offline, fixed-machine preview/approval/delivery workflow.

This module compiles geometry only. It never connects to a printer or asserts
that a real machine is currently homed. Physical readiness belongs to the owner.
"""
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import zipfile
import xml.etree.ElementTree as ET

import pymupdf as fitz

from .gcode import generate
from .model import PlotNoteError
from .package import build_package, read_package
from .profile import Profile
from .svg_input import parse_svg
from .validate import validate_gcode

CONTRACT_ID = "writer-a1-mini-owner-v1"
BASE_PROFILE = dict(
    printer="a1-mini", calibrated=True, pen_offset_x=0, pen_offset_y=-30.8,
    paper_x=7.5, paper_width=165.0, paper_height=127.5,
    nozzle_min_x=5.0, nozzle_max_x=175.0, nozzle_min_y=5.0, nozzle_max_y=175.0,
    draw_z=4.8, lift_z=6.5, safe_z=10.0,
    draw_feed=1800.0, travel_feed=2400.0, z_feed=600.0, pen_width=0.3,
)
CONTRACT = {
    "id": CONTRACT_ID, "bed_mm": [180, 180], "paper_mm": [210, 297],
    "tile_mm": [165, 127.5], "a4_window_x_mm": 22.5,
    "a4_window_y_mm": [36.5, 164.5], "paper_y_by_pass_mm": [16.0, 5.0],
    "mount_reference_z_mm": 5.0, "base_profile": BASE_PROFILE,
    "registration_marks": False, "tile_frames": False,
    "runtime_owner_only": True, "runtime_home_flag_xyz_mask": 7,
    "evidence": {
        "historical_calibration_nozzle_y_mm": [40, 150],
        "full_declared_5_to_175_range_physically_verified": False,
        "note": "Owner observed successful note printing with this setup. Bounds are a generation envelope, not proof that every position or other pen/paper is safe. Owner rechecks mounting/contact and homing. Firmware startup may heat to75C; pause may set90C. Cancel can lose homing.",
    },
}


def _json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise PlotNoteError(f"Invalid JSON {path}: {e}") from e


def _write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def owner_profile(pass_no):
    if type(pass_no) is not int or pass_no not in (1, 2):
        raise PlotNoteError("Pass must be 1 or 2")
    return Profile(**BASE_PROFILE, paper_y=CONTRACT["paper_y_by_pass_mm"][pass_no - 1],
        calibration_notes="Fixed owner machine contract. Offline export does not verify physical homing. Mount at Z5; pen removed before homing; owner-only execution; full envelope not physically verified.").validate()


def _request(data):
    if not isinstance(data, dict):
        raise PlotNoteError("Request must be an object")
    required = {"job_id", "max_sheets", "duplex", "font_size_mm", "formula_policy", "faces"}
    if set(data) != required:
        raise PlotNoteError(f"Request fields must be exactly {sorted(required)}")
    if not isinstance(data["job_id"], str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", data["job_id"]):
        raise PlotNoteError("job_id must be a short ASCII filename-safe identifier")
    if type(data["max_sheets"]) is not int or not 1 <= data["max_sheets"] <= 100:
        raise PlotNoteError("max_sheets must be an integer in1..100")
    if type(data["duplex"]) is not bool:
        raise PlotNoteError("duplex must be a boolean")
    size = data["font_size_mm"]
    if type(size) not in (int, float) or not math.isfinite(size) or not 1 <= size <= 20:
        raise PlotNoteError("font_size_mm must be a finite intended size in1..20; the AI must apply it to the supplied geometry")
    if data["formula_policy"] not in ("keep", "blank_display_formulas"):
        raise PlotNoteError("formula_policy must be keep or blank_display_formulas")
    faces = data["faces"]
    if not isinstance(faces, list) or not faces:
        raise PlotNoteError("At least one complete face (two passes) is required")
    seen = set()
    for face in faces:
        if not isinstance(face, dict) or set(face) != {"sheet", "side", "pass1", "pass2"}:
            raise PlotNoteError("Each face needs exactly sheet, side, pass1, pass2")
        sheet = face["sheet"]
        if type(sheet) is not int or not 1 <= sheet <= data["max_sheets"]:
            raise PlotNoteError("Face exceeds max_sheets paper budget")
        if face["side"] not in (("front", "back") if data["duplex"] else ("front",)):
            raise PlotNoteError("Face side is incompatible with duplex setting")
        key = (sheet, face["side"])
        if key in seen:
            raise PlotNoteError("Duplicate sheet/side")
        seen.add(key)
        for key in ("pass1", "pass2"):
            if not isinstance(face[key], str) or not face[key]:
                raise PlotNoteError("Each pass must name an SVG file")
    sheets = sorted({n for n, _ in seen})
    if sheets != list(range(1, max(sheets) + 1)) or any((n, "front") not in seen for n in sheets):
        raise PlotNoteError("Sheets must be contiguous from1 and each needs a front face")
    ordered = sorted(faces, key=lambda f: (f["sheet"], f["side"] == "back"))
    if faces != ordered:
        raise PlotNoteError("Faces must be ordered by sheet, front then back")
    return data


def _load_tile(path, pass_no):
    source = Path(path).read_text(encoding="utf-8")
    try:
        tree = ET.fromstring(source)
    except ET.ParseError as e:
        raise PlotNoteError(f"Invalid SVG: {e}") from e
    for node in tree.iter():
        if node.tag.rsplit("}", 1)[-1] in ("clipPath", "mask") or any(k.rsplit("}", 1)[-1] in ("clip-path", "mask") for k in node.attrib):
            raise PlotNoteError("Handoff SVG must contain complete, unclipped geometry")
        if "clip-path" in node.get("style", "") or "mask:" in node.get("style", ""):
            raise PlotNoteError("Handoff SVG clipping/masking is not permitted")
    page = parse_svg(source)
    owner_profile(pass_no).check_page(page)
    return page


def _paths_from_code(code, profile):
    paths = []
    points = None
    for line in code.splitlines():
        if line.startswith("; stroke "):
            if points is not None:
                paths.append(points)
            points = []
        elif line.startswith("G1 X") and points is not None:
            args = {p[0]: float(p[1:]) for p in line.split()[1:]}
            points.append((args["X"] - profile.paper_x + profile.pen_offset_x,
                profile.paper_y + profile.paper_height - args["Y"] - profile.pen_offset_y))
    if points is not None:
        paths.append(points)
    if any(len(points) < 2 for points in paths) or not paths:
        raise PlotNoteError("No complete plotted strokes")
    return paths


def _face_content(directory, passes, face_no):
    pt = 72 / 25.4
    content = ["q", f"{pt:.12f} 0 0 {-pt:.12f} 0 {297 * pt:.12f} cm", "0 0 0 RG", "0.3 w", "1 J", "1 j"]
    for item in (p for p in passes if p["face"] == face_no):
        profile = owner_profile(item["pass"])
        for points in _paths_from_code((directory / item["gcode"]).read_text(), profile):
            xy = [(x + 22.5, y + CONTRACT["a4_window_y_mm"][item["pass"] - 1]) for x, y in points]
            content.append(f"{xy[0][0]:.6f} {xy[0][1]:.6f} m")
            content.extend(f"{x:.6f} {y:.6f} l" for x, y in xy[1:])
            content.append("S")
    content.append("Q")
    return ("\n".join(content) + "\n").encode()


def _preview(directory, passes):
    """Vector A4 preview from rounded G-code coordinates, not source-font rerendering."""
    pt = 72 / 25.4
    doc = fitz.open()
    for face_no in sorted({p["face"] for p in passes}):
        page = doc.new_page(width=210 * pt, height=297 * pt)
        xref = doc.get_new_xref()
        doc.update_object(xref, "<<>>")
        doc.update_stream(xref, _face_content(directory, passes, face_no))
        page.set_contents(xref)
    doc.set_metadata({"title": "Writer A1 mini - actual G-code preview", "subject": "One A4 page per face; two manual placements per face; source geometry is not scaled"})
    doc.save(directory / "preview.pdf", garbage=4, deflate=True)
    doc.close()


def _verify_preview(directory, passes):
    try:
        with fitz.open(directory / "preview.pdf") as doc:
            faces = sorted({p["face"] for p in passes})
            if len(doc) != len(faces):
                raise PlotNoteError("Preview face count differs from G-code")
            for page, face_no in zip(doc, faces):
                if page.rotation != 0 or abs(page.rect.width - 210 * 72 / 25.4) > .01 or abs(page.rect.height - 297 * 72 / 25.4) > .01 or page.first_annot is not None or page.read_contents() != _face_content(directory, passes, face_no):
                    raise PlotNoteError("Preview geometry differs from actual G-code")
    except (RuntimeError, ValueError) as e:
        raise PlotNoteError(f"Invalid preview PDF: {e}") from e


def prepare(request_path, output):
    request_path, output = Path(request_path), Path(output)
    request = _request(_json(request_path))
    prepared = []
    for number, face in enumerate(request["faces"], 1):
        for part in (1, 2):
            path = request_path.parent / face[f"pass{part}"]
            prepared.append((number, face, part, path, _load_tile(path, part)))
    if output.exists():
        raise PlotNoteError("Output already exists; use a new revision directory")
    output.mkdir(parents=True)
    (output / "inputs").mkdir()
    (output / "gcode").mkdir()
    copied_request = {**request, "faces": [dict(f) for f in request["faces"]]}
    passes = []
    for number, face, part, path, page in prepared:
        stem = f"face-{number:03d}-pass-{part}"
        svg_name = f"inputs/{stem}.svg"
        shutil.copyfile(path, output / svg_name)
        copied_request["faces"][number - 1][f"pass{part}"] = svg_name
        profile = owner_profile(part)
        # homed=True acknowledges the required owner workflow in the generated
        # header only. No physical readiness is inferred by this offline exporter.
        code, _, validation = generate(page, profile, homed=True)
        gcode_name = f"gcode/{stem}.gcode"
        (output / gcode_name).write_text(code, encoding="utf-8")
        package_name = gcode_name + ".3mf"
        (output / package_name).write_bytes(build_package(code, page, profile))
        profile_name = f"gcode/{stem}-profile.json"
        profile.save(output / profile_name)
        first = _paths_from_code(code, profile)[0][0]
        first_xy = profile.machine_point(*first)
        passes.append({"face": number, "sheet": face["sheet"], "side": face["side"], "pass": part,
            "source": svg_name, "gcode": gcode_name, "package": package_name, "profile": profile_name,
            "placement": "A4 top edge at plate back edge; center X" if part == 1 else "A4 bottom edge at plate front edge; center X",
            "first_nozzle_xy_mm": list(first_xy), "mount_reference_z_mm": 5,
            "validation": validation})
    _write_json(output / "request.json", copied_request)
    _write_json(output / "machine-contract.json", CONTRACT)
    _preview(output, passes)
    files = {p.relative_to(output).as_posix(): _sha(p) for p in sorted(output.rglob("*")) if p.is_file()}
    manifest = {"format": "writer-a1-mini-handoff-v1", "job_id": request["job_id"], "machine_contract_id": CONTRACT_ID,
        "request": copied_request, "passes": passes, "files": files, "preview_sha256": files["preview.pdf"],
        "approval_state": "draft", "owner_must_check_physical_readiness": True}
    _write_json(output / "manifest.json", manifest)
    verify(output)
    return manifest


def verify(directory):
    directory = Path(directory)
    manifest = _json(directory / "manifest.json")
    if manifest.get("format") != "writer-a1-mini-handoff-v1" or manifest.get("machine_contract_id") != CONTRACT_ID:
        raise PlotNoteError("Wrong handoff format/machine contract")
    request = _request(manifest.get("request"))
    files = manifest.get("files")
    if not isinstance(files, dict) or "preview.pdf" not in files:
        raise PlotNoteError("Missing artifact hashes")
    expected = {"request.json", "machine-contract.json", "preview.pdf"}
    expected_passes = len(request["faces"]) * 2
    passes = manifest.get("passes", [])
    if len(passes) != expected_passes:
        raise PlotNoteError("Manifest must have exactly two passes per face")
    for number, item in enumerate(passes):
        face_no, part = number // 2 + 1, number % 2 + 1
        stem = f"face-{face_no:03d}-pass-{part}"
        required_names = {"source": f"inputs/{stem}.svg", "gcode": f"gcode/{stem}.gcode", "package": f"gcode/{stem}.gcode.3mf", "profile": f"gcode/{stem}-profile.json"}
        if item.get("face") != face_no or item.get("pass") != part or any(item.get(k) != v for k, v in required_names.items()):
            raise PlotNoteError("Pass order/paths differ from fixed contract")
        if request["faces"][face_no - 1][f"pass{part}"] != required_names["source"]:
            raise PlotNoteError("Request source differs from pass source")
        face = request["faces"][face_no - 1]
        placement = "A4 top edge at plate back edge; center X" if part == 1 else "A4 bottom edge at plate front edge; center X"
        if item.get("sheet") != face["sheet"] or item.get("side") != face["side"] or item.get("placement") != placement or item.get("mount_reference_z_mm") != 5:
            raise PlotNoteError("Pass placement differs from fixed contract/request")
        expected.update(required_names.values())
    if set(files) != expected:
        raise PlotNoteError("Manifest has missing or unexpected files")
    actual = {p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file()}
    if actual - {"manifest.json", "approval.json"} != expected:
        raise PlotNoteError("Job contains missing or unmanifested files")
    for name, digest in files.items():
        path = directory / name
        if path.is_symlink() or _sha(path) != digest:
            raise PlotNoteError(f"Artifact changed: {name}")
    if manifest.get("preview_sha256") != files["preview.pdf"]:
        raise PlotNoteError("Preview hash mismatch")
    if _json(directory / "machine-contract.json") != CONTRACT or _json(directory / "request.json") != request:
        raise PlotNoteError("Fixed contract/request changed")
    for item in passes:
        part = item["pass"]
        profile = Profile.load(directory / item["profile"])
        if asdict(profile) != asdict(owner_profile(part)):
            raise PlotNoteError("Owner profile parameters changed")
        source = _load_tile(directory / item["source"], part)
        code = (directory / item["gcode"]).read_text()
        expected_code, _, _ = generate(source, profile, homed=True)
        if code != expected_code or read_package(directory / item["package"]) != code:
            raise PlotNoteError("Source/G-code/package geometry mismatch")
        validate_gcode(code, profile, source)
        first = _paths_from_code(code, profile)[0][0]
        if item.get("first_nozzle_xy_mm") != list(profile.machine_point(*first)):
            raise PlotNoteError("First-position metadata differs from G-code")
    _verify_preview(directory, passes)
    return manifest


def approve(directory, reviewer, preview_sha256):
    directory = Path(directory)
    manifest = verify(directory)
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise PlotNoteError("Reviewer name is required")
    if preview_sha256 != manifest["preview_sha256"]:
        raise PlotNoteError("The reviewed preview hash does not match this revision")
    path = directory / "approval.json"
    if path.exists():
        raise PlotNoteError("Revision is already approved; use a new revision to change it")
    approval = {"format": "writer-a1-mini-approval-v1", "reviewer": reviewer.strip(),
        "approved_at_utc": datetime.now(timezone.utc).isoformat(),
        "preview_sha256": preview_sha256, "manifest_sha256": _sha(directory / "manifest.json")}
    _write_json(path, approval)
    return approval


def bundle(directory, output):
    directory, output = Path(directory), Path(output)
    manifest = verify(directory)
    approval = _json(directory / "approval.json")
    if approval.get("format") != "writer-a1-mini-approval-v1" or not str(approval.get("reviewer", "")).strip() or approval.get("manifest_sha256") != _sha(directory / "manifest.json") or approval.get("preview_sha256") != manifest["preview_sha256"]:
        raise PlotNoteError("Approval does not match current artifacts; obtain new human review")
    if directory.resolve() in output.resolve().parents:
        raise PlotNoteError("Write delivery ZIP outside the revision directory")
    if output.exists():
        raise PlotNoteError("Bundle exists; output is never overwritten")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "x", zipfile.ZIP_DEFLATED) as archive:
        for name in sorted([*manifest["files"], "manifest.json", "approval.json"]):
            archive.write(directory / name, arcname=name)
    return {"bundle": str(output), "sha256": _sha(output), "job_id": manifest["job_id"]}
