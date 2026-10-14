"""Additive Webconf virtual host + fallback; all discovery is outside MIDI execution."""
import asyncio
import json
import hmac
import logging
from pathlib import Path
import re
import sys
import threading
import time
from urllib.parse import urlsplit
import tornado.httpclient
import tornado.web
import tornado.websocket
sys.path.insert(0,str(Path(__file__).parent))
from mbmf_web_policy import local_address

def matches_token(value,expected):
    return hmac.compare_digest(str(value).encode('utf-8'),expected.encode('utf-8'))

DATA=Path('/zynthian/zynthian-my-data/midi-human-looper')

def ticks(pid):
    try:
        fields=Path('/proc/%s/stat'%int(pid)).read_text().rsplit(')',1)[1].split()
        return None if fields[0] in ('Z','X') else fields[19]
    except (OSError,ValueError,IndexError):return None

class Resolver:
    def __init__(self,directory=DATA,proc=Path('/proc')):
        self.directory=Path(directory);self.proc=Path(proc);self.lock=threading.Lock();self.cache=[];self.cached_at=0
    def config(self):
        path=self.directory/'web-access.json'
        if path.is_symlink() or path.stat().st_size>4096:raise ValueError('invalid Web access config')
        config=json.loads(path.read_text())
        if config.get('version')!=1 or config.get('auth') not in ('none','token'):raise ValueError('invalid Web access auth mode')
        return config
    def entries(self):
        # Existing workers identify their exact socket, port, and token file in
        # argv. No fixed processor number, port, synth, or UI focus is consulted.
        with self.lock:
            if time.monotonic()-self.cached_at<1:return list(self.cache)
            config=json.loads((self.directory/'install.json').read_text())
            server=str(Path(config['repository'])/'headless/server.py')
            results=[]
            for process in self.proc.glob('[0-9]*'):
                try:
                    args=process.joinpath('cmdline').read_bytes().decode().split('\0')
                    if server not in args:continue
                    def argument(name):return args[args.index(name)+1]
                    socket=Path(argument('--socket'))
                    if socket.name!='control.sock' or socket.parent.parent!=self.directory:continue
                    match=re.fullmatch(r'processor-([0-9]+)',socket.parent.name)
                    if not match:continue
                    port=int(argument('--port'))
                    if not 1024<=port<=65535:continue
                    token=''
                    if '--token-file' in args:
                        token_path=Path(argument('--token-file'))
                        if str(token_path)!=config.get('token_file') or token_path.is_symlink():continue
                        token=token_path.read_text().strip()
                    generation=process.joinpath('stat').read_text().rsplit(')',1)[1].split()[19]
                    results.append(dict(processor=int(match[1]),port=port,pid=int(process.name),ticks=generation,token=token))
                except (OSError,ValueError,IndexError):continue
            self.cache=sorted(results,key=lambda item:item['processor']);self.cached_at=time.monotonic()
            return list(self.cache)
    def auth_token(self):
        config=json.loads((self.directory/'install.json').read_text())
        path=Path(config['token_file'])
        if path.is_symlink() or path.stat().st_size>4096:raise ValueError('invalid token file')
        token=path.read_text().strip()
        if not token:raise ValueError('token mode requires an existing editor token')
        return token
    async def choose(self,cookie):
        entries=await asyncio.to_thread(self.entries)
        if len(entries)==1:return entries[0],entries
        for item in entries:
            if cookie=='%s:%s'%(item['processor'],item['ticks']):return item,entries
        return None,entries

class Entry(tornado.websocket.WebSocketHandler):
    def initialize(self,resolver,prefix=''):
        self.resolver=resolver;self.prefix=prefix;self.upstream=None;self.first_frame=True
        self.mode=resolver.config()["auth"]
        self.expected_token=resolver.auth_token() if self.mode=='token' else ''
    def trusted(self):
        try:host=(urlsplit('http://'+self.request.host).hostname or '').lower()
        except ValueError:return False
        origin=self.request.headers.get('Origin')
        if not local_address(self.request.remote_ip):return False
        peer=getattr(getattr(self.request.connection,'context',None),'address',None)
        if peer and not local_address(peer[0]):return False
        if host!='mbmf.local' and not local_address(host) and not re.fullmatch(r'[a-z0-9-]+\.local',host):return False
        return not origin or origin==self.request.protocol+'://'+self.request.host
    def check_origin(self,origin):return self.trusted()
    async def get(self,path=''):
        path=path or ''
        if not self.trusted():self.set_status(403);self.finish('Local same-origin access only');return
        if self.request.headers.get('Upgrade','').lower()=='websocket':
            self.target,self.candidates=await self.resolver.choose(self.get_cookie('mbmf_processor',''))
            if not self.target:self.set_status(503);self.finish('No selected MBMF editor');return
            return await super().get(path)
        await self.proxy(path)
    async def post(self,path=''):await self.proxy(path)
    async def head(self,path=''):await self.proxy(path)
    async def proxy(self,path):
        path=path or ''
        if not self.trusted():self.set_status(403);self.finish('Local same-origin access only');return
        target,entries=await self.resolver.choose(self.get_cookie('mbmf_processor',''))
        if path.startswith('__mbmf/select/'):
            selected=next((e for e in entries if str(e['processor'])==path.rsplit('/',1)[-1]),None)
            if selected:
                self.set_cookie('mbmf_processor','%s:%s'%(selected['processor'],selected['ticks']),httponly=True,samesite='Strict')
                self.redirect(self.prefix+'/');return
            self.set_status(404);self.finish('Processor unavailable');return
        if not target:
            if path.startswith('api/') or self.request.method=='POST':
                self.set_status(503);self.finish(dict(error='Select an available MBMF processor from the entry page'));return
            self.set_status(503 if not entries else 200)
            self.set_header('Content-Type','text/html; charset=utf-8')
            self.finish('<!doctype html><meta name=viewport content="width=device-width"><title>MBMF</title><style>html{background:#000;color:#bbb;font:13px monospace}h1{color:#fff;font-size:18px}a{color:#ffe900;padding:6px;border:1px solid #555;display:inline-block}</style><h1>MBMF</h1>'+('Add a MIDI Bad Mother Fucker chain in Zynthian.' if not entries else ''.join('<p><a href="%s/__mbmf/select/%s">Processor %s</a></p>'%(self.prefix,e['processor'],e['processor']) for e in entries)))
            return
        if len(self.request.body)>16000000:self.set_status(413);self.finish('Upload too large');return
        if self.mode=='token' and (path.startswith('api/') or self.request.method=='POST') and not matches_token(self.request.headers.get('X-Engine-Token',''),self.expected_token):
            self.set_status(401);self.finish(dict(error='Editor token required'));return
        if ticks(target['pid'])!=target['ticks']:
            self.resolver.cached_at=0;self.set_status(503);self.finish('Editor restarting; retry shortly.');return
        headers={k:v for k,v in self.request.headers.items() if k.lower() not in ('host','origin','connection','transfer-encoding','content-length','x-forwarded-for','x-real-ip')}
        host='127.0.0.1:%s'%target['port']
        headers['Host']=host
        headers['X-Engine-Token']=target['token']
        if self.request.headers.get('Origin'):headers['Origin']='http://'+host
        uri='http://'+host+'/'+path+('?' + self.request.query if self.request.query else '')
        try:
            response=await tornado.httpclient.AsyncHTTPClient().fetch(uri,method=self.request.method,headers=headers,
                body=self.request.body if self.request.method=='POST' else None,request_timeout=10,follow_redirects=False,raise_error=False)
        except (OSError,tornado.httpclient.HTTPError):self.set_status(503);self.finish('Editor restarting; retry shortly.');return
        self.set_status(response.code)
        for name in ('Content-Type','Cache-Control','Content-Security-Policy','X-Content-Type-Options','Content-Disposition'):
            if name in response.headers:self.set_header(name,response.headers[name])
        for cookie in response.headers.get_list('Set-Cookie'):self.add_header('Set-Cookie',cookie)
        body=response.body
        mime=response.headers.get('Content-Type','')
        if self.mode=='none':
            if mime.startswith('text/html'):
                body=body.replace(b'<label>LAN token ',b'<label hidden>LAN token ')
                body=body.replace(b'<button id="connect"',b'<button hidden id="connect"')
            elif mime.startswith('text/css'):body+=b'\n.connection [hidden]{display:none!important}\n'
        if self.mode=='token' and path=='app.js':
            body+=b"\ndocument.getElementById('connect')?.addEventListener('click',async()=>{await refresh();if(document.getElementById('connection').textContent.includes('CONNECTED'))document.getElementById('error').textContent='';});\n"
        if self.prefix:
            mime=response.headers.get('Content-Type','')
            if mime.startswith('text/html'):
                body=re.sub(rb'((?:src|href)=["\'])/',lambda m:m[1]+self.prefix.encode()+b'/',body)
            elif 'javascript' in mime:body=body.replace(b'/api/v1/',self.prefix.encode()+b'/api/v1/')
            elif 'text/css' in mime:body=body.replace(b'/fonts/',self.prefix.encode()+b'/fonts/')
        self.finish(body)
    async def open(self,path=''):
        if ticks(self.target['pid'])!=self.target['ticks']:self.close(1013,'Editor restarting');return
        host='127.0.0.1:%s'%self.target['port']
        headers={'Origin':'http://'+host}
        try:
            self.upstream=await tornado.websocket.websocket_connect(tornado.httpclient.HTTPRequest('ws://'+host+'/'+path,headers=headers,connect_timeout=5))
            self.reader=asyncio.create_task(self.pump())
        except (OSError,tornado.httpclient.HTTPError):self.close(1013,'Editor unavailable')
    async def on_message(self,message):
        # open() completes before Tornado dispatches client frames.
        if self.first_frame:
            if self.mode=='token':
                try:valid=matches_token(json.loads(message).get('token',''),self.expected_token)
                except (ValueError,TypeError,AttributeError):valid=False
                if not valid:self.close(1008,'Editor token required');return
            message=json.dumps(dict(token=self.target['token']))
        self.first_frame=False
        if self.upstream:await self.upstream.write_message(message,binary=isinstance(message,bytes))
    async def pump(self):
        try:
            while self.upstream:
                message=await self.upstream.read_message()
                if message is None:break
                if self.resolver.config()['auth']!=self.mode:
                    self.close(1008,'Editor access mode changed');break
                await self.write_message(message,binary=isinstance(message,bytes))
        except (OSError,tornado.websocket.WebSocketClosedError):pass
        finally:self.close()
    def on_close(self):
        if self.upstream:self.upstream.close();self.upstream=None
        if hasattr(self,'reader'):self.reader.cancel()

def register(app,directory=DATA,mdns=True):
    resolver=Resolver(directory)
    # Specific host rules precede Tornado's original wildcard routes.
    app.add_handlers(r'mbmf\.local(?::[0-9]+)?$',[(r'/(.*)',Entry,dict(resolver=resolver))])
    app.add_handlers(r'.*$',[(r'/mbmf(?:/(.*))?',Entry,dict(resolver=resolver,prefix='/mbmf'))])
    if mdns:
        from mbmf_web_mdns import start
        start()
    return resolver
