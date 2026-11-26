"""Local-only workbench. No printer/network dispatch endpoints exist."""

from dataclasses import asdict
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import mimetypes
from pathlib import Path
import re
import secrets
from urllib.parse import urlparse, parse_qs, unquote
import uuid
import zipfile
from .artifacts import write_artifacts
from .cli import load_input, export_pages
from .model import PlotNoteError
from .profile import Profile


def bundle(directory):
    target = directory / "download.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(directory.iterdir()):
            if p.is_file() and p != target:
                z.write(p, p.name)


def handler_factory(workspace, token):
    workspace = Path(workspace).resolve()
    workspace.mkdir(parents=True, exist_ok=True)

    class Handler(BaseHTTPRequestHandler):
        def reply(self, status, body, content_type="application/json; charset=utf-8"):
            if not isinstance(body, bytes):
                body = json.dumps(body, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def host_valid(self):
            return self.headers.get("Host") == f"127.0.0.1:{self.server.server_port}"

        def do_GET(self):
            if not self.host_valid():
                self.reply(403, {"error": "Invalid local Host"})
                return
            path = unquote(urlparse(self.path).path)
            if path == "/":
                html = (
                    Path(__file__)
                    .with_name("data")
                    .joinpath("workbench.html")
                    .read_text()
                    .replace("__TOKEN__", token)
                )
                self.reply(200, html.encode(), "text/html; charset=utf-8")
                return
            if path == "/api/profile":
                self.reply(200, asdict(Profile()))
                return
            if path.startswith("/jobs/"):
                parts = path[6:].split("/")
                if (
                    len(parts) < 3
                    or not re.fullmatch("[a-f0-9]{32}", parts[0])
                    or not (
                        parts[1] == "preview"
                        or re.fullmatch("export-[a-f0-9]{12}", parts[1])
                    )
                ):
                    self.reply(404, {"error": "File not found"})
                    return
                f = (workspace / path[6:]).resolve()
                if workspace not in f.parents or not f.is_file():
                    self.reply(404, {"error": "File not found"})
                    return
                self.reply(
                    200,
                    f.read_bytes(),
                    mimetypes.guess_type(f.name)[0] or "application/octet-stream",
                )
                return
            self.reply(404, {"error": "Not found"})

        def do_POST(self):
            origin = self.headers.get("Origin")
            if (
                not self.host_valid()
                or self.headers.get("X-PlotNote-Token") != token
                or origin not in (None, f"http://127.0.0.1:{self.server.server_port}")
            ):
                self.reply(403, {"error": "Local origin/token required"})
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 30_000_000:
                    raise PlotNoteError("Input size must be 1 byte..30 MB")
                data = self.rfile.read(size)
                route = urlparse(self.path)
                if route.path == "/api/convert":
                    name = parse_qs(route.query).get("name", ["note.pdf"])[0]
                    suffix = Path(name).suffix.lower()
                    if suffix not in (".pdf", ".svg"):
                        raise PlotNoteError("Choose PDF or SVG")
                    job = uuid.uuid4().hex
                    folder = workspace / job
                    folder.mkdir()
                    source = folder / f"source{suffix}"
                    source.write_bytes(data)
                    pages = load_input(source)
                    out = write_artifacts(pages, folder / "preview")
                    bundle(out)
                    self.reply(
                        200,
                        {
                            "job": job,
                            "preview": f"/jobs/{job}/preview/preview.html",
                            "pdf": f"/jobs/{job}/preview/preview.pdf",
                            "download": f"/jobs/{job}/preview/download.zip",
                            "pages": [p.summary() for p in pages],
                        },
                    )
                    return
                if route.path == "/api/export":
                    request = json.loads(data)
                    job = request.get("job", "")
                    if not re.fullmatch("[a-f0-9]{32}", job):
                        raise PlotNoteError("Invalid job ID")
                    folder = workspace / job
                    inputs = list(folder.glob("source.*"))
                    if len(inputs) != 1:
                        raise PlotNoteError(
                            "Source job not found; convert a document first"
                        )
                    profile = Profile(**request["profile"])
                    profile.validate()
                    if type(request.get("homed")) is not bool:
                        raise PlotNoteError("homed must be boolean")
                    run = uuid.uuid4().hex[:12]
                    out = folder / f"export-{run}"
                    export_pages(
                        load_input(inputs[0]),
                        profile,
                        out,
                        homed=request["homed"],
                        air_mm=float(request.get("air_mm", 0)),
                    )
                    bundle(out)
                    self.reply(
                        200, {"download": f"/jobs/{job}/export-{run}/download.zip"}
                    )
                    return
                self.reply(404, {"error": "Not found"})
            except (PlotNoteError, ValueError, TypeError, KeyError, OSError) as e:
                self.reply(400, {"error": str(e)})

        def log_message(self, fmt, *args):
            # Do not log source filenames or request bodies.
            pass

    return Handler


def serve(port, workspace):
    if not 1024 <= port <= 65535:
        raise PlotNoteError("Port must be 1024..65535")
    token = secrets.token_urlsafe(32)
    # PyMuPDF is not thread safe: conversions run serially on this one local server.
    with HTTPServer(("127.0.0.1", port), handler_factory(workspace, token)) as server:
        print(f"PlotNote: http://127.0.0.1:{port}  (Ctrl+C to stop)", flush=True)
        server.serve_forever()
