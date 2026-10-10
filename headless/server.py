#!/usr/bin/env python3
"""M0 control worker: no scheduling, MIDI clock, or direct access to EEL memory."""
import argparse
import hmac
import ipaddress
import itertools
import json
import base64
import hashlib
import struct
import os
import math
import time
from registry import REGISTRY
from controller_config import binding_wire, decode
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).parent / 'web'

PATCH_KEYS={'format','schema','work_mem_size','globals','memory','controllerEngine','globalSnapshots'}
def validate_patch_extensions(patch):
    if not isinstance(patch,dict) or set(patch)-PATCH_KEYS:
        raise ValueError('Unsupported patch fields preserved; refusing to discard configuration.')
    if patch.get('format')!='MIDI_HUMAN_LOOPER_PATCH' or type(patch.get('schema')) is not int or not 1<=patch['schema']<=7:
        raise ValueError('Unsupported patch format/schema preserved; refusing overwrite or load.')
    for name,versions in (('controllerEngine',(1,)),('globalSnapshots',(1,2,3,4))):
        if name in patch and (not isinstance(patch[name],dict) or type(patch[name].get('version')) is not int or patch[name]['version'] not in versions):
            raise ValueError('Unsupported patch extension preserved; refusing to discard configuration.')

class Control:
    def __init__(self, path):
        self.path = path
        self.lock = threading.Lock()
        self.ids = itertools.count(1)

    def request(self, op=0, target=0, arg=0, revision=1, ch=0, note=0, value=0, session=0, patch=None, parameters=None, module=0, binding=None, name=None, settings=None, inclusions=None, macro=None):
        # One worker producer owns the engine's command queue; HTTP threads never
        # inspect live engine state. A timeout does not cancel an already executed TEST.
        with self.lock:
            request_id = next(self.ids)
            line = f'{request_id} {op} {target} {arg} {revision} {ch} {note} {value}\n'
            if session:line=line.rstrip('\n')+f' session {session}\n'
            if op in (13,28):line=line.rstrip('\n')+f' {module}\n'
            if name is not None:line=line.rstrip('\n')+' '+name.encode('ascii').hex()+'\n'
            if settings is not None:line=line.rstrip('\n')+' '+' '.join(format(v,'.17g') for v in settings)+'\n'
            if inclusions is not None:line=line.rstrip('\n')+' include '+str(len(inclusions))+' '+ ' '.join(str(v) for a in inclusions for v in (a['instrumentId'],a['moduleId'],a['kind'],int(a['included'])))+'\n'
            if macro is not None:line=line.rstrip('\n')+' '+' '.join(format(v,'.17g') for v in macro)+'\n'
            if parameters is not None:
                line=line.rstrip('\n')+f' {module} {len(parameters)} '+ ' '.join(f"{p['kind']} {p['value']:.17g}" for p in parameters)+'\n'
            if binding is not None:line=line.rstrip('\n')+' '+' '.join(format(v,'.17g') for v in binding)+'\n'
            if patch is not None:
                validate_patch_extensions(patch)
                line = line.rstrip('\n') + ' ' + ' '.join(format(v, '.17g') for v in patch['globals']+patch['memory'])+'\n'
                if 'controllerEngine' in patch:
                    decode(patch['controllerEngine'])
                    line=line.rstrip('\n')+' controllers '+' '.join(format(v,'.17g') for v in patch['controllerEngine']['configuration'])+'\n'
                if 'globalSnapshots' in patch:
                    snapshot_wire=patch['globalSnapshots'].get('configuration')
                    if type(patch['globalSnapshots'].get('version')) is not int or patch['globalSnapshots'].get('version') not in (1,2,3,4) or not isinstance(snapshot_wire,list) or len(snapshot_wire)>52000 or any(type(v) not in (int,float) or not math.isfinite(v) for v in snapshot_wire):raise ValueError('invalid snapshots')
                    # The native worker validates the complete versioned structure.
                    if 'controllerEngine' not in patch:
                        line=line.rstrip('\n')+' controllers '+' '.join(format(v,'.17g') for v in [1]+[0]*64+([0,0,0,0,0,1,0,0,0,0,0,.02,.2,1,1,.5,1,2]+[0,0,0,1,1,0]+[0]*42)*32)+'\n'
                    line=line.rstrip('\n')+' snapshots '+' '.join(format(v,'.17g') for v in snapshot_wire)+'\n'
            with socket.socket(socket.AF_UNIX) as client:
                client.settimeout(15)
                client.connect(self.path)
                client.sendall(line.encode('ascii'))
                data = bytearray()
                while b'\n' not in data:
                    chunk = client.recv(4096)
                    if not chunk:
                        raise ConnectionError('engine disconnected')
                    data.extend(chunk)
                    if len(data) > 16000000:
                        raise ValueError('oversized engine response')
            return json.loads(data)

class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def websocket(self):
        self.close_connection = True
        if self.server.token:
            # Browser WebSocket API cannot set custom headers: first client frame
            # authenticates, rather than putting the secret in a logged URL.
            pass
        key=self.headers.get('Sec-WebSocket-Key','')
        try:
            if len(base64.b64decode(key,validate=True))!=16 or self.headers.get('Sec-WebSocket-Version')!='13': raise ValueError()
        except ValueError:
            self.respond(400, {'error':'invalid WebSocket handshake'});return
        self.send_response(101)
        self.send_header('Upgrade','websocket');self.send_header('Connection','Upgrade')
        self.send_header('Sec-WebSocket-Accept',base64.b64encode(hashlib.sha1((key+'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest()).decode());self.end_headers()
        try:
            header=self.rfile.read(2)
            if len(header)!=2 or header[0]!=0x81 or not header[1]&128: return
            n=header[1]&127
            if n==126:n=struct.unpack('!H',self.rfile.read(2))[0]
            if n>1024:return
            mask=self.rfile.read(4);payload=self.rfile.read(n)
            if len(mask)!=4 or len(payload)!=n:return
            message=json.loads(bytes(c^mask[i%4] for i,c in enumerate(payload)))
            if not isinstance(message,dict) or not hmac.compare_digest(str(message.get('token','')),self.server.token):return
            self.connection.settimeout(2)
            while True:
                state=self.server.control.request()
                payload=json.dumps(state,separators=(',',':')).encode()
                prefix=bytes([0x81,len(payload)]) if len(payload)<126 else bytes([0x81,126])+struct.pack('!H',len(payload)) if len(payload)<=65535 else bytes([0x81,127])+struct.pack('!Q',len(payload))
                self.wfile.write(prefix+payload);self.wfile.flush()
                time.sleep(.25)
        except (OSError, ValueError, EOFError):
            return

    def log_message(self, *args):
        pass  # Never log token/header contents.

    def respond(self, code, data, content_type='application/json'):
        body = json.dumps(data).encode() if content_type == 'application/json' else data
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'")
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def allowed(self, api=False):
        try:
            host = urlsplit('http://' + self.headers.get('Host', '')).hostname
        except ValueError:
            host = None
        try:
            private_ip = ipaddress.ip_address(host).is_private
        except ValueError:
            private_ip = False
        if host not in ('localhost', '127.0.0.1', self.server.bind_address) and not (self.server.token and private_ip):
            self.respond(403, {'error': 'invalid host'})
            return False
        origin = self.headers.get('Origin')
        if origin and origin != 'http://' + self.headers.get('Host', ''):
            self.respond(403, {'error': 'same-origin required'})
            return False
        if api and self.server.token and not hmac.compare_digest(self.headers.get('X-Engine-Token', ''), self.server.token):
            self.respond(401, {'error': 'token required'})
            return False
        return True

    def engine(self, **kwargs):
        try:
            data = self.server.control.request(**kwargs)
            code = {'ok': 200, 'conflict': 409, 'unknown_target': 422,
                    'queue_full': 503, 'invalid': 400}.get(data.get('status'), 502)
            self.respond(code, data)
        except (OSError, ValueError) as error:
            self.respond(503, {'error': 'engine unavailable'})

    def do_GET(self):
        path = urlsplit(self.path).path
        if not self.allowed(api=path.startswith('/api/') and path!='/api/v1/ws'):
            return
        if path=='/api/v1/ws' and self.headers.get('Upgrade','').lower()=='websocket':
            self.websocket();return
        if path == '/api/v1/descriptors':
            document=REGISTRY.document()
            document['runtimeCapabilities']={'transformerTypes':[1,2,3,4,5,6], 'humanizer':False, 'echocity':False, 'phraseTransformers':False, 'snapshots':True, 'reaperSnapshots':False, 'ordering':'legacy-stages-or-serial-pitch'}
            self.respond(200,document);return
        if path.startswith('/api/v1/snapshot/'):
            try:
                id=int(path.rsplit('/',1)[-1])
                if not 1<=id<=16777215:raise ValueError()
                data=self.server.control.request(op=29,target=id,revision=-1)
                record=data.get('snapshotDetail')
                self.respond(200 if record else 404,record or {'error':'snapshot not found'})
            except (ValueError,KeyError,OSError):self.respond(503,{'error':'snapshot details unavailable'})
            return
        if path == '/api/v1/state':
            self.engine()
            return
        files = {'/': ('index.html', 'text/html; charset=utf-8'),
                 '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                 '/style.css': ('style.css', 'text/css; charset=utf-8')}
        if path not in files:
            self.respond(404, {'error': 'not found'})
            return
        name, mime = files[path]
        self.respond(200, (ROOT / name).read_bytes(), mime)

    def do_POST(self):
        if not self.allowed(api=True):
            return
        if self.path in ('/api/v1/patch/save','/api/v1/patch/load','/api/v1/patch/export'):
            self.patch_command();return
        if self.path != '/api/v1/command':
            self.respond(404, {'error': 'not found'})
            return
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            self.respond(415, {'error': 'JSON required'})
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if length < 1 or length > 32768:
                self.respond(413, {'error': 'command size limit'})
                return
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict) or type(data.get('protocolVersion')) is not int or data.get('protocolVersion') != 1:
                raise ValueError('protocolVersion 1 required')
            revision = data.get('expectedRevision')
            if type(revision) is not int or not 0 <= revision < 2147483647:
                raise ValueError('expectedRevision required')
            session=data.get('expectedEngineSessionId')
            if type(session) is not int or not 1<=session<=9007199254740991:raise ValueError('engine session required')
            action = data.get('action')
            if length>2048 and action!='snapshot_commit':
                self.respond(413,{'error':'command size limit'});return
            if action in ('snapshot_capture','snapshot_update','snapshot_duplicate','snapshot_delete','snapshot_move','snapshot_rename','snapshot_recall','snapshot_morph','snapshot_commit'):
                target=data.get('snapshotId',0)
                if type(target) is not int or not 0<=target<=16777215 or (action!='snapshot_capture' and not target):raise ValueError()
                direction=data.get('direction','up')
                if direction not in ('up','down'):raise ValueError()
                args=dict(op={'snapshot_capture':20,'snapshot_update':21,'snapshot_duplicate':22,'snapshot_delete':23,'snapshot_move':24,'snapshot_rename':25,'snapshot_recall':26,'snapshot_morph':26,'snapshot_commit':27}[action],target=target,arg=int(direction=='down'))
                if action in ('snapshot_recall','snapshot_morph','snapshot_commit'):args['arg']=int(action=='snapshot_morph')
                if action in ('snapshot_rename','snapshot_commit'):
                    name=data.get('name')
                    if not isinstance(name,str) or not 1<=len(name)<=48 or any(ord(c)<32 or ord(c)>126 for c in name):raise ValueError()
                    args['name']=name
                if action=='snapshot_commit':
                    seconds,ease,switching=data.get('seconds'),data.get('ease'),data.get('switching')
                    if type(seconds) not in (int,float) or not math.isfinite(seconds) or not 0<=seconds<=30 or type(ease) is not int or ease not in (0,1) or type(switching) is not int or switching not in (1,2,3,4):raise ValueError()
                    args['settings']=[seconds,ease,switching]
                    if 'inclusions' in data:
                        masks=data['inclusions']
                        if not isinstance(masks,list) or len(masks)>512:raise ValueError()
                        for a in masks:
                            if not isinstance(a,dict) or any(type(a.get(k)) is not int for k in ('instrumentId','moduleId','kind')) or not 1<=a['instrumentId']<=16777215 or not 0<=a['moduleId']<=16777215 or (not 0<=a['kind']<=24 or a['kind']==16) or type(a.get('included')) is not bool:raise ValueError()
                        args['inclusions']=masks
            elif action=='snapshot_ab_configure':
                a,b,ease,position=data.get('a'),data.get('b'),data.get('ease',0),data.get('position',0)
                if any(type(v) is not int for v in (a,b,ease)) or not 0<=a<=16777215 or not 0<=b<=16777215 or ease not in (0,1) or (bool(a)!=bool(b)) or (a and a==b) or type(position) not in (int,float) or not math.isfinite(position) or not 0<=position<=1:raise ValueError()
                args=dict(op=30,target=a,arg=ease,macro=[b,position])
            elif action=='snapshot_ab_position':
                position=data.get('position')
                if type(position) not in (int,float) or not math.isfinite(position) or not 0<=position<=1:raise ValueError()
                a,b=data.get('a',0),data.get('b',0)
                if any(type(v) is not int or not 0<=v<=16777215 for v in (a,b)):raise ValueError()
                args=dict(op=31,target=a,macro=[b,position])
            elif action == 'snapshot_switch':
                target,gesture,kind,snapshot=data.get('switchId'),data.get('gesture'),data.get('snapshotAction'),data.get('snapshotId',0)
                if any(type(v) is not int for v in (target,gesture,kind,snapshot)) or not 1<=target<=16777215 or not 0<=gesture<=2 or not 0<=kind<=7 or not 0<=snapshot<=16777215:raise ValueError()
                args=dict(op=28,target=target,arg=gesture,ch=kind,module=snapshot)
            elif action == 'test':
                target, gesture = data.get('switchId'), data.get('gesture', 'tap')
                if type(target) is not int or not 1 <= target <= 16777215 or gesture not in ('tap', 'double', 'hold'):
                    raise ValueError('invalid switch or gesture')
                args = dict(op=1, target=target, arg=('tap', 'double', 'hold').index(gesture))
            elif action in ('controller_source','controller_learn','controller_forget','controller_cancel','controller_confirm','mapping_delete','controller_return','controller_capture'):
                target=data.get('sourceId') if action.startswith('controller_') and action not in ('controller_return','controller_capture') else data.get('mappingId') if action=='mapping_delete' else data.get('targetId')
                if type(target) is not int or not 1<=target<=16777215:raise ValueError()
                if action=='controller_source':
                    kind,channel,number=data.get('kind',0),data.get('channel',1),data.get('number',0)
                    if any(type(v) is not int for v in (kind,channel,number)) or not 0<=kind<=2 or not 1<=channel<=16 or not 0<=number<=127:raise ValueError()
                    args=dict(op=14,target=target,arg=kind,ch=channel-1,note=number)
                elif action=='mapping_delete':args=dict(op=17,target=target)
                elif action in ('controller_return','controller_capture'):args=dict(op=18,target=target,arg=int(action=='controller_capture'))
                else:args=dict(op=15,target=target,arg={'controller_learn':0,'controller_cancel':1,'controller_confirm':2,'controller_forget':3}[action])
            elif action=='mapping_commit':
                binding=binding_wire(data.get('mapping'));args=dict(op=16,target=binding[0],binding=binding)
            elif action=='midi_cc':
                channel,number,value=data.get('channel'),data.get('number'),data.get('value')
                if any(type(v) is not int for v in (channel,number,value)) or not 1<=channel<=16 or not 0<=number<=127 or not 0<=value<=127:raise ValueError()
                args=dict(op=19,ch=channel-1,note=number,value=value)
            elif action == 'panic':
                args = dict(op=2)
            elif action=='parameter_set':
                target,module,kind,value=data.get('targetId'),data.get('moduleId',0),data.get('kind'),data.get('value')
                if any(type(v) is not int for v in (target,module,kind)) or not 1<=target<=16777215 or not 0<=module<=16777215 or kind==16 or type(value) not in (int,float) or not math.isfinite(value):raise ValueError()
                p=next((p for p in REGISTRY.parameters.values() if p['engineKind']==kind),None)
                if not p or not p['min']<=value<=p['max'] or (kind!=14 and abs(value/p['step']-round(value/p['step']))>1e-6):raise ValueError()
                args=dict(op=32,target=target,arg=kind,macro=[module,value])
            elif action=='module_structure':
                target=data.get('instrumentId');module=data.get('moduleId',0);op=data.get('operation');type_=data.get('engineType',0)
                if any(type(v) is not int or not 0<=v<=16777215 for v in (target,module,type_)) or not target or op not in ('add','delete','bypass','up','down'):raise ValueError()
                if op=='add' and type_ not in REGISTRY.engine_types:raise ValueError()
                args=dict(op=13,target=target,module=module,arg=('add','delete','bypass','up','down').index(op)+1,note=type_)
            elif action in ('phrase_learn','phrase_learn_cancel','phrase_forget','phrase_learn_confirm'):
                target=data.get('phraseId')
                if type(target) is not int or not 1<=target<=16:raise ValueError()
                args=dict(op=34,target=target,arg=('phrase_learn','phrase_learn_cancel','phrase_forget','phrase_learn_confirm').index(action))
            elif action in ('instrument_add','instrument_delete'):
                target=data.get('instrumentId',0)
                if type(target) is not int or not 0<=target<=16777215 or (action=='instrument_delete' and not target):raise ValueError()
                args=dict(op=33,target=target,arg=int(action=='instrument_delete'))
            elif action=='instrument_commit':
                target=data.get('instrumentId');values=[data.get(k) for k in ('enabled','input','output','level')]
                if type(target) is not int or not 1<=target<=16777215 or any(type(v) is not int or not 0<=v<=limit for v,limit in zip(values,(1,16,16,127))):raise ValueError()
                args=dict(op=11,target=target,arg=values[0],ch=values[1],note=values[2],value=values[3])
            elif action=='module_commit':
                target=data.get('instrumentId');module=data.get('moduleId');parameters=data.get('parameters')
                if any(type(v) is not int or not 1<=v<=16777215 for v in (target,module)) or not isinstance(parameters,list) or not 1<=len(parameters)<=4:raise ValueError()
                seen=set()
                for p in parameters:
                    if not isinstance(p,dict) or type(p.get('kind')) is not int or p['kind'] in seen or type(p.get('value')) not in (int,float) or not math.isfinite(p['value']):raise ValueError()
                    descriptor=next((d for d in REGISTRY.parameters.values() if d['engineKind']==p['kind']),None)
                    if not descriptor or not descriptor['min']<=p['value']<=descriptor['max']:raise ValueError()
                    # Current native kinds are quantized with the exact JSFX step.
                    step=descriptor['step']
                    if abs(p['value']/step-round(p['value']/step))>1e-6:raise ValueError()
                    seen.add(p['kind'])
                args=dict(op=12,target=target,module=module,parameters=parameters)
            elif action in ('instrument_route','instrument_enabled'):

                target=data.get('instrumentId');field=data.get('field','enabled');value=data.get('value')
                if type(target) is not int or not 1<=target<=16777215 or field not in ('input','output','level','enabled') or type(value) is not int or not 0<=value<=(127 if field=='level' else 1 if field=='enabled' else 16):raise ValueError()
                args=dict(op=10 if field=='enabled' else 9,target=target,arg=('input','output','level').index(field) if field!='enabled' else 0,value=value)
            elif action in ('phrase_play','phrase_record','phrase_finish'):
                target=data.get('phraseId')
                if type(target) is not int or not 1<=target<=16:raise ValueError('invalid phrase')
                args=dict(op={'phrase_play':6,'phrase_record':7,'phrase_finish':8}[action],target=target-1)
            elif action == 'midi':
                channel, note, value = data.get('channel'), data.get('note'), data.get('value')
                if any(type(v) is not int for v in (channel, note, value)) or not (1 <= channel <= 16 and 0 <= note <= 127 and 0 <= value <= 127):
                    raise ValueError('invalid simulated MIDI')
                args = dict(op=3, ch=channel-1, note=note, value=value)
            else:
                raise ValueError('unknown command')
        except (ValueError, TypeError, json.JSONDecodeError):
            self.respond(400, {'error': 'invalid command'})
            return
        self.engine(revision=revision, session=session, **args)

    def patch_command(self):
        try:
            n=int(self.headers.get('Content-Length','0'))
            if not 0<n<=2048:raise ValueError()
            data=json.loads(self.rfile.read(n));slot=data.get('slot');rev=data.get('expectedRevision');session=data.get('expectedEngineSessionId')
            if type(session) is not int or not 1<=session<=9007199254740991:raise ValueError()
            if type(slot) is not int or slot not in (1,2,3,4) or type(rev) is not int or not 1<=rev<2147483647:raise ValueError()
            path=self.server.patch_dir/f'patch{slot}.json'
            if self.path.endswith('/save') or self.path.endswith('/export'):
                if path.exists():
                    previous=json.loads(path.read_text())
                    try:validate_patch_extensions(previous)
                    except ValueError as error:
                        self.respond(422,{'error':str(error)});return
                patch=self.server.control.request(op=4,revision=rev,session=session)
                if patch.get('status')=='conflict':self.respond(409,patch);return
                if patch.get('format')!='MIDI_HUMAN_LOOPER_PATCH':raise ValueError()
                if self.path.endswith('/export'):
                    snapshots=patch.get('globalSnapshots',{}).get('configuration',[])
                    if len(snapshots)>=4 and snapshots[3]:
                        self.respond(422,{'error':'REAPER cannot yet execute Global Snapshots; export refused to preserve snapshot data.'});return
                    patch.pop('globalSnapshots',None)
                    patch.pop('controllerEngine',None)
                    path=self.server.patch_dir/f'patch{slot}-reaper.json'
                self.server.patch_dir.mkdir(parents=True,exist_ok=True)
                temp=path.with_suffix('.tmp')
                # Serialize patch writes independently from command execution.
                with self.server.patch_lock:
                    with temp.open('w') as f:
                        json.dump(patch,f,allow_nan=False,separators=(',',':'));f.flush();os.fsync(f.fileno())
                    temp.replace(path)
                self.respond(200,{'status':'saved','slot':slot,'file':path.name})
            else:
                if path.stat().st_size>16000000:raise ValueError()
                patch=json.loads(path.read_text())
                try:validate_patch_extensions(patch)
                except ValueError as error:
                    self.respond(422,{'error':str(error)});return
                schema=patch.get('schema');memory=patch.get('memory');globals_=patch.get('globals')
                if patch.get('format')!='MIDI_HUMAN_LOOPER_PATCH' or type(schema) is not int or not 1<=schema<=7 or not isinstance(memory,list) or patch.get('work_mem_size')!=len(memory) or not 0<len(memory)<=200000 or not isinstance(globals_,list) or len(globals_)!=9:raise ValueError()
                if any(type(x) not in (int,float) or not math.isfinite(x) for x in globals_+memory):raise ValueError()
                result=self.server.control.request(op=5,target=schema,revision=rev,session=session,patch=patch)
                if result.get('status')!='ok':self.respond(409 if result.get('status')=='conflict' else 400,result);return
                self.engine()
        except FileNotFoundError:
            self.respond(404,{'error':'patch not saved'})
        except (ValueError,TypeError,AttributeError):
            self.respond(400,{'error':'invalid patch'})
        except OSError:
            self.respond(503,{'error':'patch I/O or engine unavailable'})


def make_server(bind, port, path, token='',patch_dir=None):
    if bind not in ('127.0.0.1', 'localhost') and not token:
        raise ValueError('explicit token required for LAN binding')
    server = ThreadingHTTPServer((bind, port), Handler)
    server.bind_address, server.token, server.control = bind, token, Control(path)
    server.patch_dir=Path(patch_dir) if patch_dir else Path.home()/'.local/share/midi-human-looper'
    server.patch_lock=threading.Lock()
    server.daemon_threads=True
    return server

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--socket', required=True)
    parser.add_argument('--bind', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--token-file', type=Path)
    parser.add_argument('--patch-dir',type=Path)
    args = parser.parse_args()
    token = args.token_file.read_text().strip() if args.token_file else ''
    server = make_server(args.bind, args.port, args.socket, token,args.patch_dir)
    print(f'EDITOR http://{args.bind}:{server.server_port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()  # Engine is a separate process and remains running.
