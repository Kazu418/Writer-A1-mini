import importlib.util
import json
from pathlib import Path
import threading
import urllib.error
import urllib.request

from http.server import ThreadingHTTPServer

spec = importlib.util.spec_from_file_location(
    'label_review_app', Path(__file__).parents[1] / 'scripts/label_review_app.py')
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)

QUEUE = {'items': [{'id': 'a1', 'label': '生', 'goodnotes': '生', 'kind': 'agree_high',
                    'paths': [[1, 1, 2, 2]]},
                   {'id': 'b2', 'label': '活', 'goodnotes': '括', 'kind': 'ai_only',
                    'paths': [[1, 1, 2, 2]]}]}


def start(tmp_path):
    store = app.Store(tmp_path / 'reviews.jsonl')
    handler = app.make_handler(QUEUE, store, 'tok', '<html>ok</html>')
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, store, f'http://127.0.0.1:{server.server_port}'


def post(base, body, token='tok'):
    req = urllib.request.Request(base + '/api/review?k=' + token, json.dumps(body).encode(),
                                 {'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def lines(path):
    return [json.loads(x) for x in path.read_text().splitlines() if x]


def test_token_required_for_page_and_data(tmp_path):
    server, _, base = start(tmp_path)
    for path in ('/', '/api/queue', '/api/state'):
        try:
            urllib.request.urlopen(base + path)
            assert False
        except urllib.error.HTTPError as e:
            assert e.code == 403
    assert urllib.request.urlopen(base + '/?k=tok').read() == b'<html>ok</html>'
    server.shutdown()


def test_answer_is_on_disk_before_ok_and_retry_is_idempotent(tmp_path):
    server, store, base = start(tmp_path)
    body = {'rid': 'rid-0001-aaaa', 'id': 'a1', 'v': 'yes', 't': 1}
    status, result = post(base, body)
    assert status == 200 and result['ok'] and not result['duplicate']
    written = lines(tmp_path / 'reviews.jsonl')   # already durable at response time
    assert written[0]['id'] == 'a1' and written[0]['v'] == 'yes'
    assert written[0]['proposed'] == '生'
    status, result = post(base, body)             # phone resends after a lost reply
    assert result['duplicate'] and len(lines(tmp_path / 'reviews.jsonl')) == 1
    server.shutdown()


def test_bad_requests_are_rejected_and_not_written(tmp_path):
    server, _, base = start(tmp_path)
    bad = [{'rid': 'rid-0002-aaaa', 'id': 'zzz', 'v': 'yes'},
           {'rid': 'rid-0002-aaaa', 'id': 'a1', 'v': 'maybe'},
           {'rid': 'short', 'id': 'a1', 'v': 'yes'},
           {'rid': 'rid-0002-aaaa', 'id': 'a1', 'v': 'fix', 'label': '二文'},
           {'rid': 'rid-0002-aaaa', 'id': 'a1', 'v': 'fix'}]
    for body in bad:
        assert post(base, body)[0] == 400
    assert post(base, {'rid': 'rid-0003-aaaa', 'id': 'a1', 'v': 'yes'}, token='wrong')[0] == 403
    assert not (tmp_path / 'reviews.jsonl').exists() or lines(tmp_path / 'reviews.jsonl') == []
    server.shutdown()


def test_resume_after_restart_undo_and_fix(tmp_path):
    server, _, base = start(tmp_path)
    post(base, {'rid': 'rid-0004-aaaa', 'id': 'a1', 'v': 'yes'})
    post(base, {'rid': 'rid-0005-aaaa', 'id': 'b2', 'v': 'fix', 'label': '括'})
    post(base, {'rid': 'rid-0006-aaaa', 'id': 'a1', 'v': 'undo'})
    server.shutdown()
    restarted = app.Store(tmp_path / 'reviews.jsonl')
    assert restarted.decisions == {'b2': {'v': 'fix', 'label': '括'}}


def test_torn_last_line_is_survived_without_losing_earlier_answers(tmp_path):
    path = tmp_path / 'reviews.jsonl'
    path.write_bytes(json.dumps({'rid': 'rid-0007-aaaa', 'id': 'a1', 'v': 'no'}).encode()
                     + b'\n{"rid":"rid-00')
    store = app.Store(path)
    assert store.decisions == {'a1': {'v': 'no', 'label': None}}
    store.add({'rid': 'rid-0008-aaaa', 'id': 'b2', 'v': 'yes', 'label': None})
    assert app.Store(path).decisions.keys() == {'a1', 'b2'}


def test_export_maps_decisions_without_changing_anything_else(tmp_path):
    spec2 = importlib.util.spec_from_file_location(
        'export_label_reviews', Path(__file__).parents[1] / 'scripts/export_label_reviews.py')
    exp = importlib.util.module_from_spec(spec2)
    spec2.loader.exec_module(exp)
    path = tmp_path / 'r.jsonl'
    rows = [
        {'rid': 'rid-00000001', 'id': 'a', 'v': 'yes', 'proposed': '生', 'goodnotes': '生'},
        {'rid': 'rid-00000002', 'id': 'b', 'v': 'fix', 'label': '括', 'proposed': '活', 'goodnotes': '括'},
        {'rid': 'rid-00000003', 'id': 'c', 'v': 'no', 'proposed': '数', 'goodnotes': '数'},
        {'rid': 'rid-00000004', 'id': 'd', 'v': 'no', 'proposed': '活', 'goodnotes': '括'},
        {'rid': 'rid-00000005', 'id': 'e', 'v': 'unsure', 'proposed': '点', 'goodnotes': '点'},
        {'rid': 'rid-00000006', 'id': 'f', 'v': 'yes', 'proposed': '字', 'goodnotes': '字'},
        {'rid': 'rid-00000007', 'id': 'f', 'v': 'undo', 'proposed': '字', 'goodnotes': '字'}]
    path.write_text('\n'.join(json.dumps(r) for r in rows) + '\n{"torn')
    data, skipped = exp.convert(exp.latest(path))
    assert data['reviews'] == [
        {'id': 'a', 'label': '生', 'status': 'accepted'},
        {'id': 'b', 'label': '括', 'status': 'accepted'},
        {'id': 'c', 'label': '数', 'status': 'rejected'}]
    assert skipped == {'unsure': 1, 'refused_ai_only': 1}
