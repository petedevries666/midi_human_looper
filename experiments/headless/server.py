#!/usr/bin/env python3
"""M0 control worker: no scheduling, MIDI clock, or direct access to EEL memory."""
import argparse
import hmac
import ipaddress
import itertools
import json
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

    def request(self, op=0, target=0, arg=0, revision=1, ch=0, note=0, value=0):
        # One worker producer owns the engine's command queue; HTTP threads never
        # inspect live engine state. A timeout does not cancel an already executed TEST.
        with self.lock:
            request_id = next(self.ids)
            line = f'{request_id} {op} {target} {arg} {revision} {ch} {note} {value}\n'
            with socket.socket(socket.AF_UNIX) as client:
                client.settimeout(3)
                client.connect(self.path)
                client.sendall(line.encode('ascii'))
                data = bytearray()
                while b'\n' not in data:
                    chunk = client.recv(4096)
                    if not chunk:
                        raise ConnectionError('engine disconnected')
                    data.extend(chunk)
                    if len(data) > 65536:
                        raise ValueError('oversized engine response')
            return json.loads(data)

class Handler(BaseHTTPRequestHandler):
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
        if not self.allowed(api=path.startswith('/api/')):
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
            action = data.get('action')
            if action == 'test':
                target, gesture = data.get('switchId'), data.get('gesture', 'tap')
                if type(target) is not int or not 1 <= target <= 16777215 or gesture not in ('tap', 'double', 'hold'):
                    raise ValueError('invalid switch or gesture')
                args = dict(op=1, target=target, arg=('tap', 'double', 'hold').index(gesture))
            elif action == 'panic':
                args = dict(op=2)
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
        self.engine(revision=revision, **args)


def make_server(bind, port, path, token=''):
    if bind not in ('127.0.0.1', 'localhost') and not token:
        raise ValueError('explicit token required for LAN binding')
    server = ThreadingHTTPServer((bind, port), Handler)
    server.bind_address, server.token, server.control = bind, token, Control(path)
    return server

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--socket', required=True)
    parser.add_argument('--bind', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--token-file', type=Path)
    args = parser.parse_args()
    token = args.token_file.read_text().strip() if args.token_file else ''
    server = make_server(args.bind, args.port, args.socket, token)
    print(f'EDITOR http://{args.bind}:{server.server_port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()  # Engine is a separate process and remains running.
