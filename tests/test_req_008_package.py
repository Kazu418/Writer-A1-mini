import hashlib
import io
import zipfile
import xml.etree.ElementTree as ET
import pytest
from plotnote.gcode import generate
from plotnote.package import build_package, read_package
from plotnote.model import PlotNoteError


def test_package_content(page, profile, tmp_path):
    code, p, _ = generate(page, profile, homed=True)
    data = build_package(code, page, p)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        assert z.read("Metadata/plate_1.gcode").decode() == code
        assert (
            z.read("Metadata/plate_1.gcode.md5").decode().strip().lower()
            == hashlib.md5(code.encode()).hexdigest()
        )
        for name in [
            "[Content_Types].xml",
            "_rels/.rels",
            "3D/3dmodel.model",
            "Metadata/slice_info.config",
        ]:
            ET.fromstring(z.read(name))
        assert "N1" in z.read("Metadata/slice_info.config").decode()
    path = tmp_path / "plot.gcode.3mf"
    path.write_bytes(data)
    assert read_package(path) == code


def test_corrupt_package_checksum(page, profile, tmp_path):
    code, p, _ = generate(page, profile, homed=True)
    original = build_package(code, page, p)
    path = tmp_path / "bad.gcode.3mf"
    with (
        zipfile.ZipFile(io.BytesIO(original)) as source,
        zipfile.ZipFile(path, "w") as target,
    ):
        for name in source.namelist():
            target.writestr(
                name, b"0000" if name.endswith(".md5") else source.read(name)
            )
    with pytest.raises(PlotNoteError, match="checksum"):
        read_package(path)
