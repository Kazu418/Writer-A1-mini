"""Exercise the actual HTTP handler and conversion/export without opening a socket."""

from dataclasses import asdict
import io
import json
from types import SimpleNamespace
import pytest
from plotnote.server import handler_factory


def request(
    handler,
    method,
    path,
    body=b"",
    *,
    host="127.0.0.1:18765",
    token="test-token",
    origin=None,
):
    class Socket:
        def __init__(self, data):
            self.data = data
            self.out = bytearray()

        def makefile(self, *args, **kwargs):
            return io.BytesIO(self.data)

        def sendall(self, data):
            self.out.extend(data)

    headers = f"{method} {path} HTTP/1.0\r\nHost: {host}\r\nX-PlotNote-Token: {token}\r\nContent-Length: {len(body)}\r\n"
    if origin:
        headers += f"Origin: {origin}\r\n"
    socket = Socket(headers.encode() + b"\r\n" + body)
    handler(socket, ("127.0.0.1", 1234), SimpleNamespace(server_port=18765))
    head, payload = bytes(socket.out).split(b"\r\n\r\n", 1)
    status = int(head.split()[1])
    return status, payload


def test_full_http_flow(make_pdf, profile, tmp_path):
    h = handler_factory(tmp_path / "jobs", "test-token")
    status, payload = request(h, "GET", "/")
    assert status == 200 and b"__TOKEN__" not in payload
    assert request(h, "GET", "/api/profile")[0] == 200
    status, payload = request(
        h, "POST", "/api/convert?name=note.pdf", make_pdf().read_bytes()
    )
    assert status == 200, payload
    data = json.loads(payload)
    assert data["pages"][0]["strokes"] > 0
    assert request(h, "GET", data["preview"])[0] == 200
    assert request(h, "GET", data["download"])[1].startswith(b"PK")
    status, payload = request(
        h,
        "POST",
        "/api/export",
        json.dumps(
            {"job": data["job"], "profile": asdict(profile), "homed": True, "air_mm": 5}
        ).encode(),
    )
    assert status == 200, payload
    assert request(h, "GET", json.loads(payload)["download"])[1].startswith(b"PK")


@pytest.mark.parametrize(
    "changes",
    [{"host": "evil.test:18765"}, {"token": "wrong"}, {"origin": "https://evil.test"}],
)
def test_origin_boundaries(tmp_path, changes):
    h = handler_factory(tmp_path / "jobs", "test-token")
    assert request(h, "POST", "/api/export", b"{}", **changes)[0] == 403


def test_traversal_and_invalid_upload(tmp_path):
    h = handler_factory(tmp_path / "jobs", "test-token")
    assert request(h, "GET", "/jobs/../../secret")[0] == 404
    assert request(h, "POST", "/api/convert?name=a.txt", b"hello")[0] == 400
    assert request(h, "POST", "/api/export", b"{}")[0] == 400
