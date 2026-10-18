"""Actual native engine + authenticated HTTP/Unix host bridge, without JACK."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import types
import unittest
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'headless'))
from server import Control, make_server
from zynthian_chains import ChainLinks, Bridge


class NativeLinks(unittest.TestCase):
    def test_real_engine_and_authenticated_api(self):
        with tempfile.TemporaryDirectory(prefix='mbmf-host-links-') as temporary:
            directory=Path(temporary);socket=directory/'engine.sock'
            binary=os.environ.get('HEADLESS_BINARY',str(ROOT/'.build/midi-headless-engine'))
            with (directory/'engine.log').open('w') as log:
                engine=subprocess.Popen([binary,str(ROOT/'midi_human_looper.jsfx'),str(socket),'--chain','--chain-timing','2'],stdout=log,stderr=log)
            bridge=web=thread=None
            try:
                deadline=time.monotonic()+30
                while not socket.exists():
                    if engine.poll() is not None:raise AssertionError((directory/'engine.log').read_text())
                    if time.monotonic()>deadline:raise AssertionError('Engine startup timed out')
                    time.sleep(.1)
                control=Control(str(socket))
                chain=types.SimpleNamespace(chain_id=2,midi_chan=2,midi_slots=[],
                    synth_slots=[[types.SimpleNamespace(id=3,eng_code='JV/synthv1')]],get_title=lambda:'Test Piano')
                manager=types.SimpleNamespace(chains={2:chain},will_midi_howl=lambda a,b:False)
                links=ChainLinks(manager,1,control);bridge=Bridge(directory/'host.sock',links)
                web=make_server('127.0.0.1',0,str(socket),'test-token',directory,bridge.path)
                thread=threading.Thread(target=web.serve_forever,daemon=True);thread.start()
                url='http://127.0.0.1:%s/api/v1/zynthian/chains'%web.server_port
                def request(body=None,token='test-token'):
                    req=urllib.request.Request(url,data=json.dumps(body).encode() if body else None,
                        headers={'X-Engine-Token':token,'Content-Type':'application/json'})
                    with urllib.request.urlopen(req,timeout=20) as response:return json.load(response)
                with self.assertRaises(urllib.error.HTTPError) as rejected:request(token='wrong')
                self.assertEqual(rejected.exception.code,401)
                current=request();self.assertFalse(current['routesManaged'])
                identity=current['chains'][0]['identity']
                body=dict(action='bind',instrumentId=1,identity=identity,
                    inventoryRevision=current['inventoryRevision'],expectedRevision=current['engineRevision'],expectedEngineSessionId=current['engineSessionId'])
                result=request(body);self.assertEqual(result['bindings']['1']['status'],'synchronized')
                instrument=control.request()['instruments'][0]
                self.assertEqual((instrument['output'],instrument['name']),(3,'Test Piano'))
                for edit in (
                    dict(action='instrument_route', instrumentId=1, field='output', value=5),
                    dict(action='parameter_set', targetId=1, moduleId=0, kind=23, value=14),
                    dict(action='instrument_commit', instrumentId=1, enabled=1, input=0, output=5, level=127)):
                    state = control.request()
                    payload = dict(protocolVersion=1, expectedRevision=state['revision'],
                                   expectedEngineSessionId=state['engineSessionId'], **edit)
                    command = urllib.request.Request(
                        'http://127.0.0.1:%s/api/v1/command' % web.server_port,
                        data=json.dumps(payload).encode(),
                        headers={'X-Engine-Token': 'test-token', 'Content-Type': 'application/json'})
                    with self.assertRaises(urllib.error.HTTPError) as conflict:
                        urllib.request.urlopen(command, timeout=20)
                    self.assertEqual(conflict.exception.code, 409)
                    self.assertIn('Unlink', json.load(conflict.exception)['error'])
                    after = control.request()
                    self.assertEqual(after['revision'], state['revision'])
                    self.assertEqual(after['instruments'], state['instruments'])
                before=links.snapshot()
                with self.assertRaises(urllib.error.HTTPError) as stale:request(body)
                self.assertEqual(stale.exception.code,409);self.assertEqual(links.snapshot(),before)
                chain.midi_chan=5;chain.get_title=lambda:'Test Bass';links.synchronize()
                instrument=control.request()['instruments'][0]
                self.assertEqual((instrument['output'],instrument['name']),(6,'Test Bass'))
                manager.chains.clear();links.synchronize()
                self.assertEqual(request()['bindings']['1']['status'],'destination-unavailable')
                state=control.request()
                self.assertEqual(state['backend'],'mock')
                self.assertFalse(any(state.get(k) for k in ('chainRunning','chainRecording','chainArmed','activeNotes')))
            finally:
                if web:web.shutdown();web.server_close()
                if thread:thread.join(timeout=5)
                if bridge:bridge.close()
                engine.terminate()
                try:engine.wait(timeout=10)
                except subprocess.TimeoutExpired:engine.kill();engine.wait()


if __name__=='__main__':unittest.main()
