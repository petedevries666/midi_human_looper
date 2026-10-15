"""Actual Tornado portal + real MBMF engine; LUMAZ/Oram peripherals explicitly fixtures."""
import asyncio
import json
import os
from pathlib import Path
import socket
import sys
import threading
import unittest
from unittest.mock import patch
import subprocess
import shutil
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'zynthian/web_access'))
import test_local_web_access as access_tests
import az_hub as hub
import az_lumaz
import tornado.web
import tornado.websocket

class LoginFixture(tornado.web.RequestHandler):
    def get(self):self.finish('<html>Zynthian fixture login</html>')
    def post(self):self.set_secure_cookie('user','root');self.finish('fixture signed in')
class VNCPage(tornado.web.RequestHandler):
    def get(self):self.finish('<html>noVNC fixture</html>')
class RFB(tornado.websocket.WebSocketHandler):
    def select_subprotocol(self,protocols):return 'binary'
    def open(self):self.write_message(b'RFB 003.008\n',binary=True)

class MPVFixture:
    def __init__(self,path):
        self.path=str(path);self.commands=[];self.values={'idle-active':False,'volume':75,'mute':False,'path':'original-video','pause':True,'loop-file':'inf','audio-device-list':[{'name':'alsa/default:CARD=vc4hdmi','description':'HDMI'}]}
        self.error=False;self.stopped=threading.Event();self.server=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        self.server.bind(self.path);self.server.listen(8);self.server.settimeout(.1)
        self.thread=threading.Thread(target=self.run);self.thread.start()
    def run(self):
        while not self.stopped.is_set():
            try:connection,_=self.server.accept()
            except socket.timeout:continue
            with connection:
                connection.settimeout(1);raw=b''
                while b'\n' not in raw:raw+=connection.recv(4096)
                request=json.loads(raw);cmd=request['command'];self.commands.append(cmd)
                if cmd[0]=='set_property':self.values[cmd[1]]=cmd[2]
                if cmd[0]=='loadfile':self.values['path']=cmd[1]
                if cmd[0]=='stop':self.values['path']=''
                reply={'request_id':request['request_id'],'error':'failure' if self.error else 'success','data':self.values.get(cmd[1]) if cmd[0]=='get_property' else None}
                connection.sendall((json.dumps(reply)+'\n').encode())
    def close(self):self.stopped.set();self.thread.join(2);self.server.close()

class HubTest(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=access_tests.Access.asyncSetUp
    worker=access_tests.Access.worker
    configure=access_tests.Access.configure
    request=access_tests.Access.request
    async def asyncTearDown(self):
        if hasattr(self,'discovery'):self.discovery.client.close()
        if hasattr(self,'mpv'):self.mpv.close()
        if hasattr(self,'control'):self.control.close()
        for handle in getattr(self,'patches',[]):handle.stop()
        await access_tests.Access.asyncTearDown(self)
    async def portal(self):
        self.commands=[];self.jack_active=True
        def systemctl(*args):
            self.commands.append(args)
            if args[0]=='show':return subprocess.CompletedProcess(args,0,'{ path=/usr/bin/python3 ; argv[]=/usr/bin/python3 /root/video_jack_trigger.py ; }','')
            if args[0]=='is-active':return subprocess.CompletedProcess(args,0,'active' if self.jack_active or args[1]!='jack2.service' else 'inactive','')
            return subprocess.CompletedProcess(args,0,'','')
        self.mpv=MPVFixture(self.directory/'mpv.sock');real=hub.mpv
        root=self.directory/'lumaz-device';root.mkdir();config=root/'lumaz/config';config.mkdir(parents=True)
        for name in ('audio_playback.py','midi_routing.py'):shutil.copyfile(ROOT/'tests/fixtures/az-lumaz'/name,root/name)
        (config/'slots.json').write_text(json.dumps({'midi_channel':16,'slots':{'1':{'source':'preserved.mp4'}}}))
        (config/'audio-playback.json').write_text(json.dumps({'sampler':{'enabled':False,'output':None,'retainedCustom':'keep'},'futureMetadata':{'keep':True}}))
        (config/'midi-settings.json').write_text(json.dumps({'calibration':{'keep':True},'version':2,'video_input_ports':[],'light_input_ports':[],'output_port':'','midi_through':True}))
        self.control=socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM);self.control.bind(str(self.directory/'light.sock'));self.control.settimeout(1)
        test=self
        class DeviceSettings(az_lumaz.Settings):
            def __init__(self,mpv):super().__init__(mpv,root,str(test.directory/'light.sock'))
            def helper(self,name):
                module=super().helper(name)
                if name=='midi_routing' and not getattr(module,'az_fixture',False):
                    module.az_fixture=True
                    real_ports=module.jack_physical_ports
                    module.jack_physical_ports=lambda:real_ports(command=(sys.executable,'-c',"print('system:midi_capture_1\\n    Helix MIDI IN\\n    properties: output,physical\\nsystem:midi_playback_1\\n    MIDI OUT\\n    properties: input,physical')"))
                return module
        self.config_root=config
        self.patches=[patch.object(hub,'Settings',DeviceSettings),patch.object(hub,'systemctl',side_effect=systemctl),patch.object(hub,'mpv',side_effect=lambda command:real(command,self.mpv.path))]
        for handle in self.patches:handle.start()
        app=tornado.web.Application([(r'/login',LoginFixture)],cookie_secret='test-only-cookie-secret')
        # Reuse actual production registration, including MBMF proxy; no mocked portal API.
        self.configure('none')
        config=json.loads((self.directory/'web-access.json').read_text());config['hub']=True
        (self.directory/'web-access.json').write_text(json.dumps(config))
        import mbmf_web_entry
        self.resolver=mbmf_web_entry.register(app,self.directory,mdns=False)
        # Retrieve the real registered Discovery object from the router.
        rules=app.wildcard_router.rules
        self.discovery=next(r.target_kwargs['discovery'] for rule in app.default_router.rules
                            for r in getattr(rule.target,'rules',[]) if 'discovery' in getattr(r,'target_kwargs',{}))
        self.http=app.listen(0,address='127.0.0.1');self.servers.append(self.http)
        self.port=next(iter(self.http._sockets.values())).getsockname()[1]
        self.discovery.webconf_port=self.port
        vnc=tornado.web.Application([(r'/vnc.html',VNCPage),(r'/websockify',RFB)]).listen(0,address='127.0.0.1')
        self.servers.append(vnc);self.vnc=vnc;self.discovery.vnc_port=next(iter(vnc._sockets.values())).getsockname()[1]
    async def status(self,headers=None):
        response=await self.request('/az/api/status',host='az.local',headers=headers)
        self.assertEqual(response.code,200,response.body);return response,json.loads(response.body)
    async def authorized(self):
        login=await self.request('/login',host='az.local',method='POST',body='')
        session=login.headers['Set-Cookie'].split(';')[0]
        response,state=await self.status({'Cookie':session})
        csrf=response.headers['Set-Cookie'].split(';')[0]
        return {'Cookie':session+'; '+csrf,'X-AZ-CSRF':state['csrf'],'Origin':'http://az.local','Content-Type':'application/json'}
    async def test_registration_links_honest_checks_and_no_token_leak(self):
        await self.portal();_,state=await self.status()
        for key in ('mbmf','lumaz','webconf','remote'):self.assertTrue(state[key]['online'],state)
        self.assertFalse((await self.discovery.vnc('127.0.0.2'))['online'],'loopback-only noVNC advertised on another interface')
        self.assertNotIn('gateway-fixture-secret',json.dumps(state));self.assertNotIn('token',json.dumps(state))
        self.assertEqual(state['mbmf']['instances'][0]['port'],self.workers[0][2]);self.assertEqual(state['mbmf']['url'],'/mbmf/')
        self.assertIn('127.0.0.1',state['webconf']['url'])
        self.assertIn(b'AZ', (await self.request(host='az.local')).body)
        self.assertNotIn(b'LOCAL CONTROL', (await self.request(host='mbmf.local')).body)
        self.assertIn(b'CONNECTED', (await self.request('/mbmf/app.js',host='az.local')).body)
        self.assertEqual((await self.request('/az/api/status',host='mbmf.local')).code,404)
        self.mpv.error=True;self.discovery.cached=None
        _,state=await self.status();self.assertFalse(state['lumaz']['online']);self.assertTrue(state['mbmf']['online'])
        self.vnc.stop();await self.vnc.close_all_connections();self.discovery.cached=None
        _,state=await self.status();self.assertFalse(state['remote']['online'])
    async def test_auth_csrf_confirmation_and_fixed_service_scope(self):
        await self.portal();path='/az/api/action'
        body=json.dumps({'action':'restart','confirmed':True})
        self.assertEqual((await self.request(path,host='az.local',method='POST',body=body)).code,401)
        headers=await self.authorized()
        for content in ({'action':'restart','confirmed':False},{'action':'restart','confirmed':True,'unit':'jack2.service'}, {'action':'shell','value':'echo nope'}):
            self.assertEqual((await self.request(path,host='az.local',method='POST',body=json.dumps(content),headers=headers)).code,409)
        forged={**headers,'Origin':'http://evil.local'}
        self.assertEqual((await self.request(path,host='az.local',method='POST',body=body,headers=forged)).code,403)
        no_csrf={**headers,'X-AZ-CSRF':'invalid'}
        self.assertEqual((await self.request(path,host='az.local',method='POST',body=body,headers=no_csrf)).code,403)
        self.assertFalse(any(cmd[0]=='restart' for cmd in self.commands))
        response=await self.request(path,host='az.local',method='POST',body=body,headers=headers)
        self.assertEqual(response.code,200,response.body)
        self.assertEqual([c for c in self.commands if c[0]=='restart'],[('restart','video-jack-trigger.service')])
        self.jack_active=False
        self.assertEqual((await self.request(path,host='az.local',method='POST',body=body,headers=headers)).code,409)
        settings_response=await self.request('/az/api/options',host='az.local',headers=headers)
        settings=json.loads(settings_response.body);self.assertEqual(settings['ports']['inputs'][0]['label'],'Helix MIDI IN')
        audio=settings['audio'];audio['sampler']={'enabled':True,'output':'HDMI'}
        body={'action':'settings','category':'audio','value':audio,'revision':settings['revision']}
        response=await self.request(path,host='az.local',method='POST',body=json.dumps(body),headers=headers)
        self.assertEqual(response.code,200,response.body)
        self.assertTrue(json.loads((self.config_root/'audio-playback.json').read_text())['sampler']['enabled'])
        self.assertEqual(json.loads((self.config_root/'audio-playback.json').read_text())['sampler']['retainedCustom'],'keep')
        self.assertEqual((await self.request(path,host='az.local',method='POST',body=json.dumps(body),headers=headers)).code,409,'stale revision was accepted')
        settings=json.loads((await self.request('/az/api/options',host='az.local',headers=headers)).body)
        body={'action':'settings','category':'video','value':'fast','revision':settings['revision']}
        self.assertEqual((await self.request(path,host='az.local',method='POST',body=json.dumps(body),headers=headers)).code,200)
        self.assertEqual((self.config_root/'scale-mode').read_text(),'fast\n')
        self.assertIn(['set_property','dscale','bilinear'],self.mpv.commands)
        settings=json.loads((await self.request('/az/api/options',host='az.local',headers=headers)).body)
        body={'action':'settings','category':'midi','value':{'video_input_ports':['system:midi_capture_1'],'light_input_ports':[],'midi_through':False,'output_port':'system:midi_playback_1'},'revision':settings['revision']}
        self.assertEqual((await self.request(path,host='az.local',method='POST',body=json.dumps(body),headers=headers)).code,200)
        self.assertEqual(json.loads(self.control.recv(1024)),{'action':'reload_midi_routes'})
        self.assertTrue(json.loads((self.config_root/'midi-settings.json').read_text())['calibration']['keep'])
        self.assertEqual(json.loads((self.config_root/'slots.json').read_text())['slots']['1']['source'],'preserved.mp4')
        settings=json.loads((await self.request('/az/api/options',host='az.local',headers=headers)).body)
        body['revision']=settings['revision'];before=(self.config_root/'midi-settings.json').read_bytes()
        self.control.close()
        self.assertEqual((await self.request(path,host='az.local',method='POST',body=json.dumps(body),headers=headers)).code,409)
        self.assertEqual((self.config_root/'midi-settings.json').read_bytes(),before)
        state_before=json.loads((await self.request('/mbmf/api/v1/state',host='az.local')).body)
        await asyncio.sleep(.1)
        state_after=json.loads((await self.request('/mbmf/api/v1/state',host='az.local')).body)
        self.assertGreater(state_after['blocks'],state_before['blocks'])
    async def test_hdmi_bounded_confirmed_and_no_stale_cleanup(self):
        await self.portal();headers=await self.authorized();path='/az/api/action'
        body=json.dumps({'action':'hdmi','confirmed':False})
        self.assertEqual((await self.request(path,host='az.local',method='POST',body=body,headers=headers)).code,409)
        self.assertNotIn('loadfile',[c[0] for c in self.mpv.commands])
        body=json.dumps({'action':'hdmi','confirmed':True})
        response=await self.request(path,host='az.local',method='POST',body=body,headers=headers)
        self.assertEqual(response.code,200,response.body);self.assertEqual(self.mpv.values['path'],'');self.assertTrue(self.mpv.values['pause'])
        task=asyncio.create_task(self.request(path,host='az.local',method='POST',body=body,headers=headers))
        for _ in range(100):
            if self.mpv.values['path'].startswith('av://'):break
            await asyncio.sleep(.01)
        else:self.fail('HDMI test did not start')
        busy=await self.request(path,host='az.local',method='POST',body=json.dumps({'action':'restart','confirmed':True}),headers=headers)
        self.assertEqual(busy.code,409)
        # A native LUMAZ playback change supersedes the test's cleanup ownership.
        await asyncio.to_thread(hub.mpv,['loadfile','new-native-video'])
        self.assertEqual((await task).code,200);self.assertEqual(self.mpv.values['path'],'new-native-video')
    async def test_private_host_checks_failed_vnc_and_processor_recreation(self):
        await self.portal()
        for headers,host in (({'Origin':'http://evil.local'},'az.local'),({},'evil.example')):
            response=await self.request('/az/api/status',host=host,headers=headers);self.assertEqual(response.code,403)
        old=self.workers[0][1];old.terminate();await asyncio.to_thread(old.wait,timeout=5)
        await self.worker(2);await asyncio.sleep(1.05);self.discovery.cached=None
        _,status=await self.status();self.assertEqual(status['mbmf']['instances'],[{'processor':2,'port':self.workers[1][2]}])
        self.workers[1][1].terminate();await asyncio.to_thread(self.workers[1][1].wait,timeout=5)
        await asyncio.sleep(1.05);self.discovery.cached=None
        _,status=await self.status();self.assertFalse(status['mbmf']['online'])

    async def test_browser_navigation_options_and_screenshots(self):
        await self.portal()
        from playwright.async_api import async_playwright
        out=ROOT/'docs/screenshots/az-hub';out.mkdir(parents=True,exist_ok=True)
        async with async_playwright() as pw:
            browser=await pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),args=['--no-sandbox','--disable-gpu','--no-proxy-server','--host-resolver-rules=MAP az.local 127.0.0.1,MAP mbmf.local 127.0.0.1'])
            try:
                page=await browser.new_page(viewport={'width':1440,'height':900},has_touch=True);errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                base=f'http://az.local:{self.port}'
                await page.goto(base+'/');await page.wait_for_function("() => document.querySelector('#mbmf-status').textContent==='ONLINE'")
                await page.locator('#options-toggle').click();self.assertTrue(await page.locator('#authorize').is_visible())
                await page.locator('#authorize').click();self.assertIn('Zynthian fixture',await page.content())
                await page.evaluate("() => fetch('/login',{method:'POST'}).then(r=>r.text())");await page.goto(base+'/');await page.wait_for_function("() => document.querySelector('#mbmf-status').textContent==='ONLINE'")
                await page.locator('#options-toggle').click();await page.locator('[data-menu=video]').click()
                pending=asyncio.Event();release=asyncio.Event()
                async def delay_real_options(route):
                    headers=await route.request.all_headers();headers['host']=f'az.local:{self.port}'
                    response=await route.fetch(url=f'http://127.0.0.1:{self.port}/az/api/options',headers=headers)
                    pending.set();await release.wait();await route.fulfill(response=response)
                await page.route('**/az/api/options',delay_real_options)
                await page.locator('#scale').focus();await page.keyboard.press('End');await page.keyboard.press('Tab');await page.locator('#settings-save').click()
                await page.wait_for_function("() => document.querySelector('#result').textContent==='Scale mode saved and applied'")
                self.assertEqual((self.config_root/'scale-mode').read_text(),'quality\n')
                await asyncio.wait_for(pending.wait(),5);await page.locator('#settings-back').click();release.set();await page.unroute_all(behavior='wait')
                await page.locator('[data-menu=audio]').click()
                await page.locator('#sampler-enabled').check();await page.locator('#sampler-output').select_option('HDMI');await page.locator('#settings-save').click()
                await page.wait_for_function("() => document.querySelector('#result').textContent.includes('Audio settings saved')")
                self.assertTrue(json.loads((self.config_root/'audio-playback.json').read_text())['sampler']['enabled'])
                await page.locator('#settings-back').click();await page.locator('[data-menu=midi]').click();await page.locator('#video_input_ports-0').check();await page.locator('#settings-save').click()
                await page.wait_for_function("() => document.querySelector('#result').textContent.includes('MIDI settings saved')")
                self.assertEqual(json.loads(self.control.recv(1024)),{'action':'reload_midi_routes'})
                await page.locator('#settings-back').click()
                await page.locator('#restart').click();await page.locator('button[value=cancel]').click()
                self.assertFalse(any(c[0]=='restart' for c in self.commands))
                await page.locator('#restart').click();await page.locator('#confirm-go').click();await page.wait_for_function("() => document.querySelector('#result').textContent.includes('Video trigger restarted')")
                self.assertEqual([c for c in self.commands if c[0]=='restart'],[('restart','video-jack-trigger.service')])
                await page.reload();await page.wait_for_function("() => document.querySelector('#mbmf-status').textContent==='ONLINE'")
                for width,height in ((1440,900),(390,844),(320,240)):
                    await page.set_viewport_size({'width':width,'height':height});await page.wait_for_timeout(200)
                    self.assertTrue(await page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
                    await page.screenshot(path=str(out/f'portal-{width}.png'),full_page=True)
                await page.set_viewport_size({'width':390,'height':844});await page.locator('#options-toggle').tap();await page.screenshot(path=str(out/'options-390.png'),full_page=True)
                for menu in ('video','audio','midi'):
                    await page.locator('[data-menu='+menu+']').click();await page.wait_for_function("(title) => document.querySelector('#settings-title').textContent===title && !document.querySelector('#settings-view').hidden",arg=menu.upper()+' SETTINGS');self.assertTrue(await page.evaluate('document.documentElement.scrollWidth<=innerWidth'));await page.screenshot(path=str(out/(menu+'-390.png')),full_page=True);await page.locator('#settings-back').click()
                await page.locator('#mbmf-open').click();await page.wait_for_function("() => document.querySelector('#connection').textContent.includes('CONNECTED')")
                self.assertFalse(await page.locator('#token').is_visible())
                self.assertEqual(errors,[])
                await page.close()
            finally:await browser.close()
        (out/'manifest.json').write_text(json.dumps({'source':'Actual AZ/Tornado + production native MBMF + editor; LUMAZ MPV/systemd and Oram login/RFB are fixtures. Not hardware validation.','screenshots':['portal-1440.png','portal-390.png','portal-320.png','options-390.png','video-390.png','audio-390.png','midi-390.png']},indent=2)+'\n')

if __name__=='__main__':unittest.main()
