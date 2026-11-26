import base64
import importlib.util
import io
import json
from pathlib import Path
import sys
import zipfile


def test_font_reproduction_from_verified_archive(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[1] / "scripts/fetch_fonts.py"
    spec = importlib.util.spec_from_file_location("font_reproducer", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    data = tmp_path / "src/plotnote/data"
    data.mkdir(parents=True)
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><path d="M10 10L20 20"/></svg>'
    (data / "kanjivg-manifest.json").write_text(
        json.dumps({"04e00.svg": m.git_hash(svg)})
    )
    (data / "HERSHEY-LICENSE.txt").write_text("fixture")
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as z:
        z.writestr("root/kanji/04e00.svg", svg)
        z.writestr("root/COPYING", "fixture")
    raw = b'{"futural":{"chars":[]}}'
    m.HERSHEY_BLOB = m.git_hash(raw)
    m.__file__ = str(tmp_path / "scripts/fetch_fonts.py")

    def download(url):
        return (
            stream.getvalue()
            if "codeload" in url
            else json.dumps({"content": base64.b64encode(raw).decode()}).encode()
        )

    monkeypatch.setattr(m, "download", download)
    monkeypatch.setattr(
        sys, "argv", ["fetch_fonts.py", "--output", str(tmp_path / "output")]
    )
    m.main()
    result = json.loads((tmp_path / "output/kanjivg.json").read_text())
    assert result == {"一": ["M10 10L20 20"]}
