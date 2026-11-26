# Historical printer transport: enabled only on the owner machine.
import os as _writer_owner_os
if _writer_owner_os.environ.get("WRITER_A1_MINI_OWNER_CONTROL") != "1":
    raise RuntimeError("Owner-only hardware control. Friends use scripts/prepare_handoff.py; see docs/OWNER_OPERATIONS.md")

"""Pen-removed homing, first-stroke XY positioning, and manual pen mounting at Z5."""
import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/"contact-test"))
from send_air_only import HOST, SERIAL, PinnedMQTT, tls_context, mqtt

import argparse
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--attempt', type=int, default=1)
parser.add_argument('--pen-removed', action='store_true', required=True)
args = parser.parse_args()
if args.attempt < 1:
    raise SystemExit('Invalid attempt')
path = HERE / ('face1-pass2-mount-run.json' if args.attempt == 1 else f'face1-pass2-mount-run-attempt{args.attempt}.json')
if path.exists() and json.loads(path.read_text()).get('sent'):
    raise SystemExit('Already dispatched. Inspect physical position; do not resend automatically.')
state = {}
version = {}
acks = []
ready = threading.Event()
seq = str(int(time.time()))
client = PinnedMQTT(mqtt.CallbackAPIVersion.VERSION2,
    client_id='plotnote-tile2-mount-' + seq, reconnect_on_failure=False)
client.username_pw_set('bblp', (lambda cfg: cfg.get('access_code',{}).get(SERIAL) or cfg.get('user_access_code',{}).get(SERIAL))(json.loads((Path.home()/'Library/Application Support/BambuStudio/BambuStudio.conf').read_text())))
client.tls_set_context(tls_context())

def connected(c, u, flags, reason, props):
    if not reason.is_failure:
        c.subscribe('device/' + SERIAL + '/report', qos=0)

def subscribed(c, u, mid, reasons, props):
    for body in ({'pushing': {'sequence_id': seq, 'command': 'pushall'}},
                 {'info': {'sequence_id': seq, 'command': 'get_version'}}):
        c.publish('device/' + SERIAL + '/request', json.dumps(body), qos=0)
    ready.set()

def message(c, u, msg):
    body = json.loads(msg.payload)
    state.update(body.get('print', {}))
    version.update(body.get('info', {}))
    p = body.get('print', {})
    if p.get('command') == 'gcode_line' and str(p.get('sequence_id')) == seq:
        acks.append(p)

client.on_connect = connected
client.on_subscribe = subscribed
client.on_message = message
try:
    client.connect(HOST, 8883, keepalive=30)
    client.loop_start()
    if not ready.wait(10):
        raise RuntimeError('Subscription failed; no motion sent')
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        if state.get('gcode_state') and version.get('module'):
            break
        time.sleep(.1)
    assert any(m.get('product_name') == 'Bambu Lab A1 mini' for m in version.get('module', [])), 'Wrong model'
    assert state.get('gcode_state') in ('IDLE', 'FINISH', 'FAILED'), 'Printer busy'
    assert not state.get('print_error') and not state.get('hms'), 'Printer error'
    assert state.get('nozzle_target_temper') == 0 and state.get('bed_target_temper') == 0, 'Heaters active'
    code = 'G28\nM400\nG21\nG90\nG1 Z15 F300\nM400\nG1 X12.501 Y159.464 F1200\nM400\nG1 Z5 F120\nM400\n'
    journal = {'utc': datetime.now(timezone.utc).isoformat(), 'sent': True,
        'authorized_action': 'User confirmed pen removed; home XYZ, position above the first stroke X12.501 Y159.464, lower nozzle to Z5 for manual pen mounting', 'gcode': code,
        'before': {k: state.get(k) for k in ('gcode_state', 'home_flag', 'print_error', 'nozzle_target_temper', 'bed_target_temper')}}
    path.write_text(json.dumps(journal, indent=2) + '\n')
    info = client.publish('device/' + SERIAL + '/request', json.dumps(
        {'print': {'sequence_id': seq, 'command': 'gcode_line', 'param': code}}), qos=0)
    info.wait_for_publish(timeout=10)
    print('Positioning dispatched ONCE. Waiting for observation; no retry.', flush=True)
    deadline = time.monotonic() + 90
    homed_since = None
    while time.monotonic() < deadline:
        flag = state.get('home_flag', 0)
        if type(flag) is int and flag & 7 == 7:
            if homed_since is None: homed_since = time.monotonic()
            if time.monotonic() - homed_since >= 25: break
        else: homed_since = None
        time.sleep(.25)
    journal['acks'] = acks
    journal['after'] = {k: state.get(k) for k in ('gcode_state', 'print_error', 'hms', 'home_flag', 'nozzle_target_temper', 'bed_target_temper')}
    journal['physical_position_verified'] = False
    path.write_text(json.dumps(journal, indent=2) + '\n')
    print(json.dumps({'acks': acks, 'after': journal['after']}, ensure_ascii=False), flush=True)
finally:
    client.disconnect()
    client.loop_stop()
