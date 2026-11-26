"""Bambu G-code package (OPC/3MF container), not a slicable mesh project."""

import hashlib
import io
import zipfile
import xml.etree.ElementTree as ET
from .validate import validate_gcode
from .artifacts import png_bytes
from .model import PlotNoteError


def build_package(gcode, page, profile):
    validate_gcode(gcode, profile, page)
    summary = page.summary()
    seconds = max(
        1,
        round(
            summary["ink_mm"] / profile.draw_feed * 60
            + summary["travel_mm"] / profile.travel_feed * 60
            + summary["strokes"]
            * 2
            * (profile.lift_z - profile.draw_z)
            / profile.z_feed
            * 60
        ),
    )
    return _package_bytes(gcode, page, profile.pen_width, seconds)


def _package_bytes(gcode, page, pen_width, seconds):
    """Internal OPC writer. Callers must validate their motion dialect first."""
    root = ET.Element(
        "Types", xmlns="http://schemas.openxmlformats.org/package/2006/content-types"
    )
    for ext, ct in {
        "rels": "application/vnd.openxmlformats-package.relationships+xml",
        "model": "application/vnd.ms-package.3dmanufacturing-3dmodel+xml",
        "png": "image/png",
        "gcode": "text/x.gcode",
        "config": "text/xml",
        "md5": "text/plain",
    }.items():
        ET.SubElement(root, "Default", Extension=ext, ContentType=ct)
    rel = ET.Element(
        "Relationships",
        xmlns="http://schemas.openxmlformats.org/package/2006/relationships",
    )
    ET.SubElement(
        rel,
        "Relationship",
        Id="model",
        Target="/3D/3dmodel.model",
        Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel",
    )
    ET.SubElement(
        rel,
        "Relationship",
        Id="preview",
        Target="/Metadata/plate_1.png",
        Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/thumbnail",
    )
    model = ET.Element(
        "model",
        unit="millimeter",
        xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02",
        attrib={"xmlns:BambuStudio": "http://schemas.bambulab.com/package/2021"},
    )
    ET.SubElement(model, "metadata", name="Application").text = "PlotNote 0.1.0"
    ET.SubElement(model, "metadata", name="BambuStudio:3mfVersion").text = "1"
    ET.SubElement(model, "resources")
    ET.SubElement(model, "build")
    config = ET.Element("config")
    header = ET.SubElement(config, "header")
    ET.SubElement(header, "header_item", key="X-BBL-Client-Type", value="slicer")
    ET.SubElement(
        header, "header_item", key="X-BBL-Client-Version", value="02.00.00.00"
    )
    plate = ET.SubElement(config, "plate")
    for k, v in {
        "index": "1",
        "printer_model_id": "N1",
        "nozzle_diameters": "0.4",
        "gcode_file": "Metadata/plate_1.gcode",
        "thumbnail_file": "Metadata/plate_1.png",
        "prediction": str(seconds),
        "weight": "0",
    }.items():
        ET.SubElement(plate, "metadata", key=k, value=v)
    data = gcode.encode()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        for path, xml in {
            "[Content_Types].xml": root,
            "_rels/.rels": rel,
            "3D/3dmodel.model": model,
            "Metadata/slice_info.config": config,
        }.items():
            z.writestr(path, ET.tostring(xml, encoding="utf-8", xml_declaration=True))
        z.writestr("Metadata/plate_1.gcode", data)
        z.writestr(
            "Metadata/plate_1.gcode.md5", hashlib.md5(data).hexdigest().upper() + "\n"
        )
        z.writestr("Metadata/plate_1.png", png_bytes(page, pen_width))
    return buffer.getvalue()


def read_package(path):
    try:
        with zipfile.ZipFile(path) as z:
            entries = z.infolist()
            if any(e.file_size > 100_000_000 for e in entries):
                raise PlotNoteError("Oversized package member")
            data = z.read("Metadata/plate_1.gcode")
            expected = z.read("Metadata/plate_1.gcode.md5").decode().strip().lower()
            if hashlib.md5(data).hexdigest() != expected:
                raise PlotNoteError("Package G-code checksum mismatch")
            return data.decode("utf-8")
    except (OSError, KeyError, ValueError, zipfile.BadZipFile, UnicodeError) as e:
        raise PlotNoteError(f"Invalid Bambu package: {e}") from e
