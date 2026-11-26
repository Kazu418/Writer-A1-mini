# Historical printer transport: enabled only on the owner machine.
import os as _writer_owner_os
if _writer_owner_os.environ.get("WRITER_A1_MINI_OWNER_CONTROL") != "1":
    raise RuntimeError("Owner-only hardware control. Friends use scripts/prepare_handoff.py; see docs/OWNER_OPERATIONS.md")

"""Pen-removed, one-shot absolute positioning. Never homes or starts a job."""
import json
import os
import threading
import time
from datetime import datetime, timezone
from send_air_only import HOST, SERIAL, HERE, PinnedMQTT, tls_context, mqtt

path = HERE / 'position-z5-run.json'
if path.exists() and json.loads(path.read_text()).get('sent'):
    raise SystemExit('Already dispatched. Inspect physical position; do not resend automatically.')
state = {}
version = {}
acks = []
ready = threading.Event()
seq = str(int(time.time()))
client = PinnedMQTT(mqtt.CallbackAPIVersion.VERSION2,
    client_id='plotnote-z5-' + seq, reconnect_on_failure=False)
client.username_pw_set('bblp', os.environ['PLOTNOTE_ACCESS_CODE'])
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
    assert state.get('gcode_state') in ('IDLE', 'FINISH'), 'Printer busy'
    assert not state.get('print_error') and not state.get('hms'), 'Printer error'
    assert state.get('nozzle_target_temper') == 0 and state.get('bed_target_temper') == 0, 'Heaters active'
    # Paper contact calibration only; the user explicitly confirmed pen removal.
    # Absolute bed center pen position: nozzle Y120.8 + offset -30.8 = pen Y90.
    code = 'G21\nG90\nG1 Z15 F300\nM400\nG1 X90 Y120.8 F1200\nM400\nG1 Z5 F120\nM400\n'
    journal = {'utc': datetime.now(timezone.utc).isoformat(), 'sent': True,
        'pen_removed_confirmed_by_user': True, 'gcode': code,
        'before': {k: state.get(k) for k in ('gcode_state', 'home_flag', 'print_error', 'nozzle_target_temper', 'bed_target_temper')}}
    path.write_text(json.dumps(journal, indent=2) + '\n')
    info = client.publish('device/' + SERIAL + '/request', json.dumps(
        {'print': {'sequence_id': seq, 'command': 'gcode_line', 'param': code}}), qos=0)
    info.wait_for_publish(timeout=10)
    print('Positioning dispatched ONCE. Waiting for observation; no retry.', flush=True)
    time.sleep(16)
    journal['acks'] = acks
    journal['after'] = {k: state.get(k) for k in ('gcode_state', 'print_error', 'hms', 'nozzle_target_temper', 'bed_target_temper')}
    journal['physical_position_verified'] = False
    path.write_text(json.dumps(journal, indent=2) + '\n')
    print(json.dumps({'acks': acks, 'after': journal['after']}, ensure_ascii=False), flush=True)
finally:
    client.disconnect()
    client.loop_stop()
