"""Exercise the expressive patch carrier in a private native engine, without JACK."""
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'headless'))
from native_capacity import build_source
from server import Control


class ExpressiveIntegration(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='mbmf-expressive-')
        self.addCleanup(self.temp.cleanup)
        directory = pathlib.Path(self.temp.name)
        source = directory / 'native-expanded.jsfx'
        source.write_text(build_source((ROOT / 'midi_human_looper.jsfx').read_text(encoding='utf-8')), encoding='utf-8')
        socket = directory / 'engine.sock'
        binary = os.environ.get('HEADLESS_BINARY', str(ROOT / '.build/midi-headless-engine'))
        if not pathlib.Path(binary).exists():
            self.skipTest('Native engine binary is not built')
        self.log = (directory / 'engine.log').open('w')
        self.addCleanup(self.log.close)
        self.engine = subprocess.Popen([binary, str(source), str(socket), '--chain', '--chain-timing', '2'],
                                       stdout=self.log, stderr=self.log)
        self.addCleanup(self.stop)
        for _ in range(200):
            if socket.exists():
                break
            if self.engine.poll() is not None:
                self.fail((directory / 'engine.log').read_text())
            time.sleep(.05)
        else:
            self.fail('Private native engine did not start')
        self.control = Control(str(socket))

    def stop(self):
        self.engine.terminate()
        self.engine.wait(timeout=10)

    def cmd(self, **kwargs):
        state = self.control.request()
        reply = self.control.request(revision=state['revision'], session=state['engineSessionId'], **kwargs)
        self.assertEqual(reply['status'], 'ok', reply)
        return self.control.request()

    def wait(self, predicate, label, seconds=3):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            state = self.control.request()
            if predicate(state):
                return state
            time.sleep(.01)
        self.fail(label + ': ' + str({k: state.get(k) for k in
                                    ('activeNotes', 'midiCount', 'lastEvent', 'expressivePending')}))

    def test_curve_live_phrase_patch_and_panic(self):
        state = self.control.request()
        for instrument in state['instruments']:
            self.cmd(op=11, target=instrument['id'], arg=0, ch=1, note=instrument['output'], value=127)
        self.cmd(op=11, target=1, arg=1, ch=1, note=1, value=127)
        wire = [1, 1, 1, 1, 0, 0, 0, 0, 1, 0, 0, 1, 0,
                2, 1, 100, 2, 1, 127, 127, 1]
        state = self.cmd(op=55, expressive=wire)
        self.assertEqual(state['nativeExpressive']['configuration'], wire)
        state = self.cmd(op=3, ch=0, note=64, value=20)
        self.wait(lambda s: s['activeNotes'] == 1 and s['midiCount'] > state['midiCount'] - 1,
                  'live attack')
        state = self.control.request()
        self.assertEqual(state['lastEvent'][3], 108)  # 20 -> 108 on inverted curve
        self.cmd(op=3, ch=0, note=64, value=0)
        self.wait(lambda s: s['activeNotes'] == 0, 'live release')
        state = self.control.request()
        exported = self.control.request(op=4, revision=state['revision'], session=state['engineSessionId'])
        self.assertEqual(exported['nativeExpressive']['configuration'], wire)
        self.cmd(op=35, target=0, arg=1,
                 phrase={'lengthSeconds': .4, 'events': [[0, 144, 65, 30], [.2, 128, 65, 0]]})
        self.cmd(op=32, target=1, arg=20, macro=[0, 1])
        self.cmd(op=49, target=0, value=0)
        self.cmd(op=40, target=0, arg=1)
        state = self.wait(lambda s: s['activeNotes'] == 1, 'phrase attack')
        self.assertEqual(state['lastEvent'][3], 98)  # 30 -> 98
        self.cmd(op=40, target=0, arg=6)
        self.wait(lambda s: s['activeNotes'] == 0 and s['expressivePending'] == 0,
                  'phrase stop releases transformed note')
        self.cmd(op=3, ch=0, note=67, value=40)
        self.wait(lambda s: s['activeNotes'] == 1, 'attack before panic')
        self.cmd(op=2)
        self.wait(lambda s: s['activeNotes'] == 0 and s['expressivePending'] == 0,
                  'panic drains expressive ledger')


if __name__ == '__main__':
    unittest.main()
