"""Actual production editor/API/WS through Tornado's Webconf host routing."""
import asyncio
import base64
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import types
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'zynthian/web_access'))
import mbmf_web_entry as entry
import tornado.httpclient
import tornado.web
import tornado.websocket

class ExistingWebconf(tornado.web.RequestHandler):
    def get(self):self.finish('EXISTING ZYNTHIAN WEBCONF')
class Access(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.directory=Path(self.temp.name)
        self.children=[];self.workers=[];self.servers=[]
        (self.directory/'editor.token').write_text('gateway-fixture-secret')
        (self.directory/'install.json').write_text(json.dumps(dict(repository=str(ROOT),token_file=str(self.directory/'editor.token'))))
        self.configure('none')
        await self.worker(1)
        app=tornado.web.Application([(r'/.*',ExistingWebconf)])
        self.resolver=entry.register(app,self.directory,mdns=False)
        self.http=app.listen(0,address='127.0.0.1');self.servers.append(self.http)
        self.port=next(iter(self.http._sockets.values())).getsockname()[1]
        self.client=tornado.httpclient.AsyncHTTPClient()
    def configure(self,mode):
        (self.directory/'web-access.json').write_text(json.dumps(dict(version=1,auth=mode)))
    async def worker(self,number):
        directory=self.directory/f'processor-{number}';directory.mkdir(exist_ok=True)
        sock=str(directory/'control.sock')
        log=(directory/'runtime.log').open('ab')
        engine=subprocess.Popen([os.environ['HEADLESS_BINARY'],str(ROOT/'midi_human_looper.jsfx'),sock,'--demo'],stdout=log,stderr=log)
        self.children.append(engine)
        for _ in range(100):
            if Path(sock).exists():break
            await asyncio.sleep(.03)
        with socket.socket() as probe:probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
        web=subprocess.Popen([sys.executable,str(ROOT/'headless/server.py'),'--socket',sock,'--port',str(port),
                              '--patch-dir',str(directory),'--token-file',str(self.directory/'editor.token')],stdout=log,stderr=log)
        self.children.append(web);self.workers.append((engine,web,port));log.close()
        for _ in range(100):
            try:
                r=await tornado.httpclient.AsyncHTTPClient().fetch(f'http://127.0.0.1:{port}/api/v1/state',headers={'X-Engine-Token':'gateway-fixture-secret'})
                if r.code==200:break
            except (OSError,tornado.httpclient.HTTPError):await asyncio.sleep(.03)
        else:raise AssertionError('actual editor did not start')
        return engine,web,port
    async def request(self,path='/',host='mbmf.local',method='GET',body=None,headers=None):
        return await self.client.fetch(f'http://127.0.0.1:{self.port}'+path,method=method,body=body,
                 headers={'Host':host,**(headers or {})},raise_error=False,follow_redirects=False)
    async def ws(self,path='/api/v1/ws'):
        return await tornado.websocket.websocket_connect(tornado.httpclient.HTTPRequest(f'ws://127.0.0.1:{self.port}'+path,
                 headers={'Host':'mbmf.local','Origin':'http://mbmf.local'}))
    async def asyncTearDown(self):
        for server in self.servers:server.stop();await server.close_all_connections()
        for child in reversed(self.children):
            if child.poll() is None:child.terminate()
            await asyncio.to_thread(child.wait,timeout=5)
        self.temp.cleanup()
    async def test_public_peer_and_forged_client_address_denied(self):
        def request(remote,peer):
            return types.SimpleNamespace(request=types.SimpleNamespace(host='mbmf.local',headers={},remote_ip=remote,
                protocol='http',connection=types.SimpleNamespace(context=types.SimpleNamespace(address=(peer,80)))))
        self.assertFalse(entry.matches_token('é','gateway-fixture-secret'))
        self.assertFalse(entry.Entry.trusted(request('8.8.8.8','8.8.8.8')))
        self.assertFalse(entry.Entry.trusted(request('127.0.0.1','8.8.8.8')))
        self.assertTrue(entry.Entry.trusted(request('192.168.1.2','192.168.1.2')))

    async def test_trusted_api_ws_no_login_and_webconf_unchanged(self):
        page=await self.request();self.assertEqual(page.code,200)
        self.assertIn(b'<label hidden>LAN token',page.body)
        self.assertNotIn(b'gateway-fixture-secret',page.body)
        state=json.loads((await self.request('/api/v1/state')).body)
        command=dict(protocolVersion=1,expectedRevision=state['revision'],expectedEngineSessionId=state['engineSessionId'],action='panic')
        response=await self.request('/api/v1/command',method='POST',body=json.dumps(command),headers={'Content-Type':'application/json','Origin':'http://mbmf.local'})
        self.assertEqual(response.code,200,response.body)
        ws=await self.ws();await ws.write_message('{}')
        update=json.loads(await asyncio.wait_for(ws.read_message(),5));self.assertIn('engineSessionId',update);ws.close()
        normal=await self.request(host='zynthian.local');self.assertEqual(normal.body,b'EXISTING ZYNTHIAN WEBCONF')
        engine=self.workers[0][0];self.assertIsNone(engine.poll())
    async def test_token_mode_and_cross_origin_rejection(self):
        self.configure('token')
        self.assertEqual((await self.request('/api/v1/state')).code,401)
        self.assertEqual((await self.request('/api/v1/state',headers={'X-Engine-Token':'gateway-fixture-secret'})).code,200)
        self.assertEqual((await self.request('/api/v1/state',headers={'Origin':'http://evil.example'})).code,403)
        ws=await self.ws();await ws.write_message('{}');self.assertIsNone(await asyncio.wait_for(ws.read_message(),5));ws.close()
        ws=await self.ws();await ws.write_message(json.dumps(dict(token='gateway-fixture-secret')))
        self.assertIn('engineSessionId',json.loads(await asyncio.wait_for(ws.read_message(),5)));ws.close()
    async def test_source_midi_download_and_upload_preview(self):
        exported=await self.request('/api/v1/phrase/1/midi')
        self.assertEqual(exported.code,200,exported.body)
        self.assertEqual(exported.body[:4],b'MThd')
        direct=await self.client.fetch('http://127.0.0.1:%s/api/v1/phrase/1/midi'%self.workers[0][2],headers={'X-Engine-Token':'gateway-fixture-secret'})
        self.assertEqual(exported.body,direct.body)
        preview=await self.request('/api/v1/phrase/midi',method='POST',body=json.dumps(dict(phraseId=2,mode='preview',file=base64.b64encode(exported.body).decode())),headers={'Content-Type':'application/json'})
        self.assertEqual(preview.code,200,preview.body)
        self.assertGreater(json.loads(preview.body)['lengthSeconds'],0)

    async def test_auth_change_closes_existing_trusted_stream(self):
        ws=await self.ws();await ws.write_message('{}')
        self.assertIsNotNone(await asyncio.wait_for(ws.read_message(),5))
        self.configure('token')
        for _ in range(8):
            if await asyncio.wait_for(ws.read_message(),5) is None:break
        else:raise AssertionError('trusted stream survived secure mode change')
        ws.close()

    async def test_prefix_fallback_and_chain_recreation(self):
        html=await self.request('/mbmf/',host='127.0.0.1')
        self.assertEqual(html.code,200);self.assertIn(b'src="/mbmf/app.js"',html.body)
        script=await self.request('/mbmf/app.js',host='127.0.0.1')
        self.assertIn(b'/mbmf/api/v1/ws',script.body)
        first=json.loads((await self.request('/mbmf/api/v1/state',host='127.0.0.1')).body)
        old=self.workers[0][1];old.terminate();await asyncio.to_thread(old.wait,timeout=5)
        await self.worker(2);await asyncio.sleep(1.05)
        second=json.loads((await self.request('/api/v1/state')).body)
        self.assertNotEqual(first['engineSessionId'],second['engineSessionId'])
        self.assertEqual(self.resolver.entries()[0]['processor'],2)
    async def test_real_chromium_trusted_alias_and_fallback(self):
        from playwright.async_api import async_playwright
        screenshots=ROOT/'docs/screenshots/web-access';screenshots.mkdir(parents=True,exist_ok=True)
        async with async_playwright() as playwright:
            browser=await playwright.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),
                args=['--no-sandbox','--disable-gpu','--no-proxy-server','--host-resolver-rules=MAP mbmf.local 127.0.0.1'])
            try:
                page=await browser.new_page(viewport=dict(width=800,height=480))
                errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
                for path,host in [('/', 'mbmf.local'),('/mbmf/','127.0.0.1')]:
                    await page.goto('http://%s:%s%s'%(host,self.port,path))
                    await page.wait_for_function("() => document.querySelector('#connection').textContent.includes('CONNECTED')")
                    self.assertFalse(await page.locator('#token').is_visible())
                    self.assertFalse(await page.locator('#connect').is_visible())
                    await page.locator('#save-patch').click()
                    await page.wait_for_function("() => document.querySelector('#patch-status').textContent.toLowerCase().includes('saved')")
                    self.assertEqual(errors,[])
                for width,height in [(320,240),(800,480),(1440,900)]:
                    await page.set_viewport_size(dict(width=width,height=height));await page.wait_for_timeout(150)
                    self.assertTrue(await page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
                    await page.screenshot(path=str(screenshots/('trusted-%s.png'%width)),full_page=True)
                self.configure('token');await page.reload()
                self.assertTrue(await page.locator('#token').is_visible())
                await page.locator('#token').fill('gateway-fixture-secret');await page.locator('#connect').click()
                await page.wait_for_function("() => document.querySelector('#connection').textContent.includes('CONNECTED')")
                await page.wait_for_function("() => document.getElementById('error').textContent===''")
                await page.screenshot(path=str(screenshots/'token-1440.png'),full_page=True)
                before=json.loads((await self.request('/api/v1/state',headers={'X-Engine-Token':'gateway-fixture-secret'})).body)['blocks']
                await page.close();await asyncio.sleep(.2)
                after=json.loads((await self.request('/api/v1/state',headers={'X-Engine-Token':'gateway-fixture-secret'})).body)['blocks']
                self.assertGreater(after,before,'browser disconnect stopped the actual engine')
            finally:await browser.close()

    async def test_multiple_processors_explicit_selection_and_unavailable(self):
        await self.worker(2);await asyncio.sleep(1.05)
        selection=await self.request();self.assertIn(b'Processor 2',selection.body)
        chosen=await self.request('/__mbmf/select/2');self.assertEqual(chosen.code,302)
        cookie=chosen.headers['Set-Cookie'].split(';')[0]
        response=await self.request('/api/v1/state',headers={'Cookie':cookie});self.assertEqual(response.code,200)
        for _,web,_ in self.workers:web.terminate();await asyncio.to_thread(web.wait,timeout=5)
        await asyncio.sleep(1.05)
        self.assertEqual((await self.request()).code,503)

if __name__=='__main__':unittest.main()
