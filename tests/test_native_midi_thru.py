"""Actual native EEL ingress isolation; no JACK or musical device is used."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'headless'))
from native_capacity import build_source
from native_midi_thru_source import extend
from server import Control


class NativeMidiThru(unittest.TestCase):
    def setUp(self):
        binary=Path(os.environ.get('HEADLESS_BINARY',ROOT/'.build/midi-headless-engine'))
        if not binary.exists():self.skipTest('Build the actual native engine first')
        self.temp=tempfile.TemporaryDirectory(prefix='mbmf-midi-thru-')
        self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name)
        # Real native source, explicitly configured as USB slot 1 and DIN slot 2.
        source=extend(build_source((ROOT/'midi_human_looper.jsfx').read_text(encoding='utf-8')))
        source=source.replace('\n@block\n','\nnative_thru_enabled=1;mem[NATIVE_THRU_MODE_BASE+2*16+2]=0;\n@block\n',1)
        path=root/'ingress.jsfx';path.write_text(source,encoding='utf-8')
        socket=root/'control.sock'
        self.log=(root/'engine.log').open('w');self.addCleanup(self.log.close)
        self.engine=subprocess.Popen([str(binary),str(path),str(socket),'--chain','--chain-timing','2'],stdout=self.log,stderr=self.log)
        self.addCleanup(self.stop)
        for _ in range(300):
            if socket.exists():break
            if self.engine.poll() is not None:self.fail((root/'engine.log').read_text())
            time.sleep(.03)
        else:self.fail('Native ingress fixture did not start')
        self.control=Control(str(socket))
        self.cmd(op=11,target=1,arg=1,ch=0,note=1,value=127)

    def stop(self):
        self.engine.terminate()
        self.engine.wait(timeout=10)

    def cmd(self,**kwargs):
        s=self.control.request()
        result=self.control.request(revision=s['revision'],session=s['engineSessionId'],**kwargs)
        self.assertEqual(result['status'],'ok',result)
        return self.control.request()

    def note(self,slot,note,value):
        return self.cmd(op=3,arg=slot,ch=2,note=note,value=value)

    def test_din_off_usb_same_channel_still_plays_and_releases(self):
        self.assertEqual(self.note(2,60,100)['activeNotes'],0)
        self.assertEqual(self.note(1,60,100)['activeNotes'],1)
        self.assertEqual(self.note(2,60,0)['activeNotes'],1)
        self.assertEqual(self.note(1,60,0)['activeNotes'],0)

    def test_equal_notes_from_two_allowed_inputs_do_not_cut_each_other(self):
        self.assertEqual(self.note(0,62,100)['activeNotes'],1)
        self.assertEqual(self.note(1,62,100)['activeNotes'],1)
        self.assertEqual(self.note(0,62,0)['activeNotes'],1)
        self.assertEqual(self.note(1,62,0)['activeNotes'],0)

    def test_phrase_learn_receives_blocked_din_and_capture_is_silent(self):
        self.cmd(op=34,target=1,arg=0)
        s=self.note(2,36,100)
        self.assertEqual(s['phrases'][0]['triggerNote'],36)
        self.assertEqual(s['phrases'][0]['triggerChannel'],3)
        self.assertEqual(s['activeNotes'],0)
        self.assertEqual(self.note(2,36,0)['activeNotes'],0)

    def test_smart_switch_learn_receives_blocked_din_without_music(self):
        ident=self.control.request()['switches'][0]['id']
        self.cmd(op=50,target=ident,arg=0)
        s=self.note(2,37,100)
        switch=next(v for v in s['switches'] if v['id']==ident)
        self.assertEqual((switch['kind'],switch['number'],switch['channel']),(1,37,3))
        self.assertEqual(s['activeNotes'],0)

    def test_panic_clears_ingress_ownership_before_next_note(self):
        self.assertEqual(self.note(1,65,100)['activeNotes'],1)
        self.assertEqual(self.cmd(op=2)['activeNotes'],0)
        self.assertEqual(self.note(1,65,0)['activeNotes'],0)
        self.assertEqual(self.note(1,65,100)['activeNotes'],1)
        self.assertEqual(self.note(1,65,0)['activeNotes'],0)


if __name__=='__main__':unittest.main()
