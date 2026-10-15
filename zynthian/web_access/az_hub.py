"""AZ launcher in Webconf, never in the MIDI callback or a new HTTP service."""
import asyncio
import json
import os
import hmac
import secrets
import re
import socket
import subprocess
import time
from pathlib import Path
from urllib.parse import urlsplit
import tornado.httpclient
import tornado.web
import tornado.websocket
from mbmf_web_entry import ticks
from az_lumaz import Settings
from mbmf_web_policy import local_address

HERE = Path(__file__).parent
UNIT = 'video-jack-trigger.service'

def systemctl(*args):
    return subprocess.run(['/bin/systemctl', *args], capture_output=True, text=True, timeout=4, check=False)

def mpv(command, path='/tmp/mpvsocket'):
    """Bounded request/reply; a socket existing is not evidence of a working player."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(1)
        client.connect(path)
        client.sendall((json.dumps({'command': command, 'request_id': 917})+'\n').encode())
        data=b'';received=0;deadline=time.monotonic()+1
        while received<65536:
            remaining=deadline-time.monotonic()
            if remaining<=0:raise TimeoutError('MPV acknowledgement deadline exceeded')
            client.settimeout(remaining)
            chunk=client.recv(4096)
            if not chunk:break
            data+=chunk;received+=len(chunk)
            while b'\n' in data:
                line,data=data.split(b'\n',1)
                result=json.loads(line)
                if result.get('request_id')==917:
                    if result.get('error')!='success':raise ValueError('MPV rejected command')
                    return result.get('data')
    raise ValueError('MPV did not acknowledge command')

class Operations:
    def lumaz_status(self):
        try:
            active=systemctl('is-active',UNIT).stdout.strip()=='active'
            mpv(['get_property','idle-active'])
            return {'online':active,'detail':'Service + HDMI player checked' if active else 'Video trigger service inactive'}
        except (OSError,ValueError,subprocess.SubprocessError):
            return {'online':False,'detail':'LUMAZ service / MPV unavailable'}

    def restart(self):
        definition=systemctl('show',UNIT,'--property=ExecStart','--value')
        if definition.returncode or not re.search(r'path=/usr/bin/python3\s*;\s*argv\[\]=/usr/bin/python3 /root/video_jack_trigger.py\s*;',definition.stdout):
            raise ValueError('Audited LUMAZ video trigger service not installed')
        if systemctl('is-active','jack2.service').stdout.strip()!='active':
            raise ValueError('JACK must already be active; it was not started')
        result=systemctl('restart',UNIT)
        if result.returncode or systemctl('is-active',UNIT).stdout.strip()!='active':
            raise ValueError('LUMAZ video trigger restart failed')
        return 'Video trigger restarted. JACK, audio, Zynthian UI and MBMF were not restarted.'
    def settings(self):
        return Settings(mpv).read()
    async def execute(self,body):
        action=body.get('action')
        if action=='restart':
            if set(body)!={'action','confirmed'} or body['confirmed'] is not True:raise ValueError('Confirmation required')
            return await asyncio.to_thread(self.restart)
        if action=='settings':return await asyncio.to_thread(Settings(mpv).write,body)
        if action=='hdmi':
            if set(body)!={'action','confirmed'} or body['confirmed'] is not True:raise ValueError('Confirmation required')
            source='av://lavfi:testsrc2=size=1024x768:rate=25:duration=5'
            pause=await asyncio.to_thread(mpv,['get_property','pause'])
            loop=await asyncio.to_thread(mpv,['get_property','loop-file'])
            await asyncio.to_thread(mpv,['loadfile',source])
            try:
                await asyncio.to_thread(mpv,['set_property','loop-file','no'])
                await asyncio.to_thread(mpv,['set_property','pause',False])
                await asyncio.sleep(5)
            finally:
                current=await asyncio.to_thread(mpv,['get_property','path'])
                if current==source:
                    await asyncio.to_thread(mpv,['stop'])
                    await asyncio.to_thread(mpv,['set_property','pause',pause])
                    await asyncio.to_thread(mpv,['set_property','loop-file',loop])
            return 'HDMI test complete; previous video was not resumed'
        raise ValueError('Unsupported action')

class Discovery:
    def __init__(self,resolver,operations=None,webconf_port=80,vnc_port=6080):
        self.resolver=resolver;self.operations=operations or Operations()
        self.webconf_port=webconf_port;self.vnc_port=vnc_port
        self.client=tornado.httpclient.AsyncHTTPClient(force_instance=True,max_body_size=1024*1024)
        self.cached=None;self.cached_host=None;self.cached_at=0;self.lock=asyncio.Lock();self.action_lock=asyncio.Lock()
    async def http(self,url,headers=None):
        return await self.client.fetch(url,headers=headers or {},
            request_timeout=2,connect_timeout=1,follow_redirects=False )
    async def webconf(self,host):
        try:
            response=await self.http(f'http://{host}:{self.webconf_port}/login',{'Host':'zynthian.local'})
            if response.code!=200 or b'zynthian' not in response.body.lower():raise ValueError('Not a Zynthian login page')
            return {'online':True,'detail':'Webconf HTTP checked'}
        except (OSError,ValueError,tornado.httpclient.HTTPError):
            return {'online':False,'detail':'Webconf /login unavailable; check binding and service'}
    async def vnc(self,host):
        ws=None
        try:
            response=await self.http(f'http://{host}:{self.vnc_port}/vnc.html')
            if b'novnc' not in response.body.lower():raise ValueError('Not a noVNC page')
            request=tornado.httpclient.HTTPRequest(f'ws://{host}:{self.vnc_port}/websockify',connect_timeout=1,request_timeout=2)
            ws=await asyncio.wait_for(tornado.websocket.websocket_connect(request,subprotocols=['binary']),2)
            greeting=await asyncio.wait_for(ws.read_message(),2)
            if not isinstance(greeting,bytes) or not greeting.startswith(b'RFB '):raise ValueError('No VNC protocol greeting')
            return {'online':True,'detail':'noVNC page + RFB greeting checked'}
        except (OSError,ValueError,asyncio.TimeoutError,tornado.httpclient.HTTPError,tornado.websocket.WebSocketError):
            return {'online':False,'detail':'Remote Screen unavailable; check novnc0 and vncserver0'}
        finally:
            if ws:ws.close()
    async def mbmf(self):
        checked=[]
        try:entries=await asyncio.to_thread(self.resolver.entries)
        except (OSError,ValueError,KeyError):entries=[]
        for entry in entries:
            try:
                response=await self.http(f'http://127.0.0.1:{entry["port"]}/api/v1/state',{'X-Engine-Token':entry['token']})
                state=json.loads(response.body)
                if 'engineSessionId' not in state or ticks(entry['pid'])!=entry['ticks']:continue
                checked.append({'processor':entry['processor'],'port':entry['port']})
            except (OSError,ValueError,tornado.httpclient.HTTPError):pass
        return {'online':bool(checked),'instances':checked,
                'detail':'Select an active editor' if len(checked)>1 else 'Editor + native engine checked' if checked else 'Load an MBMF MIDI Tool chain'}
    async def status(self,host):
        async with self.lock:
            if self.cached and self.cached_host==host and time.monotonic()-self.cached_at<3:return self.cached
            mbmf,webconf,vnc,lumaz=await asyncio.gather(self.mbmf(),self.webconf(host),self.vnc(host),asyncio.to_thread(self.operations.lumaz_status))
            self.cached={'mbmf':mbmf,'webconf':webconf,'remote':vnc,'lumaz':lumaz,'checkedAt':time.time()}
            self.cached_host=host;self.cached_at=time.monotonic()
            return self.cached

class Hub(tornado.web.RequestHandler):
    def initialize(self,discovery):self.discovery=discovery
    def prepare(self):
        if not self.discovery.resolver.config().get('hub',False):raise tornado.web.HTTPError(404,'AZ is disabled')
        try:host=urlsplit('http://'+self.request.host).hostname or ''
        except ValueError:raise tornado.web.HTTPError(403)
        peer=getattr(getattr(self.request.connection,'context',None),'address',None)
        if not local_address(self.request.remote_ip) or (peer and not local_address(peer[0])):
            raise tornado.web.HTTPError(403,'Private network only')
        if host not in ('az.local','mbmf.local','zynthian.local') and not local_address(host):raise tornado.web.HTTPError(403)
        if host=='mbmf.local':raise tornado.web.HTTPError(404)
        origin=self.request.headers.get('Origin')
        if origin and origin!=self.request.protocol+'://'+self.request.host:raise tornado.web.HTTPError(403,'Same origin required')
        self.interface_address=self.host_address()
        self.set_header('Cache-Control','no-store')
        self.set_header('X-Content-Type-Options','nosniff')
        self.set_header('Referrer-Policy','same-origin')
        self.set_header('Content-Security-Policy',"default-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
    def prefix(self):return '/az'
    def host_address(self):
        # The actual interface reached by this request, not a guessed primary IP
        # or a DNS name that may fail on hotspot clients.
        connection=self.request.connection
        stream=getattr(connection,'stream',None)
        address=stream.socket.getsockname()[0] if stream and stream.socket else None
        if not address or not local_address(address):raise tornado.web.HTTPError(503,'No private interface available')
        return '['+address+']' if ':' in address else address
    async def get(self,path=''):
        if path in ('','/'):
            self.set_header('Content-Type','text/html; charset=utf-8');self.finish((HERE/'az-index.html').read_bytes());return
        if path in ('az-style.css','az-app.js'):
            self.set_header('Content-Type','text/css' if path.endswith('.css') else 'text/javascript')
            self.finish((HERE/path).read_bytes());return
        if path=='api/options':
            if self.get_secure_cookie('user')!=b'root':raise tornado.web.HTTPError(401)
            try:self.finish(await asyncio.to_thread(self.discovery.operations.settings))
            except (OSError,ValueError) as error:self.set_status(503);self.finish({'error':str(error)})
            return
        if path=='api/status':
            state=await self.discovery.status(self.interface_address)
            # Clone before adding client-specific navigation/authorization.
            state=json.loads(json.dumps(state));address=self.interface_address
            state['mbmf']['url']='/mbmf/'
            state['mbmf']['alias']='http://mbmf.local'
            state['webconf']['url']=f'http://{address}:{self.discovery.webconf_port}/'
            state['remote']['url']=f'http://{address}:{self.discovery.vnc_port}/vnc.html?autoconnect=true&resize=scale'
            state['lumaz']['url']=state['remote']['url']
            state['authorized']=self.get_secure_cookie('user')==b'root'
            csrf=self.get_secure_cookie('az_csrf')
            if not csrf:
                csrf=secrets.token_hex(32).encode();self.set_secure_cookie('az_csrf',csrf,httponly=True,samesite='Strict')
            state['csrf']=csrf.decode()
            self.finish(state);return
        raise tornado.web.HTTPError(404)
    async def post(self,path=''):
        if path!='api/action':raise tornado.web.HTTPError(404)
        if self.get_secure_cookie('user')!=b'root':raise tornado.web.HTTPError(401,'Sign in to Webconf for LUMAZ options')
        csrf=self.get_secure_cookie('az_csrf')
        if not csrf or not hmac.compare_digest(csrf,self.request.headers.get('X-AZ-CSRF','').encode()):raise tornado.web.HTTPError(403)
        if self.request.headers.get('Origin')!=self.request.protocol+'://'+self.request.host:raise tornado.web.HTTPError(403)
        if len(self.request.body)>65536:raise tornado.web.HTTPError(413)
        if self.discovery.action_lock.locked():raise tornado.web.HTTPError(409,'Operation already in progress')
        try:
            body=json.loads(self.request.body)
            if not isinstance(body,dict):raise ValueError('Invalid action')
            async with self.discovery.action_lock:
                message=await self.discovery.operations.execute(body)
        except (OSError,ValueError,subprocess.SubprocessError) as error:
            self.set_status(409);self.finish({'error':str(error)});return
        self.discovery.cached=None;self.finish({'message':message})


def register(app,resolver,mdns=True):
    discovery=Discovery(resolver,webconf_port=int(os.environ.get('ZYNTHIAN_WEBCONF_PORT','80')))
    app.add_handlers(r'az\.local(?::[0-9]+)?$',[(r'/',Hub,dict(discovery=discovery))])
    app.add_handlers(r'.*$',[(r'/az(?:/(.*))?',Hub,dict(discovery=discovery))])
    if mdns:
        from mbmf_web_mdns import start
        start('az.local')
    return discovery
