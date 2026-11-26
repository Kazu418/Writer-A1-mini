"""Reproduce bundled stroke datasets from pinned upstream data; never executes downloaded code."""

import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import re
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

KVG_COMMIT = "9d7220dfca09107dca2e0b0e45f90f696185e3c3"
HERSHEY_BLOB = "1aa06c45ebf5d620b7709f26cf538a54bc5add45"


def download(url):
    request = urllib.request.Request(
        url, headers={"User-Agent": "PlotNote-font-data-reproducer"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        data = response.read(100_000_001)
    if len(data) > 100_000_000:
        raise ValueError("Font archive exceeds 100 MB")
    return data


def git_hash(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--output",
        type=Path,
        required=True,
        help="New directory, never overwrite installed fonts",
    )
    args = p.parse_args()
    if args.output.exists():
        p.error("Output already exists")
    source = Path(__file__).resolve().parents[1] / "src/plotnote/data"
    manifest = json.loads((source / "kanjivg-manifest.json").read_text())
    archive = download(f"https://codeload.github.com/KanjiVG/kanjivg/zip/{KVG_COMMIT}")
    glyphs = {}
    license_text = None
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        for member in z.infolist():
            if member.file_size > 1_000_000:
                continue
            name = Path(member.filename).name
            if member.filename.endswith("/COPYING"):
                license_text = z.read(member).decode()
            if "/kanji/" not in member.filename or not re.fullmatch(
                "[0-9a-f]{5}\\.svg", name
            ):
                continue
            data = z.read(member)
            if name not in manifest or git_hash(data) != manifest[name]:
                raise ValueError(f"Upstream glyph hash mismatch: {name}")
            root = ET.fromstring(data)
            glyphs[chr(int(name[:5], 16))] = [
                el.attrib["d"]
                for el in root.iter()
                if el.tag.rsplit("}", 1)[-1] == "path"
            ]
    if len(glyphs) != len(manifest) or not license_text:
        raise ValueError("Incomplete KanjiVG archive")
    blob = json.loads(
        download(
            f"https://api.github.com/repos/techninja/hersheytextjs/git/blobs/{HERSHEY_BLOB}"
        )
    )
    raw = base64.b64decode(blob["content"])
    if git_hash(raw) != HERSHEY_BLOB:
        raise ValueError("Hershey data hash mismatch")
    args.output.mkdir(parents=True)
    (args.output / "kanjivg.json").write_text(json.dumps(glyphs, ensure_ascii=False))
    (args.output / "hershey.json").write_text(
        json.dumps(json.loads(raw), ensure_ascii=False)
    )
    (args.output / "KANJIVG-LICENSE.txt").write_text(license_text)
    (args.output / "HERSHEY-LICENSE.txt").write_bytes(
        (source / "HERSHEY-LICENSE.txt").read_bytes()
    )
    print(
        f"Reproduced {len(glyphs)} Japanese glyphs with verified upstream Git blob hashes in {args.output}"
    )


if __name__ == "__main__":
    main()
