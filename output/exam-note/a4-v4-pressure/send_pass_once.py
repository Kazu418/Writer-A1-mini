# Historical printer transport: enabled only on the owner machine.
import os as _writer_owner_os
if _writer_owner_os.environ.get("WRITER_A1_MINI_OWNER_CONTROL") != "1":
    raise RuntimeError("Owner-only hardware control. Friends use scripts/prepare_handoff.py; see docs/OWNER_OPERATIONS.md")

"""Dispatch one authorized A4 v4 contact pass using the established pinned transport."""
import ftplib
import hashlib
import io
import json
import os
from pathlib import Path
import socket
import ssl
import sys
import threading
import time
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'src'))
from plotnote import contact_test
from plotnote.profile import Profile
from plotnote.printer_state import require_plot_ready
from plotnote.validate import validate_gcode
from plotnote.package import read_package
import paho.mqtt.client as mqtt

HOST='192.168.2.112'
SERIAL='0309FA590900303'
PIN='527af761368117e670669b2b89d19d20fb70a272a34cb957924db954c2301d5e'
HERE=Path(__file__).resolve().parent/'gcode'
JOURNAL=HERE/'live-air-run.json'


def tls_context():
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname=False
    context.verify_mode=ssl.CERT_NONE
    context.maximum_version=ssl.TLSVersion.TLSv1_2
    return context


def check_pin(sock):
    if hashlib.sha256(sock.getpeercert(binary_form=True)).hexdigest()!=PIN:
        sock.close()
        raise ssl.SSLError('Printer certificate pin mismatch; credentials not sent')
    return sock


class PinnedMQTT(mqtt.Client):
    def _ssl_wrap_socket(self,sock):
        return check_pin(super()._ssl_wrap_socket(sock))


class PinnedFTPS(ftplib.FTP_TLS):
    def connect(self,host='',port=990,timeout=20,source_address=None):
        self.host=host;self.port=port;self.timeout=timeout;self.source_address=source_address
        self.sock=check_pin(self.context.wrap_socket(socket.create_connection((host,port),timeout),server_hostname=host))
        self.af=self.sock.family
        self.file=self.sock.makefile('r',encoding=self.encoding)
        self.welcome=self.getresp()
        return self.welcome

    def ntransfercmd(self,cmd,rest=None):
        sock,size=ftplib.FTP.ntransfercmd(self,cmd,rest)
        if self._prot_p:
            sock=check_pin(self.context.wrap_socket(sock,server_hostname=self.host,session=self.sock.session))
        return sock,size

    def storbinary(self,cmd,fp,blocksize=8192,callback=None,rest=None):
        # The printer does not complete TLS close_notify; stdlib unwrap() hangs.
        # Close only the data socket, then require the FTP completion response.
        self.voidcmd('TYPE I')
        with self.transfercmd(cmd,rest) as connection:
            while chunk:=fp.read(blocksize):
                connection.sendall(chunk)
                if callback:callback(chunk)
        return self.voidresp()

    def retrbinary(self,cmd,callback,blocksize=8192,rest=None):
        self.voidcmd('TYPE I')
        with self.transfercmd(cmd,rest) as connection:
            while chunk:=connection.recv(blocksize):callback(chunk)
        return self.voidresp()


def main(*,tile,attempt=1):
    if type(attempt) is not int or attempt < 1: raise SystemExit("Invalid attempt")
    writing=True
    if tile not in {f"face{f}-pass{p}" for f in (1,2) for p in (1,2)}: raise SystemExit("Invalid pass")
    if os.environ.get('PLOTNOTE_Z5_CONFIRMED')!='1':raise SystemExit('Renewed physical Z5 contact confirmation required')
    if type(writing) is not bool:raise SystemExit('Invalid test mode')
    journal_path=HERE/(tile+('-live-run.json' if attempt == 1 else f'-live-run-attempt{attempt}.json'))
    if journal_path.exists() and json.loads(journal_path.read_text()).get('start_sent'):
        raise SystemExit('This test was already dispatched. Refusing a duplicate start; inspect its live run journal.')
    password=os.environ.get('PLOTNOTE_ACCESS_CODE')
    if not password:raise SystemExit('PLOTNOTE_ACCESS_CODE is required')
    label=tile
    artifact=HERE/(label+'.gcode.3mf')
    raw=artifact.read_bytes();code=read_package(artifact)
    profile=Profile.load(HERE/(tile+"-profile.json"))
    validation=validate_gcode(code,profile)
    if code!=(HERE/(label+'.gcode')).read_text():raise SystemExit('Package/raw G-code mismatch')
    journal={'authorized_action':'one user-authorized A4 v4 contact pass; air run explicitly declined','host':HOST,'serial':SERIAL,
             'certificate_sha256':PIN,'local_package_sha256':hashlib.sha256(raw).hexdigest(),
             'validation':validation,'start_sent':False,'events':[]}
    def save():journal_path.write_text(json.dumps(journal,ensure_ascii=False,indent=2)+'\n')
    state={};version={};acks=[];state_lock=threading.Lock();ready=threading.Event()
    seq=int(time.time())
    client=PinnedMQTT(mqtt.CallbackAPIVersion.VERSION2,client_id='plotnote-'+label+'-'+str(seq),reconnect_on_failure=False)
    client.username_pw_set('bblp',password);client.tls_set_context(tls_context())
    def publish(body):
        # A1 firmware may execute QoS1 commands without returning PUBACK.
        # Use at-most-once transport; determine execution from printer reports.
        info=client.publish('device/'+SERIAL+'/request',json.dumps(body),qos=0)
        info.wait_for_publish(timeout=10)
        return info.is_published()
    def on_connect(c,u,flags,reason,props):
        if reason.is_failure:
            journal['connection_error']=str(reason);save();return
        c.subscribe('device/'+SERIAL+'/report',qos=0)
    def on_subscribe(c,u,mid,reasons,props):
        for body in [{'pushing':{'sequence_id':str(seq),'command':'pushall'}},
                     {'info':{'sequence_id':str(seq+1),'command':'get_version'}}]:
            c.publish('device/'+SERIAL+'/request',json.dumps(body),qos=0)
        ready.set()
    def on_message(c,u,msg):
        try:body=json.loads(msg.payload)
        except Exception:return
        with state_lock:
            if isinstance(body.get('print'),dict):
                data=body['print'];state.update(data)
                if data.get('command')!='push_status':acks.append(data)
            if isinstance(body.get('info'),dict):version.update(body['info'])
    client.on_connect=on_connect;client.on_subscribe=on_subscribe;client.on_message=on_message
    try:
        client.connect(HOST,8883,keepalive=30);client.loop_start()
        if not ready.wait(10):raise RuntimeError('MQTT subscription failed')
        end=time.monotonic()+12
        while time.monotonic()<end:
            with state_lock:
                found=bool(state.get('gcode_state') and version.get('module'))
            if found:break
            time.sleep(.2)
        with state_lock:before=dict(state);modules=list(version.get('module',[]))
        if not any(m.get('product_name')=='Bambu Lab A1 mini' for m in modules):
            raise RuntimeError('Target did not identify as A1 mini')
        require_plot_ready(before)
        journal['before']={k:before.get(k) for k in ('gcode_state','print_error','home_flag','nozzle_temper','nozzle_target_temper','bed_temper','bed_target_temper')}
        save();print('Fresh idle/model/heater checks passed.',flush=True)
        remote=('plotnote_write_' if writing else 'plotnote_air_')+datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')+'.gcode.3mf'
        journal['remote_file']=remote;save()
        ftp=PinnedFTPS(context=tls_context(),timeout=20)
        def phase(value):
            journal['transfer_phase']=value;save();print('FTPS',value,flush=True)
        try:
            phase('connecting')
            ftp.connect(HOST,990);phase('connected')
            ftp.login('bblp',password);phase('authenticated')
            ftp.prot_p();ftp.voidcmd('TYPE I');phase('uploading')
            ftp.storbinary('STOR /'+remote,io.BytesIO(raw),blocksize=8192)
            phase('upload_finished')
            if ftp.size('/'+remote)!=len(raw):raise RuntimeError('Uploaded package size mismatch')
            phase('readback_verification')
            returned=io.BytesIO();ftp.retrbinary('RETR /'+remote,returned.write)
            if returned.getvalue()!=raw:raise RuntimeError('Uploaded package byte-for-byte verification failed')
            ftp.quit()
        finally:
            ftp.close()
        journal['remote_file']=remote;journal['upload_verified']=True;save()
        print(label+' package uploaded and verified byte-for-byte.',flush=True)
        # Recheck local state in case another job started during transfer.
        with state_lock:latest=dict(state)
        require_plot_ready(latest)
        request={'print':{'sequence_id':str(seq+2),'command':'project_file',
            'param':'Metadata/plate_1.gcode','url':'ftp:///'+remote,
            'subtask_name':'PlotNote A4 v4 '+tile+f' attempt{attempt}',
            'md5':hashlib.md5(code.encode()).hexdigest(),
            'project_id':'0','profile_id':'0','task_id':'0','subtask_id':'0',
            'bed_type':'auto','timelapse':False,'bed_leveling':False,'flow_cali':False,
            'vibration_cali':False,'layer_inspect':False,'use_ams':False,'ams_mapping':[]}}
        journal['request']=request;journal['start_sent']=True;journal['start_time_utc']=datetime.now(timezone.utc).isoformat();save()
        try:
            journal['transport_write_confirmed']=publish(request)
        except Exception as error:
            journal['transport_write_confirmed']=False
            journal['transport_observation_error']=type(error).__name__
        save()
        print('ONE '+label+' start command dispatched; monitoring. No automatic retry.',flush=True)
        # Drop the command connection and observe on a clean session: no queued
        # start packet can be replayed if the printer reconnects during startup.
        client.disconnect();client.loop_stop()
        ready.clear()
        client=PinnedMQTT(mqtt.CallbackAPIVersion.VERSION2,client_id='plotnote-observe-'+str(seq),reconnect_on_failure=False)
        client.username_pw_set('bblp',password);client.tls_set_context(tls_context())
        client.on_connect=on_connect;client.on_subscribe=on_subscribe;client.on_message=on_message
        client.connect(HOST,8883,keepalive=30);client.loop_start()
        if not ready.wait(10):raise RuntimeError('Read-only monitoring connection unavailable after start; do not resend')
        seen_active=False;last_signature=None;end=time.monotonic()+7200
        while time.monotonic()<end:
            with state_lock:current=dict(state);replies=list(acks)
            relevant=[a for a in replies if a.get('command')=='project_file' and str(a.get('sequence_id'))==str(seq+2)]
            if relevant:
                journal['start_ack']=relevant[-1]
                result=str(relevant[-1].get('result','')).upper()
                if result in ('FAIL','FAILED','FAILURE'):
                    journal['outcome']='start_rejected';save();print('START REJECTED:',json.dumps(relevant[-1]),flush=True);return 3
            signature=tuple(current.get(k) for k in ('gcode_state','mc_percent','stg_cur','nozzle_target_temper','bed_target_temper','print_error'))
            if signature!=last_signature:
                event={'utc':datetime.now(timezone.utc).isoformat(),**{k:current.get(k) for k in ('gcode_state','gcode_file','mc_percent','stg_cur','nozzle_temper','nozzle_target_temper','bed_temper','bed_target_temper','print_error')}}
                journal['events'].append(event);save();print('STATUS',json.dumps(event),flush=True);last_signature=signature
            value=current.get('gcode_state')
            if value in ('PREPARE','RUNNING','SLICING'):seen_active=True
            unsafe=current.get('print_error',0) or current.get('bed_target_temper',0)>0 or current.get('nozzle_target_temper',0)>80
            if unsafe and value in ('PREPARE','RUNNING','PAUSE'):
                publish({'print':{'sequence_id':str(seq+3),'command':'stop'}})
                journal['outcome']='stop_requested_due_to_unexpected_state';save()
                print('STOP requested due to unexpected heater/error state.',flush=True);return 4
            if seen_active and value in ('FINISH','FAILED','IDLE'):
                journal['outcome']='completed' if value=='FINISH' and not current.get('print_error',0) else 'terminated_'+str(value)
                journal['after']={k:current.get(k) for k in ('gcode_state','mc_percent','print_error','hms','nozzle_temper','nozzle_target_temper','bed_temper','bed_target_temper')}
                save();print('RESULT',json.dumps({'outcome':journal['outcome'],'after':journal['after']}),flush=True)
                return 0 if journal['outcome']=='completed' else 5
            time.sleep(.25)
        journal['outcome']='monitor_timeout_do_not_resend';save()
        print('Monitoring timed out. No retry sent; inspect live printer before any further action.',flush=True);return 6
    finally:
        client.disconnect();client.loop_stop()


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pass',dest='tile',required=True,choices=['face1-pass1','face1-pass2','face2-pass1','face2-pass2'])
    parser.add_argument("--attempt", type=int, default=1)
    args=parser.parse_args()
    try:raise SystemExit(main(tile=args.tile,attempt=args.attempt))
    except Exception as error:
        print('Air-test operation stopped:',type(error).__name__,str(error),flush=True)
        import traceback
        traceback.print_exc()
        raise SystemExit(2)
