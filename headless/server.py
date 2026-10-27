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
from phrase_midi import read_smf, write_smf, MAX_BYTES
from registry import REGISTRY
from controller_config import binding_wire, decode
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).parent / 'web'

PATCH_KEYS={'format','schema','work_mem_size','globals','memory','controllerEngine','globalSnapshots','conductor','echocity','nativeExpressive','midiThru'}
def validate_patch_extensions(patch):
    if not isinstance(patch,dict) or set(patch)-PATCH_KEYS:
        raise ValueError('Unsupported patch fields preserved; refusing to discard configuration.')
    if patch.get('format')!='MIDI_HUMAN_LOOPER_PATCH' or type(patch.get('schema')) is not int or not 1<=patch['schema']<=8:
        raise ValueError('Unsupported patch format/schema preserved; refusing overwrite or load.')
    if 'conductor' in patch:
        from conductor import decode as decode_conductor
        decode_conductor(patch['conductor'])
    if 'echocity' in patch:
        from echocity_config import decode as decode_echo
        decode_echo(patch['echocity'])
        if patch['schema']!=8:raise ValueError('ECHOCITY requires the native patch format')
    if 'nativeExpressive' in patch:
        from native_expressive_config import decode as decode_expressive
        decode_expressive(patch['nativeExpressive'])
        if patch['schema']!=8:raise ValueError('Native expressive settings require schema 8')
    if 'midiThru' in patch:
        from midi_thru_config import decode as decode_midi_thru
        decode_midi_thru(patch['midiThru'])
        if patch['schema']!=8:raise ValueError('MIDI THRU rules require schema 8')
    for name,versions in (('controllerEngine',(1,2)),('globalSnapshots',(1,2,3,4))):
        if name in patch and (not isinstance(patch[name],dict) or set(patch[name])!={'version','configuration'} or type(patch[name].get('version')) is not int or patch[name]['version'] not in versions):
            raise ValueError('Unsupported patch extension preserved; refusing to discard configuration.')

class Control:
    def __init__(self, path):
        self.path = path
        self.lock = threading.RLock()
        self.ids = itertools.count(1)
        self._observation=None
        self._observation_until=0.0
        self._observation_json=None

    def observation(self):
        # Share one bounded-rate state copy across observers. The MIDI callback
        # still owns execution; this is only a read-only control-thread cache.
        with self.lock:
            if self._observation is None or time.monotonic()>=self._observation_until:
                self._observation=self.request()
                self._observation_until=time.monotonic()+.25
                self._observation_json=None
            return self._observation

    def observation_payload(self):
        # Immutable bytes shared by WebSocket subscribers for the same observed
        # state. This reduces worker serialization only, not MIDI callback work.
        with self.lock:
            state=self.observation()
            if self._observation_json is None:
                self._observation_json=json.dumps(state,separators=(',',':')).encode()
            return self._observation_json

    def request(self, op=0, target=0, arg=0, revision=1, ch=0, note=0, value=0, session=0, patch=None, parameters=None, module=0, binding=None, name=None, settings=None, inclusions=None, macro=None,instance=None, phrase=None,echo=None,expressive=None,midi_thru=None,midi_inputs=None):
        # One worker producer owns the engine's command queue; HTTP threads never
        # inspect live engine state. A timeout does not cancel an already executed TEST.
        with self.lock:
            if op!=0:
                self._observation=None
                self._observation_json=None
            request_id = next(self.ids)
            line = f'{request_id} {op} {target} {arg} {revision} {ch} {note} {value}\n'
            if session:line=line.rstrip('\n')+f' session {session}\n'
            if op in (13,28):line=line.rstrip('\n')+f' {module}\n'
            if name is not None:line=line.rstrip('\n')+' '+(name.encode('ascii').hex() or '-')+'\n'
            if settings is not None:line=line.rstrip('\n')+' '+' '.join(format(v,'.17g') for v in settings)+'\n'
            if inclusions is not None:line=line.rstrip('\n')+' include '+str(len(inclusions))+' '+ ' '.join(str(v) for a in inclusions for v in (a['instrumentId'],a['moduleId'],a['kind'],int(a['included'])))+'\n'
            if instance is not None:line=line.rstrip('\n')+' '+str(instance[0])+' '+str(instance[1])+'\n'
            if macro is not None:line=line.rstrip('\n')+' '+' '.join(format(v,'.17g') for v in macro)+'\n'
            if echo is not None:
                from echocity_config import decode as decode_echo
                decode_echo(echo)
                line=line.rstrip('\n')+' '+' '.join(format(v,'.17g') for v in echo['configuration'])+'\n'
            if expressive is not None:
                from native_expressive_config import decode as decode_expressive
                extension={'version':1,'configuration':expressive}
                decode_expressive(extension)
                values=' '.join(format(v,'.17g') for v in expressive)
                line=line.rstrip('\n')+(' '+values if op==55 else ' native_expressive '+values)+'\n'
            if midi_thru is not None:
                from midi_thru_config import decode as decode_midi_thru
                decode_midi_thru({'version':1,'configuration':midi_thru})
                if op!=56:raise ValueError('MIDI THRU carrier requires its dedicated operation')
                line=line.rstrip('\n')+' '+' '.join(str(v) for v in midi_thru)+'\n'
            if midi_inputs is not None:
                from midi_thru_config import validate_inputs
                validate_inputs(midi_inputs)
                if op!=57:raise ValueError('MIDI input carrier requires its dedicated operation')
                line=line.rstrip('\n')+' '+' '.join(str(v) for v in midi_inputs)+'\n'
            if parameters is not None:
                line=line.rstrip('\n')+f' {module} {len(parameters)} '+ ' '.join(f"{p['kind']} {p['value']:.17g}" for p in parameters)+'\n'
            if binding is not None:line=line.rstrip('\n')+' '+' '.join(format(v,'.17g') for v in binding)+'\n'
            if phrase is not None:
                line=line.rstrip('\n')+' '+format(phrase['lengthSeconds'],'.17g')+' '+str(len(phrase['events']))+' '+' '.join(format(v,'.17g') for e in phrase['events'] for v in e)+'\n'
            if patch is not None:
                if patch.get('schema') in range(1,8) and self.request().get('schemaVersion')==8:
                    from native_capacity import migrate
                    patch=migrate(patch);target=8
                    line=f'{request_id} {op} {target} {arg} {revision} {ch} {note} {value}'+(f' session {session}' if session else '')+'\n'
                validate_patch_extensions(patch)
                line = line.rstrip('\n') + ' ' + ' '.join(format(v, '.17g') for v in patch['globals']+patch['memory'])+'\n'
                if 'controllerEngine' in patch:
                    decode(patch['controllerEngine'])
                    line=line.rstrip('\n')+' controllers '+' '.join(format(v,'.17g') for v in patch['controllerEngine']['configuration'])+'\n'
                if 'globalSnapshots' in patch:
                    snapshot_wire=patch['globalSnapshots'].get('configuration')
                    if type(patch['globalSnapshots'].get('version')) is not int or patch['globalSnapshots'].get('version') not in (1,2,3,4) or not isinstance(snapshot_wire,list) or len(snapshot_wire)>220000 or any(type(v) not in (int,float) or not math.isfinite(v) for v in snapshot_wire):raise ValueError('invalid snapshots')
                    # The native worker validates the complete versioned structure.
                    if 'controllerEngine' not in patch:
                        line=line.rstrip('\n')+' controllers '+' '.join(format(v,'.17g') for v in [1]+[0]*64+([0,0,0,0,0,1,0,0,0,0,0,.02,.2,1,1,.5,1,2]+[0,0,0,1,1,0]+[0]*42)*32)+'\n'
                    line=line.rstrip('\n')+' snapshots '+' '.join(format(v,'.17g') for v in snapshot_wire)+'\n'
            if patch is not None and 'conductor' in patch:
                line=line.rstrip('\n')+' conductor '+str(len(patch['conductor']['configuration']))+' '+' '.join(str(v) for v in patch['conductor']['configuration'])+'\n'
            if patch is not None and 'echocity' in patch:
                line=line.rstrip('\n')+' echocity '+' '.join(format(v,'.17g') for v in patch['echocity']['configuration'])+'\n'
            if patch is not None and 'nativeExpressive' in patch:
                line=line.rstrip('\n')+' native_expressive '+' '.join(format(v,'.17g') for v in patch['nativeExpressive']['configuration'])+'\n'
            if patch is not None and 'midiThru' in patch:
                line=line.rstrip('\n')+' midi_thru '+' '.join(str(v) for v in patch['midiThru']['configuration'])+'\n'
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
                    if len(data) > 134217728:
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
                payload=self.server.control.observation_payload()
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

    def update_command(self, action=None):
        # Neither the editor token nor LAN trust grants executable installation.
        # Only this strict HTTP envelope reaches the separate root worker; native
        # authorization is deliberately not an accepted network field.
        try:
            import sys
            sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'zynthian/update'))
            from backend import client
            fields={}
            if action is None:
                if self.headers.get('Origin')!='http://'+self.headers.get('Host',''):
                    self.respond(403,{'error':'Explicit same-origin request required'});return
                if self.headers.get('Content-Type','').split(';')[0]!='application/json':
                    self.respond(415,{'error':'JSON required'});return
                length=int(self.headers.get('Content-Length','0'))
                if not 1<=length<=2048:raise ValueError('Update request size limit')
                fields=json.loads(self.rfile.read(length))
                if not isinstance(fields,dict) or set(fields)-{'action','password','confirm','revision'}:
                    raise ValueError('Invalid update fields')
                action=fields.pop('action',None)
                if action not in ('check','install','rollback','recover'):raise ValueError('Invalid update action')
            response=client(action,**fields)
            self.respond(200,response)
        except FileNotFoundError:
            self.respond(503,{'error':'UPDATE worker not installed; musical engine is unaffected'})
        except (OSError,ValueError,TypeError) as error:
            self.respond(403,{'error':str(error)})

    def do_GET(self):
        path = urlsplit(self.path).path
        if not self.allowed(api=path.startswith('/api/') and path!='/api/v1/ws'):
            return
        if path=='/api/v1/midi-inputs':
            self.midi_inputs_command(read_only=True);return
        if path == '/api/v1/zynthian/chains':
            self.host_chain_command(read_only=True);return
        if path == '/api/v1/patch-recall':
            self.host_chain_command(read_only=True,recall=True);return
        if path == '/api/v1/patches':
            self.server.switch_presets.active_slot=self.server.switch_presets.read()['activeSlot']
            from patch_names import read
            try:names=read(self.server.patch_dir)
            except ValueError as e:self.respond(422,{'error':str(e)});return
            slots=[]
            for slot in range(1,128):slots.append({'slot':slot,'saved':(self.server.patch_dir/f'patch{slot}.json').is_file(),'name':names.get(str(slot),'')})
            self.respond(200,{'slots':slots,'activeSlot':self.server.switch_presets.active_slot});return
        if path == '/api/v1/switch-presets':
            self.preset_command('status');return
        if path == '/api/v1/update':
            self.update_command('status');return
        if path=='/api/v1/ws' and self.headers.get('Upgrade','').lower()=='websocket':
            self.websocket();return
        if path.startswith('/api/v1/phrase/') and path.endswith('/midi'):
            self.phrase_export(path);return
        if path == '/api/v1/project/status':
            self.project_command('status');return
        if path == '/api/v1/project/capture':
            self.project_command('capture');return
        if path == '/api/v1/conductor':
            try:
                from conductor import decode as decode_conductor, resolve, mute_group_warnings
                with self.server.control.lock:
                    state=self.server.control.request()
                    patch=self.server.control.request(op=48)
                model=decode_conductor(patch['conductor']) if patch.get('conductor') else None
                self.respond(200,{'engineSessionId':state['engineSessionId'],'revision':state['revision'],'executionSupported':True,'supportedExecution':['SEQUENTIAL','IMMEDIATE','PRESS_INSTANT','PHRASE_POLY','MOVEMENT_CC','MOVEMENT_PARAMETER','LINEAR','HOLD_CURVE','ONE_SHOT','END_OF_PHRASE','GATED','LONG_HOLD','REVEAL_FADE','RELEASE','SUPERCHARGE_RELEASE','MOVEMENT_LOOP','MOVEMENT_PING_PONG','CURVE_BEND'],'runtime':{str(v['id']):v.get('conductor',{}) for v in state['switches']},'model':model,'missingReferences':resolve(model,{v['id'] for v in state['switches']}) if model else [],'muteGroupWarnings':mute_group_warnings(model) if model else []})
            except (ValueError,OSError):self.respond(503,{'error':'CONDUCTOR unavailable'})
            return
        if path == '/api/v1/descriptors':
            document=REGISTRY.document()
            # Native product identity is independent of the frozen REAPER JSFX.
            document['applicationVersion']='2.0.0'
            document['displayVersion']='V.2 DICKINSON'
            document['runtimeCapabilities']={'transformerTypes':[1,2,3,4,5,6], 'humanizer':True, 'velocityCurves':True, 'expressiveRouting':'UNIQUE_EXPLICIT_MIDI_OUT', 'echocity':False, 'nativePhrasePlayModes':[0,1,2], 'nativeHeldRelease':True,'nativeMovementPlayModes':['ONE_SHOT','GATED'],'nativeMovementCycleModes':['ONCE','LOOP','PING_PONG'],'conductorRelease':True,'supercharge':True,'nativeSmartSwitchGestures':['TAP','DOUBLE','HOLD','LONG_HOLD'],'configurableRevealCC':True,'switchPresetLibrary':True, 'phraseTransformers':False, 'snapshots':True, 'reaperSnapshots':False, 'ordering':'legacy-stages-or-serial-pitch'}
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
        if path.startswith('/assets/'):
            asset=(ROOT/path.lstrip('/')).resolve()
            types={'.css':'text/css; charset=utf-8','.png':'image/png','.webp':'image/webp','.woff2':'font/woff2','.json':'application/json; charset=utf-8'}
            try:asset.relative_to((ROOT/'assets').resolve())
            except ValueError:
                self.respond(404,{'error':'not found'});return
            if not asset.is_file() or asset.suffix not in types:
                self.respond(404,{'error':'not found'});return
            self.respond(200,asset.read_bytes(),types[asset.suffix]);return
        files = {'/': ('index.html', 'text/html; charset=utf-8'),
                 '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                 '/expressive.js': ('expressive.js', 'text/javascript; charset=utf-8'),
                 '/midi-thru.js': ('midi-thru.js', 'text/javascript; charset=utf-8'),
                 '/midi-thru.css': ('midi-thru.css', 'text/css; charset=utf-8'),
                 '/block-tools.js': ('block-tools.js', 'text/javascript; charset=utf-8'),
                 '/conductor.js': ('conductor.js', 'text/javascript; charset=utf-8'),
                 '/movement.js': ('movement.js', 'text/javascript; charset=utf-8'),
                 '/update.js': ('update.js', 'text/javascript; charset=utf-8'),
                 '/patch-recall.js': ('patch-recall.js', 'text/javascript; charset=utf-8'),
                 '/switch-presets.js': ('switch-presets.js','text/javascript; charset=utf-8'),
                 '/style.css': ('style.css', 'text/css; charset=utf-8'),
                 '/expressive.css': ('expressive.css', 'text/css; charset=utf-8'),
                 '/tiles.css': ('tiles.css','text/css; charset=utf-8'),
                 '/tiles.js': ('tiles.js','text/javascript; charset=utf-8'),
                 '/module-layout.js': ('module-layout.js','text/javascript; charset=utf-8'),
                  '/interactions.js': ('interactions.js','text/javascript; charset=utf-8'),
                 '/fonts/mbmf-block.woff2': ('fonts/mbmf-block.woff2', 'font/woff2')}
        if path not in files:
            self.respond(404, {'error': 'not found'})
            return
        name, mime = files[path]
        self.respond(200, (ROOT / name).read_bytes(), mime)

    def project_command(self, operation):
        from project_sync import Conflict
        try:
            if operation in ('capture','status'):
                result=getattr(self.server.projects,operation)()
            else:
                length=int(self.headers.get('Content-Length','0'))
                if not 0 < length <= 134217728:raise ValueError('Bounded project upload required')
                if self.headers.get('Content-Type','').split(';')[0]!='application/json':raise ValueError('JSON required')
                data=json.loads(self.rfile.read(length))
                if not isinstance(data,dict):raise ValueError('Invalid project command')
                result=getattr(self.server.projects,operation)(data)
                if operation=='activate':self.server.switch_presets.on_patch(0)
            self.respond(200,result)
        except Conflict as error:self.respond(409,{'error':str(error)})
        except (ValueError,KeyError,TypeError) as error:self.respond(422,{'error':str(error)})
        except FileNotFoundError:self.respond(404,{'error':'Staged project not found'})
        except (OSError,RuntimeError) as error:self.respond(503,{'error':str(error)})

    def phrase_export(self, path):
        try:
            phrase_id=int(path.split('/')[4])
            if not 1<=phrase_id<=128:raise ValueError('Invalid phrase')
            result=self.server.control.request(op=35,target=phrase_id-1,arg=0,revision=-1)
            if result.get('status')!='ok':raise ValueError('Finish recording before exporting MIDI')
            self.respond(200,write_smf(result['phraseData']),'audio/midi')
        except (ValueError,KeyError) as error:self.respond(422,{'error':str(error)})
        except OSError:self.respond(503,{'error':'Engine unavailable'})

    def phrase_import(self):
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=MAX_BYTES*4//3+4096:raise ValueError('Oversized MIDI upload (limit 1 MiB)')
            data=json.loads(self.rfile.read(length));phrase_id=data.get('phraseId');mode=data.get('mode')
            if type(phrase_id) is not int or not 1<=phrase_id<=128 or mode not in ('preview','replace'):
                raise ValueError('Choose a valid destination and preview or replace')
            raw=base64.b64decode(data['file'],validate=True)
            parsed=read_smf(raw)
            state=self.server.control.request()
            grid=state.get('chainMode') and state.get('chainCaptureMode','two-bar-grid')=='two-bar-grid'
            capacity=state.get('chainLength',0)/state['sampleRate'] if grid else 3600
            if parsed['lengthSeconds']>capacity or (grid and max(e[0] for e in parsed['events'])>=capacity):
                raise ValueError('File exceeds phrase capacity; replacement cancelled. Shorten the source MIDI explicitly.')
            if mode=='preview':
                self.respond(200,{k:v for k,v in parsed.items() if k!='events'});return
            revision=data.get('expectedRevision');session=data.get('expectedEngineSessionId')
            if type(revision) is not int or not 1<=revision<2147483647 or type(session) is not int or not 1<=session<=9007199254740991:
                raise ValueError('Expected revision/session required')
            result=self.server.control.request(op=35,target=phrase_id-1,arg=1,revision=revision,session=session,phrase=parsed)
            status=result.get('status')
            if status=='conflict':self.respond(409,result);return
            if status!='ok':raise ValueError('Stop playback and finish recording before replacing a phrase; check capacity')
            self.respond(200,{'status':'imported','phraseId':phrase_id,'events':len(parsed['events'])})
        except (ValueError,KeyError,TypeError) as error:self.respond(422,{'error':str(error)})
        except OSError:self.respond(503,{'error':'Engine unavailable'})

    def block_command(self):
        from block_edit import capture, paste, KINDS
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=2048:raise ValueError('Invalid block command')
            data=json.loads(self.rfile.read(length))
            action=data.get('action');kind=data.get('kind')
            if kind not in KINDS or action not in ('copy','paste'):raise ValueError('Invalid block operation')
            revision=data.get('expectedRevision');session=data.get('expectedEngineSessionId')
            if type(revision) is not int or not 1<=revision<2147483647 or type(session) is not int or not 1<=session<=9007199254740991:raise ValueError('Revision/session required')
            with self.server.patch_lock,self.server.control.lock:
                patch=self.server.control.request(op=4,arg=1,revision=revision,session=session)
                if patch.get('format')!='MIDI_HUMAN_LOOPER_PATCH':
                    self.respond(409,{'error':'STOP et relâcher les notes avant COPY / PASTE. Réessayer après la fin des échos.'});return
                context=(session,self.server.switch_presets.read()['activeSlot'])
                if action=='copy':
                    clip=capture(patch,kind,data.get('source'))
                    ident=os.urandom(12).hex()
                    self.server.block_clipboards[kind]=(ident,context,clip)
                    self.respond(200,{'clipboardId':ident,'kind':kind});return
                stored=self.server.block_clipboards.get(kind)
                if not stored or stored[0]!=data.get('clipboardId'):raise ValueError('COPY expiré ; copier à nouveau')
                if data.get('mode')=='swap' and stored[1]!=context:raise ValueError('SWAP exige le patch source actuel ; copier à nouveau')
                result,ident=paste(patch,stored[2],data.get('target'),data.get('mode','empty'))
                reply=self.server.control.request(op=5,arg=1,target=result['schema'],revision=revision,session=session,patch=result)
                if reply.get('status')!='ok':self.respond(409,reply);return
                self.respond(200,{'status':'ok','kind':kind,'id':ident})
        except (ValueError,KeyError,TypeError,StopIteration) as error:self.respond(422,{'error':str(error) or 'Block missing'})
        except (OSError,RuntimeError) as error:self.respond(503,{'error':str(error)})

    def do_POST(self):
        if not self.allowed(api=True):
            return
        if self.path=='/api/v1/midi-inputs':
            self.midi_inputs_command();return
        if self.path == '/api/v1/zynthian/chains':
            self.host_chain_command();return
        if self.path == '/api/v1/patch-recall':
            self.host_chain_command(recall=True);return
        if self.path == '/api/v1/switch-presets':
            self.preset_command();return
        if self.path == '/api/v1/update':
            self.update_command();return
        if self.path in ('/api/v1/project/stage','/api/v1/project/activate','/api/v1/project/checkpoint'):
            self.project_command(self.path.rsplit('/',1)[-1]);return
        if self.path == '/api/v1/phrase/midi':
            self.phrase_import();return
        if self.path == '/api/v1/blocks':
            self.block_command();return
        if self.path in ('/api/v1/patch/save','/api/v1/patch/load','/api/v1/patch/export','/api/v1/patch/copy','/api/v1/patch/paste','/api/v1/patch/rename'):
            self.patch_command();return
        if self.path != '/api/v1/command':
            self.respond(404, {'error': 'not found'})
            return
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            self.respond(415, {'error': 'JSON required'})
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if length < 1 or length > 16000000:
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
            if action=='switch_delete':
                from switch_edit import remove_switch
                with self.server.patch_lock,self.server.control.lock:
                    patch=self.server.control.request(op=4,arg=1,revision=revision,session=session)
                    if patch.get('format')!='MIDI_HUMAN_LOOPER_PATCH':self.respond(409,{'error':'Stop MBMF and release keys before deleting a switch.'});return
                    patch=remove_switch(patch,data.get('switchId'))
                    result=self.server.control.request(op=5,arg=1,target=patch['schema'],revision=revision,session=session,patch=patch)
                if result.get('status')=='ok':self.engine();return
                self.respond(409,result);return
            if length>2048 and action not in ('snapshot_commit','conductor_commit'):
                self.respond(413,{'error':'command size limit'});return
            if action=='conductor_commit':
                from conductor import encode
                extension=encode(data.get('conductor'))
                with self.server.control.lock:
                    patch=self.server.control.request(op=4,arg=1,revision=revision,session=session)
                    if patch.get('format')!='MIDI_HUMAN_LOOPER_PATCH':
                        self.respond(409,patch);return
                    patch['conductor']=extension
                    result=self.server.control.request(op=5,target=patch['schema'],arg=1,revision=revision,session=session,patch=patch)
                self.respond(200 if result.get('status')=='ok' else 409,result);return
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
            elif action in ('movement_preview','movement_stop','movement_release'):
                from conductor import identity, decode as decode_conductor
                ident=identity(data.get('movementId'))
                with self.server.control.lock:
                    patch=self.server.control.request(op=48)
                    model=decode_conductor(patch['conductor']) if patch.get('conductor') else {}
                    items=model.get('movements',[])
                    index=next((i for i,m in enumerate(items) if m['id']==ident),None)
                    if index is None:raise ValueError('Missing MOVEMENT source')
                    result=self.server.control.request(op=46 if action=='movement_preview' else 47,target=index,arg=int(action=='movement_release'),revision=revision,session=session)
                self.respond(200 if result.get('status')=='ok' else 409,result);return
            elif action=='conductor_release':
                target=data.get('switchId')
                if type(target) is not int or not 1<=target<=16777215:raise ValueError()
                args=dict(op=45,target=target)
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
            elif action=='switch_add':
                from switch_model import add_switch
                with self.server.control.lock:
                    patch=self.server.control.request(op=4,arg=1,revision=revision,session=session)
                    if patch.get('format')!='MIDI_HUMAN_LOOPER_PATCH':
                        self.respond(409,patch);return
                    patch,identity=add_switch(patch)
                    result=self.server.control.request(op=5,arg=1,target=patch['schema'],revision=revision,session=session,patch=patch)
                if result.get('status')=='ok':result['switchId']=identity
                self.respond(200 if result.get('status')=='ok' else 409,result);return
            elif action=='switch_commit':
                target=data.get('switchId');settings=data.get('settings');sequence=data.get('sequence');name=data.get('name','')
                if type(target) is not int or not 1<=target<=16777215 or not isinstance(settings,list) or len(settings)!=18 or any(type(v) is not int for v in settings) or not isinstance(sequence,list) or len(sequence)>64 or any(type(v) is not int or not 1<=v<=128 for v in sequence) or not isinstance(name,str) or len(name)>16 or any(not 32<=ord(c)<127 for c in name):raise ValueError()
                settings=list(settings);settings[11]=len(sequence)
                args=dict(op=41,target=target,settings=settings+[p-1 for p in sequence]+[0]*(64-len(sequence))+[ord(c) for c in name]+[0]*(16-len(name)))
                if 'longHold' in data:
                    lh=data['longHold']
                    if not isinstance(lh,dict) or set(lh)!={'milliseconds','action','target'} or any(type(v) is not int for v in lh.values()) or not (lh['milliseconds']==0 or settings[8]<lh['milliseconds']<=30000) or not 0<=lh['action']<=9 or not 0<=lh['target']<=64:raise ValueError('LONG HOLD must exceed HOLD')
                    args['settings'] += [lh['milliseconds'],lh['action'],lh['target']]

            elif action in ('switch_learn','switch_learn_cancel'):
                target=data.get('switchId')
                if type(target) is not int or not 1<=target<=16777215:raise ValueError('Invalid switch')
                args=dict(op=50,target=target,arg=int(action=='switch_learn_cancel'))
            elif action=='switch_test_edge':
                target,edge=data.get('switchId'),data.get('edge')
                if type(target) is not int or not 1<=target<=16777215 or edge not in ('press','release'):raise ValueError('invalid test edge')
                args=dict(op=1,target=target,arg=3 if edge=='press' else 4)
            elif action == 'test':
                target, gesture = data.get('switchId'), data.get('gesture', 'tap')
                if type(target) is not int or not 1 <= target <= 16777215 or gesture not in ('tap', 'double', 'hold','long_hold'):
                    raise ValueError('invalid switch or gesture')
                args = dict(op=1, target=target, arg=5 if gesture=='long_hold' else ('tap', 'double', 'hold').index(gesture))
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
            elif action=='controller_remove':
                target=data.get('sourceId')
                if type(target) is not int or not 1<=target<=16777215:raise ValueError()
                args=dict(op=37,target=target,name='',arg=2)
            elif action=='controller_rename':
                target=data.get('sourceId');name=data.get('name')
                if type(target) is not int or not 1<=target<=16777215 or not isinstance(name,str) or not 1<=len(name)<=16 or any(not 32<=ord(c)<127 for c in name):raise ValueError('Controller name: 1–16 printable ASCII characters')
                args=dict(op=37,target=target,name=name,arg=int(data.get('create') is True))
            elif action=='curve_preset_store':
                slot=data.get('slot')
                if type(slot) is not int or not 0<=slot<4:raise ValueError()
                binding=binding_wire(dict(id=1,sourceId=1,targetId=1,instrumentId=1,points=data.get('points')))
                args=dict(op=39,target=slot,binding=binding)
            elif action=='mapping_commit':
                binding=binding_wire(data.get('mapping'));args=dict(op=16,target=binding[0],binding=binding,arg=int(data.get('replaceLegacy') is True))
            elif action=='controller_test':
                target,value=data.get('sourceId'),data.get('value')
                if type(target) is not int or not 1<=target<=16777215 or type(value) is not int or not 0<=value<=127:raise ValueError()
                args=dict(op=43,target=target,value=value)
            elif action=='midi_cc':
                channel,number,value=data.get('channel'),data.get('number'),data.get('value')
                if any(type(v) is not int for v in (channel,number,value)) or not 1<=channel<=16 or not 0<=number<=127 or not 0<=value<=127:raise ValueError()
                args=dict(op=19,ch=channel-1,note=number,value=value)
            elif action=='instance_stop':
                id,generation=data.get('instanceId'),data.get('generation')
                if any(type(v) is not int or not 1<=v<=9007199254740991 for v in (id,generation)):raise ValueError()
                args=dict(op=44,instance=(id,generation))
            elif action=='phrase_play_independent':
                target=data.get('phraseId')
                if type(target) is not int or not 1<=target<=128:raise ValueError()
                args=dict(op=40,target=target-1,arg=7)
            elif action=='phrase_stop':
                target=data.get('phraseId')
                if type(target) is not int or not 1<=target<=128:raise ValueError()
                args=dict(op=40,target=target-1,arg=6)
            elif action == 'chain_stop':
                args=dict(op=40,target=0,arg=0)
            elif action=='patch_clear':
                if data.get('confirm') is not True:raise ValueError()
                args=dict(op=42)
            elif action == 'panic':
                args = dict(op=2)
            elif action in ('phrase_rename','instrument_rename'):
                target=data.get('phraseId' if action=='phrase_rename' else 'instrumentId');name=data.get('name')
                if type(target) is not int or not 1<=target<=(128 if action=='phrase_rename' else 16777215) or not isinstance(name,str) or len(name)>16 or any(not 32<=ord(c)<127 for c in name):raise ValueError('Names support up to 16 printable ASCII characters, matching REAPER')
                args=dict(op=36,target=target,arg=int(action=='instrument_rename'),name=name)
            elif action in ('parameter_curve','parameter_unassign'):
                target,module,kind=data.get('targetId'),data.get('moduleId',0),data.get('kind')
                if any(type(v) is not int for v in (target,module,kind)) or not 1<=target<=16777215 or not 0<=module<=16777215 or not 0<=kind<14:raise ValueError()
                args=dict(op=38,target=target,arg=kind,macro=[module,int(action=='parameter_unassign')])
            elif action=='parameter_set':
                target,module,kind,value=data.get('targetId'),data.get('moduleId',0),data.get('kind'),data.get('value')
                if any(type(v) is not int for v in (target,module,kind)) or not 1<=target<=16777215 or not 0<=module<=16777215 or kind in (16,27) or type(value) not in (int,float) or not math.isfinite(value):raise ValueError()
                p=next((p for p in REGISTRY.parameters.values() if p['engineKind']==kind),None)
                if not p or not p['min']<=value<=p['max'] or (kind!=14 and abs(value/p['step']-round(value/p['step']))>1e-6):raise ValueError()
                args=dict(op=32,target=target,arg=kind,macro=[module,value])
            elif action=='echocity_commit':
                from echocity_config import decode as decode_echo
                extension=data.get('echocity');decode_echo(extension)
                args=dict(op=54,echo=extension)
            elif action=='expressive_commit':
                from native_expressive_config import decode as decode_expressive
                extension=data.get('expressive');rows=decode_expressive(extension)
                args=dict(op=55,expressive=extension['configuration'])
            elif action=='midi_thru_commit':
                from midi_thru_config import decode as decode_midi_thru
                extension=data.get('midiThru');decode_midi_thru(extension)
                args=dict(op=56,midi_thru=extension['configuration'])
            elif action=='module_structure':
                target=data.get('instrumentId');module=data.get('moduleId',0);op=data.get('operation');type_=data.get('engineType',0)
                if any(type(v) is not int or not 0<=v<=16777215 for v in (target,module,type_)) or not target or op not in ('add','delete','bypass','up','down'):raise ValueError()
                if op=='add' and type_ not in REGISTRY.engine_types:raise ValueError()
                args=dict(op=13,target=target,module=module,arg=('add','delete','bypass','up','down').index(op)+1,note=type_)
            elif action in ('phrase_learn','phrase_learn_cancel','phrase_forget','phrase_learn_confirm'):
                target=data.get('phraseId')
                if type(target) is not int or not 1<=target<=128:raise ValueError()
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
                if any(type(v) is not int or not 1<=v<=16777215 for v in (target,module)) or not isinstance(parameters,list) or not 1<=len(parameters)<=5:raise ValueError()
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
            elif action=='phrase_output':
                target=data.get('phraseId');channel=data.get('channel')
                if type(target) is not int or not 1<=target<=128 or type(channel) is not int or not 0<=channel<=17:raise ValueError('invalid phrase output channel')
                args=dict(op=49,target=target-1,value=channel)
            elif action=='phrase_cancel':
                target=data.get('phraseId')
                if type(target) is not int or not 1<=target<=128:raise ValueError()
                args=dict(op=40,target=target-1,arg=5)
            elif action in ('phrase_play','phrase_record','phrase_finish','phrase_clear','phrase_release','phrase_cancel'):
                target=data.get('phraseId')
                if type(target) is not int or not 1<=target<=128:raise ValueError('invalid phrase')
                args=dict(op=40,target=target-1,arg=4) if action=='phrase_release' else dict(op=35,target=target-1,arg=2) if action=='phrase_clear' else dict(op={'phrase_play':6,'phrase_record':7,'phrase_finish':8}[action],target=target-1)
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
        # Host-linked output channels have one authority. Reject competing
        # manual edits instead of accepting them and silently overwriting later.
        output_edit = (action == 'instrument_commit' or
                       action == 'parameter_set' and data.get('kind') == 23 or
                       action == 'instrument_route' and data.get('field') == 'output')
        if output_edit and getattr(self.server, 'host_chain_socket', None):
            try:
                from zynthian_chains import bridge_request
                host = bridge_request(self.server.host_chain_socket, {'action': 'status'})
                target = data.get('targetId') if action == 'parameter_set' else data.get('instrumentId')
                binding = host.get('bindings', {}).get(str(target))
                desired = data.get('output') if action == 'instrument_commit' else data.get('value')
                if binding:
                    destination = binding.get('destination')
                    if not destination or desired != destination.get('channel'):
                        self.respond(409, {'error': 'Output follows the linked Zynthian chain. Unlink this instrument before choosing a manual MIDI output.'})
                        return
            except (OSError, ValueError, KeyError, TypeError):
                self.respond(503, {'error': 'Cannot verify Zynthian output link; retry when the host connection is available.'})
                return
        self.engine(revision=revision, session=session, **args)

    def preset_command(self,operation=None):
        try:
            if operation=='status':
                result=self.server.switch_presets.inventory();state=self.server.control.request();result.update(expectedRevision=state['revision'],expectedEngineSessionId=state['engineSessionId']);self.respond(200,result);return
            if self.headers.get('Content-Type','').split(';')[0]!='application/json':raise ValueError('JSON required')
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=32768:raise ValueError('Bounded preset command required')
            data=json.loads(self.rfile.read(size))
            result=self.server.switch_presets.execute(data.get('previewId')) if data.get('action')=='execute' else self.server.switch_presets.preview(data) if data.get('action')=='preview' else None
            if result is None:raise ValueError('Preview or execute required')
            self.respond(200,result)
        except (ValueError,KeyError,TypeError) as error:self.respond(409,{'error':str(error)})
        except OSError as error:self.respond(503,{'error':str(error)})

    def patch_command(self):
        from patch_lock import library_lock
        try:
            with library_lock(self.server.patch_dir),self.server.patch_lock,self.server.control.lock:self._patch_command_locked()
        except ValueError as error:self.respond(409,{'error':str(error)})

    def _patch_command_locked(self):
        try:
            n=int(self.headers.get('Content-Length','0'))
            if not 0<n<=2048:raise ValueError()
            data=json.loads(self.rfile.read(n));slot=data.get('slot');rev=data.get('expectedRevision');session=data.get('expectedEngineSessionId')
            if type(session) is not int or not 1<=session<=9007199254740991:raise ValueError()
            if type(slot) is not int or not 1<=slot<=127 or type(rev) is not int or not 1<=rev<2147483647:raise ValueError()
            path=self.server.patch_dir/f'patch{slot}.json'
            if self.path.endswith('/rename'):
                from patch_names import rename
                with self.server.patch_lock:name=rename(self.server.patch_dir,slot,data.get('name'),data.get('expectedName'))
                self.respond(200,{'status':'renamed','slot':slot,'name':name});return
            if self.path.endswith('/copy'):
                patch=self.server.control.request(op=4,arg=1,revision=rev,session=session)
                if patch.get('format')!='MIDI_HUMAN_LOOPER_PATCH':self.respond(409,{'error':'Stop MBMF before copying the patch.'});return
                ident=os.urandom(12).hex();self.server.patch_clipboard=(ident,patch)
                self.respond(200,{'status':'copied','clipboardId':ident});return
            if self.path.endswith('/paste'):
                saved=getattr(self.server,'patch_clipboard',None)
                if not saved or data.get('clipboardId')!=saved[0]:self.respond(409,{'error':'COPY PATCH first; clipboard changed or expired.'});return
                patch=saved[1];result=self.server.control.request(op=5,target=patch['schema'],revision=rev,session=session,patch=patch)
                if result.get('status')!='ok':self.respond(409,result);return
                self.server.switch_presets.on_patch(slot);self.engine();return
            if self.path.endswith('/load') and not path.exists():
                result=self.server.control.request(op=42,revision=rev,session=session)
                if result.get('status')!='ok':self.respond(409,result);return
                self.server.switch_presets.on_patch(slot);result=self.server.control.request();result['emptySlot']=True;self.respond(200,result);return
            if self.path.endswith('/load') and getattr(self.server,'host_chain_socket',None):
                from zynthian_chains import bridge_request
                state=self.server.control.request()
                if state['revision']!=rev or state['engineSessionId']!=session:
                    self.respond(409,{'error':'conflict'});return
                result=bridge_request(self.server.host_chain_socket,dict(action='patch_recall',operation='recall',slot=slot))
                if 'error' in result:self.respond(409,result);return
                self.respond(202,{'status':'queued','recall':result});return
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
                    if patch['schema']==8:
                        self.respond(422,{'error':'Native schema 8 cannot be exported to frozen REAPER; original preserved.'});return
                    if 'conductor' in patch:
                        self.respond(422,{'error':'REAPER cannot execute CONDUCTOR yet; export refused, original preserved.'});return
                    snapshots=patch.get('globalSnapshots',{}).get('configuration',[])
                    if len(snapshots)>=4 and snapshots[3]:
                        self.respond(422,{'error':'REAPER cannot yet execute Global Snapshots; export refused to preserve snapshot data.'});return
                    patch.pop('globalSnapshots',None)
                    patch.pop('controllerEngine',None)
                    path=self.server.patch_dir/f'patch{slot}-reaper.json'
                self.server.patch_dir.mkdir(parents=True,exist_ok=True)
                # Serialize patch writes independently from command execution.
                with self.server.patch_lock:
                    from project_sync import atomic_json
                    atomic_json(path,patch)
                if self.path.endswith('/save'):self.server.switch_presets.on_patch(slot)
                self.respond(200,{'status':'saved','slot':slot,'file':path.name})
            else:
                if path.stat().st_size>134217728:raise ValueError()
                patch=json.loads(path.read_text())
                try:validate_patch_extensions(patch)
                except ValueError as error:
                    self.respond(422,{'error':str(error)});return
                patch=self.server.switch_presets.materialize(patch,slot)
                schema=patch.get('schema');memory=patch.get('memory');globals_=patch.get('globals')
                if patch.get('format')!='MIDI_HUMAN_LOOPER_PATCH' or type(schema) is not int or not 1<=schema<=8 or not isinstance(memory,list) or patch.get('work_mem_size')!=len(memory) or not 0<len(memory)<=2000000 or not isinstance(globals_,list) or len(globals_)!=9:raise ValueError()
                if any(type(x) not in (int,float) or not math.isfinite(x) for x in globals_+memory):raise ValueError()
                result=self.server.control.request(op=5,target=schema,revision=rev,session=session,patch=patch)
                if result.get('status')!='ok':self.respond(409 if result.get('status')=='conflict' else 400,result);return
                self.server.switch_presets.on_patch(slot)
                self.engine()
        except FileNotFoundError:
            self.respond(404,{'error':'patch not saved'})
        except (ValueError,TypeError,AttributeError):
            self.respond(400,{'error':'invalid patch'})
        except OSError:
            self.respond(503,{'error':'patch I/O or engine unavailable'})


    def midi_inputs_command(self,read_only=False):
        service=getattr(self.server,'midi_inputs',None)
        if service is None:
            if read_only:
                self.respond(200,{'available':False,'enabled':False,'inputs':[],
                                 'reason':'Les entrées MIDI physiques sont disponibles avec le bridge Zynthian.'})
            else:self.respond(503,{'error':'MIDI THRU physique disponible avec le bridge Zynthian'})
            return
        try:
            with self.server.patch_lock:
                if read_only:result=service.status()
                else:
                    length=int(self.headers.get('Content-Length','0'))
                    if not 0<length<=8192 or self.headers.get('Content-Type','').split(';')[0]!='application/json':
                        raise ValueError('Bounded JSON request required')
                    request=json.loads(self.rfile.read(length))
                    if not isinstance(request,dict):raise ValueError('JSON object required')
                    result=service.update_source(request)
                result['activeSlot']=self.server.switch_presets.read()['activeSlot']
            self.respond(200,result)
        except (ValueError,TypeError,KeyError) as error:self.respond(422,{'error':str(error)})
        except OSError:self.respond(503,{'error':'Physical MIDI input registry unavailable'})

    def host_chain_command(self, read_only=False, recall=False):
        path = getattr(self.server, 'host_chain_socket', None)
        if path is None:
            self.respond(503, {'error': 'Zynthian chain links unavailable'});return
        try:
            from zynthian_chains import bridge_request
            request = {'action': 'patch_recall','operation':'status'} if recall else {'action': 'status'}
            if not read_only:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 4096 or self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                    raise ValueError('Bounded JSON request required')
                request = json.loads(self.rfile.read(length))
                if not isinstance(request, dict):raise ValueError('JSON object required')
            result = bridge_request(path, request)
            self.respond(409 if 'error' in result else 200, result)
        except (ValueError, TypeError, KeyError) as error:self.respond(422, {'error': str(error)})
        except OSError:self.respond(503, {'error': 'Zynthian chain links unavailable'})


def make_server(bind, port, path, token='',patch_dir=None,host_chain_socket=None,midi_input_registry=None):
    if bind not in ('127.0.0.1', 'localhost') and not token:
        raise ValueError('explicit token required for LAN binding')
    server = ThreadingHTTPServer((bind, port), Handler)
    server.bind_address, server.token, server.control = bind, token, Control(path)
    server.patch_dir=Path(patch_dir) if patch_dir else Path.home()/'.local/share/midi-human-looper'
    server.patch_lock=threading.RLock()
    server.block_clipboards={}
    server.host_chain_socket=host_chain_socket
    server.midi_inputs=None
    if midi_input_registry is not None and host_chain_socket is not None:
        from midi_thru_service import Service
        from zynthian_chains import bridge_request
        config=Path(midi_input_registry).with_name('install.json')
        legacy=json.loads(config.read_text(encoding='utf-8')).get('exclusive_midi_input_ports',[]) if config.exists() else []
        def refresh_inputs():
            result=bridge_request(host_chain_socket,{'action':'refresh_midi_inputs'})
            if 'error' in result:raise ValueError(result['error'])
        server.midi_inputs=Service(midi_input_registry,server.control,refresh_inputs,legacy)
    from project_sync import ProjectStore
    server.projects=ProjectStore(server.patch_dir,server.control)
    from switch_presets import Store
    server.switch_presets=Store(server.patch_dir,server.control,server.patch_lock);server.switch_presets.recover()
    server.daemon_threads=True
    return server

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--socket', required=True)
    parser.add_argument('--bind', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--token-file', type=Path)
    parser.add_argument('--patch-dir',type=Path)
    parser.add_argument('--host-chain-socket',type=Path)
    parser.add_argument('--midi-input-registry',type=Path)
    parser.add_argument('--restore-active-project',action='store_true',help='Restore committed portable project on fresh engine startup')
    args = parser.parse_args()
    token = args.token_file.read_text().strip() if args.token_file else ''
    server = make_server(args.bind, args.port, args.socket, token,args.patch_dir,args.host_chain_socket,args.midi_input_registry)
    if args.restore_active_project:server.projects.restore()
    print(f'EDITOR http://{args.bind}:{server.server_port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()  # Engine is a separate process and remains running.
