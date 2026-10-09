#!/usr/bin/env python3
"""Exercise the actual headless JSFX through the non-RT HTTP worker."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
BINARY = os.environ.get('HEADLESS_BINARY', '/tmp/midi-headless-engine')

class HeadlessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='midi-m0-')
        cls.sock = str(Path(cls.temp.name)/'engine.sock')
        cls.engine = subprocess.Popen([BINARY, str(ROOT/'midi_human_looper.jsfx'), cls.sock], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        cls.wait_for(lambda: Path(cls.sock).exists(), 'engine socket')
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0))
            cls.port = s.getsockname()[1]
        cls.base = f'http://127.0.0.1:{cls.port}'
        cls.start_web()

    @classmethod
    def wait_for(cls, predicate, label):
        deadline = time.monotonic()+5
        while time.monotonic()<deadline:
            try:
                if predicate(): return
            except OSError:
                pass
            time.sleep(.02)
        raise AssertionError(label+' failed to start')

    @classmethod
    def start_web(cls):
        cls.web = subprocess.Popen([sys.executable,str(ROOT/'experiments/headless/server.py'),'--socket',cls.sock,'--port',str(cls.port)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        cls.wait_for(lambda: urllib.request.urlopen(cls.base+'/api/v1/state', timeout=1).status==200, 'HTTP worker')

    @classmethod
    def stop_web(cls):
        cls.web.terminate()
        cls.web.communicate(timeout=5)

    @classmethod
    def tearDownClass(cls):
        cls.stop_web()
        cls.engine.terminate()
        cls.engine.communicate(timeout=5)
        cls.temp.cleanup()

    def call(self, body=None, headers=None, expected=200):
        request = urllib.request.Request(self.base+'/api/v1/'+('command' if body is not None else 'state'),data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json',**(headers or {})})
        try:
            response=urllib.request.urlopen(request,timeout=4)
        except urllib.error.HTTPError as error:
            response=error
        self.assertEqual(response.status,expected)
        return json.load(response)

    def command(self, action, expected=200, **args):
        return self.call(dict(protocolVersion=1,expectedRevision=1,action=action,**args), expected=expected)

    def setUp(self):
        self.command('panic')

    def test_real_engine_and_fifo(self):
        result=subprocess.run([BINARY,'--queue-test'],capture_output=True,text=True,check=True)
        self.assertIn('PASS bounded FIFO',result.stdout)
        state=self.call()
        self.assertEqual(state['schemaVersion'],7)
        self.assertEqual(len(state['phrases']),16)
        self.assertEqual([s['id'] for s in state['switches']],[1,2,3,4])
        self.assertEqual([i['id'] for i in state['instruments']],[1,2,3])
        self.assertGreater(state['blocks'],0)

    def test_independent_switch_input(self):
        for number,pitch,target in ((72,60,1),(73,64,2)):
            self.command('panic')
            before=self.call()['midiCount']
            state=self.command('midi',channel=1,note=number,value=100)
            deadline=time.monotonic()+1
            while (state['midiCount']<=before or state['lastEvent'][2]!=pitch or state['lastEvent'][1]&240 not in (128,144)) and time.monotonic()<deadline:
                time.sleep(.02)
                state=self.call()
            self.assertEqual(state['lastEvent'][2],pitch)
            self.assertGreater(state['midiCount'],before)
            self.command('midi',channel=1,note=number,value=0)
            self.assertEqual(next(s for s in state['switches'] if s['id']==target)['step'],1)

    def test_dispatcher_and_panic(self):
        state=self.command('test',switchId=1,gesture='tap')
        self.assertEqual(state['lastEvent'][2],60)
        self.command('test',switchId=1,gesture='double')
        state=self.command('test',switchId=1,gesture='hold')
        self.assertEqual(state['switches'][0]['step'],0)
        state=self.command('panic')
        self.assertEqual(state['activeNotes'],0)
        time.sleep(.25)
        self.assertEqual(self.call()['midiCount'],state['midiCount'])

    def test_web_process_restart_does_not_stop_engine(self):
        before=self.command('test',switchId=1,gesture='tap')
        self.stop_web()
        self.assertIsNone(self.engine.poll())
        time.sleep(.65)
        self.start_web()
        after=self.call()
        self.assertGreater(after['sampleClock'],before['sampleClock']+24000)
        self.assertGreater(after['midiCount'],before['midiCount'])
        self.assertEqual(after['revision'],before['revision'])
        self.assertEqual(after['engineSessionId'],before['engineSessionId'])

    def test_validation_and_revision(self):
        before=self.call()
        self.call(dict(protocolVersion=1,expectedRevision=99,action='test',switchId=1),expected=409)
        self.command('test',switchId=999,expected=422)
        self.command('test',switchId=True,expected=400)
        self.call(dict(protocolVersion=2,expectedRevision=1,action='panic'),expected=400)
        self.command('rewriteEEL',expected=400)
        self.call(headers={'Origin':'http://unrelated.invalid'},expected=403)
        self.assertEqual(self.call()['midiCount'],before['midiCount'])

    def test_slow_client_does_not_block_scheduler(self):
        before=self.command('test',switchId=1,gesture='tap')
        with socket.socket(socket.AF_UNIX) as client:
            client.connect(self.sock)
            client.sendall(b'17 1')  # Partial command holds only the control thread.
            time.sleep(.65)
        after=self.call()
        self.assertGreater(after['sampleClock'],before['sampleClock']+24000)
        self.assertGreater(after['midiCount'],before['midiCount'])

    def test_engine_survives_malformed_local_client(self):
        before=self.call()
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(3)
            client.connect(self.sock)
            client.sendall(b'not an engine command\n')
            self.assertEqual(json.loads(client.recv(1024))['status'],'invalid')
        after=self.call()
        self.assertGreater(after['sampleClock'],before['sampleClock'])
        self.assertEqual(after['midiCount'],before['midiCount'])

if __name__=='__main__':
    unittest.main()
