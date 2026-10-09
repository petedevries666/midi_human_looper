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
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).parent / 'web'

class Control:
    def __init__(self, path):
        self.path = path
        self.lock = threading.Lock()
        self.ids = itertools.count(1)

    def request(self, op=0, target=0, arg=0, revision=1, ch=0, note=0, value=0, session=0, patch=None):
        # One worker producer owns the engine's command queue; HTTP threads never
        # inspect live engine state. A timeout does not cancel an already executed TEST.
        with self.lock:
            request_id = next(self.ids)
            line = f'{request_id} {op} {target} {arg} {revision} {ch} {note} {value}\n'
            if session:line=line.rstrip('\n')+f' session {session}\n'
            if patch is not None:
                line = line.rstrip('\n') + ' ' + ' '.join(format(v, '.17g') for v in patch['globals']+patch['memory'])+'\n'
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
                prefix=bytes([0x81,len(payload)]) if len(payload)<126 else bytes([0x81,126])+struct.pack('!H',len(payload))
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
        if self.path in ('/api/v1/patch/save','/api/v1/patch/load'):
            self.patch_command();return
        if self.path != '/api/v1/command':
            self.respond(404, {'error': 'not found'})
            return
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            self.respond(415, {'error': 'JSON required'})
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if length < 1 or length > 2048:
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
            if action == 'test':
                target, gesture = data.get('switchId'), data.get('gesture', 'tap')
                if type(target) is not int or not 1 <= target <= 16777215 or gesture not in ('tap', 'double', 'hold'):
                    raise ValueError('invalid switch or gesture')
                args = dict(op=1, target=target, arg=('tap', 'double', 'hold').index(gesture))
            elif action == 'panic':
                args = dict(op=2)
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
            if type(slot) is not int or slot not in (1,2) or type(rev) is not int or not 1<=rev<2147483647:raise ValueError()
            path=self.server.patch_dir/f'patch{slot}.json'
            if self.path.endswith('/save'):
                patch=self.server.control.request(op=4,revision=rev,session=session)
                if patch.get('status')=='conflict':self.respond(409,patch);return
                if patch.get('format')!='MIDI_HUMAN_LOOPER_PATCH':raise ValueError()
                self.server.patch_dir.mkdir(parents=True,exist_ok=True)
                temp=path.with_suffix('.tmp')
                # Serialize patch writes independently from command execution.
                with self.server.patch_lock:
                    with temp.open('w') as f:
                        json.dump(patch,f,allow_nan=False,separators=(',',':'));f.flush();os.fsync(f.fileno())
                    temp.replace(path)
                self.respond(200,{'status':'saved','slot':slot})
            else:
                if path.stat().st_size>16000000:raise ValueError()
                patch=json.loads(path.read_text())
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
