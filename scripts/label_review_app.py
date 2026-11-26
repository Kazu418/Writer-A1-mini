"""Phone-friendly hand review of handwriting labels, served on the local network.

Every decision is appended to a JSONL file and fsync'd BEFORE the server answers
"ok"; the phone only shows "saved" after that answer. Stdlib only; the font
database is never opened or modified here.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

VERDICTS = {'yes', 'no', 'unsure', 'fix', 'undo'}


class Store:
    """Append-only decision log. Last record per id wins; 'undo' clears it."""

    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.Lock()
        self.decisions = {}
        self.rids = set()
        self.lines = 0
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            raw = self.path.read_bytes()
            for line in raw.split(b'\n'):
                if not line.strip():
                    continue
                try:
                    self._apply(json.loads(line))
                except (ValueError, KeyError, TypeError):
                    continue  # a torn final line is skipped, never deleted
            # Guarantee the next record starts on a fresh line.
            if raw and not raw.endswith(b'\n'):
                with open(self.path, 'ab') as handle:
                    handle.write(b'\n')
                    self._sync(handle)

    def _apply(self, rec):
        if rec['v'] == 'undo':
            self.decisions.pop(rec['id'], None)
        else:
            self.decisions[rec['id']] = {'v': rec['v'], 'label': rec.get('label')}
        self.rids.add(rec['rid'])
        self.lines += 1

    @staticmethod
    def _sync(handle):
        handle.flush()
        os.fsync(handle.fileno())
        try:  # macOS: force the drive to commit, not just the OS cache
            import fcntl
            fcntl.fcntl(handle.fileno(), fcntl.F_FULLFSYNC)
        except (ImportError, OSError, AttributeError):
            pass

    def add(self, rec):
        with self.lock:
            if rec['rid'] in self.rids:  # a retry of something already saved
                return self.lines, True
            line = (json.dumps(rec, ensure_ascii=False, separators=(',', ':')) + '\n').encode()
            with open(self.path, 'ab') as handle:
                handle.write(line)
                self._sync(handle)
            self._apply(rec)
            return self.lines, False


def make_handler(queue, store, token, html):
    known = {item['id']: item for item in queue['items']}
    queue_json = json.dumps(queue, ensure_ascii=False, separators=(',', ':')).encode()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send(self, status, body, ctype='application/json; charset=utf-8'):
            if isinstance(body, (dict, list)):
                body = json.dumps(body, ensure_ascii=False).encode()
            elif isinstance(body, str):
                body = body.encode()
            self.send_response(status)
            self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)

        def authorised(self, url):
            given = parse_qs(url.query).get('k', [''])[0]
            return secrets.compare_digest(given, token)

        def do_GET(self):
            url = urlsplit(self.path)
            if not self.authorised(url):
                return self.send(403, {'error': 'forbidden'})
            if url.path == '/':
                return self.send(200, html, 'text/html; charset=utf-8')
            if url.path == '/api/queue':
                return self.send(200, queue_json)
            if url.path == '/api/state':
                with store.lock:
                    return self.send(200, {'decisions': dict(store.decisions),
                                           'lines': store.lines})
            self.send(404, {'error': 'not found'})

        def do_POST(self):
            url = urlsplit(self.path)
            if not self.authorised(url):
                return self.send(403, {'error': 'forbidden'})
            if url.path != '/api/review':
                return self.send(404, {'error': 'not found'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 2048:
                    raise ValueError('size')
                data = json.loads(self.rfile.read(length))
                rid, item_id, verdict = data['rid'], data['id'], data['v']
                if (not isinstance(rid, str) or not 8 <= len(rid) <= 64 or
                        item_id not in known or verdict not in VERDICTS):
                    raise ValueError('fields')
                label = data.get('label')
                if verdict == 'fix':
                    if (not isinstance(label, str) or len([*label]) != 1 or
                            label.isspace() or not label.isprintable()):
                        raise ValueError('label')
                else:
                    label = None
                rec = {'rid': rid, 'id': item_id, 'v': verdict, 'label': label,
                       'proposed': known[item_id]['label'],
                       'goodnotes': known[item_id]['goodnotes'],
                       'kind': known[item_id]['kind'], 't': data.get('t')}
                total, duplicate = store.add(rec)
            except (ValueError, KeyError, TypeError):
                return self.send(400, {'ok': False, 'error': 'bad request'})
            self.send(200, {'ok': True, 'lines': total, 'duplicate': duplicate})

    return Handler


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--queue', type=Path, required=True)
    p.add_argument('--reviews', type=Path, required=True)
    p.add_argument('--port', type=int, default=8780)
    p.add_argument('--host', default='0.0.0.0')
    a = p.parse_args()
    queue = json.loads(a.queue.read_text())
    token_file = a.reviews.with_suffix('.token')
    if token_file.exists():
        token = token_file.read_text().strip()
    else:
        token = secrets.token_urlsafe(9)
        token_file.parent.mkdir(parents=True, exist_ok=True)
        token_file.write_text(token + '\n')
    store = Store(a.reviews)
    html = (Path(__file__).with_name('label_review_app.html')).read_text()
    server = ThreadingHTTPServer((a.host, a.port), make_handler(queue, store, token, html))
    print(json.dumps({'items': len(queue['items']), 'saved_decisions': len(store.decisions),
                      'port': a.port, 'token': token}), flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
