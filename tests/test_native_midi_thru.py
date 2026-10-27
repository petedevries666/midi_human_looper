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
from server import Control


class NativeMidiThru(unittest.TestCase):
    def setUp(self):
        binary=Path(os.environ.get('HEADLESS_BINARY',ROOT/'.build/midi-headless-engine'))
        if not binary.exists():self.skipTest('Build the actual native engine first')
        self.temp=tempfile.TemporaryDirectory(prefix='mbmf-midi-thru-')
        self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name)
        # Real production source and control protocol, without an injected gate.
        source=build_source((ROOT/'midi_human_looper.jsfx').read_text(encoding='utf-8'))
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
        self.inputs=[1,3]
        for slot in (1,2,3):
            modes=[1]*16
            if slot==2:modes[2]=0
            self.inputs.extend([slot,slot,1,*modes])
        self.cmd(op=57,midi_inputs=self.inputs)

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
        self.assertEqual(self.note(3,62,100)['activeNotes'],1)
        self.assertEqual(self.note(1,62,100)['activeNotes'],1)
        self.assertEqual(self.note(3,62,0)['activeNotes'],1)
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


    def test_closing_usb_channel_leaves_other_input_note_running(self):
        self.assertEqual(self.note(1,66,100)['activeNotes'],1)
        self.assertEqual(self.note(3,67,100)['activeNotes'],2)
        modes=[-1]*16;modes[2]=0
        self.assertEqual(self.cmd(op=56,midi_thru=[1,1,1,*modes])['activeNotes'],1)
        self.assertEqual(self.note(1,66,0)['activeNotes'],1)
        self.assertEqual(self.note(3,67,0)['activeNotes'],0)

    def test_disconnection_releases_only_the_disconnected_input(self):
        self.assertEqual(self.note(1,68,100)['activeNotes'],1)
        self.assertEqual(self.note(3,69,100)['activeNotes'],2)
        disconnected=list(self.inputs);disconnected[4]=0
        self.assertEqual(self.cmd(op=57,midi_inputs=disconnected)['activeNotes'],1)
        self.assertEqual(self.note(3,69,0)['activeNotes'],0)

    def test_reenable_after_release_while_off_does_not_swallow_fresh_note_off(self):
        self.note(1,71,100)
        modes=[-1]*16;modes[2]=0
        self.assertEqual(self.cmd(op=56,midi_thru=[1,1,1,*modes])['activeNotes'],0)
        self.note(1,71,0)
        self.cmd(op=56,midi_thru=[1,0])
        self.assertEqual(self.note(1,71,100)['activeNotes'],1)
        self.assertEqual(self.note(1,71,0)['activeNotes'],0)

    def test_reconnection_without_old_note_off_starts_with_clean_ownership(self):
        self.note(1,72,100)
        disconnected=list(self.inputs);disconnected[4]=0
        self.assertEqual(self.cmd(op=57,midi_inputs=disconnected)['activeNotes'],0)
        self.cmd(op=57,midi_inputs=self.inputs)
        self.assertEqual(self.note(1,72,100)['activeNotes'],1)
        self.assertEqual(self.note(1,72,0)['activeNotes'],0)

    def test_assigned_controller_release_while_off_does_not_leave_stale_gate(self):
        self.cmd(op=14,target=17,arg=1,ch=2,note=76)
        modes=list(self.inputs);modes[5+2]=2
        self.cmd(op=57,midi_inputs=modes)
        self.assertEqual(self.note(1,76,100)['activeNotes'],1)
        off=[-1]*16;off[2]=0
        self.assertEqual(self.cmd(op=56,midi_thru=[1,1,1,*off])['activeNotes'],0)
        self.note(1,76,0)
        self.cmd(op=56,midi_thru=[1,0])
        self.assertEqual(self.note(1,76,100)['activeNotes'],1)
        self.assertEqual(self.note(1,76,0)['activeNotes'],0)

    def test_all_includes_controller_notes_but_never_learn_capture(self):
        self.cmd(op=14,target=17,arg=1,ch=2,note=74)
        self.assertEqual(self.note(1,74,100)['activeNotes'],0)
        self.note(1,74,0)
        modes=list(self.inputs);modes[5+2]=2
        self.cmd(op=57,midi_inputs=modes)
        self.assertEqual(self.note(1,74,100)['activeNotes'],1)
        self.assertEqual(self.note(1,74,0)['activeNotes'],0)
        self.cmd(op=15,target=17,arg=0)
        self.assertEqual(self.note(1,75,100)['activeNotes'],0)
        self.assertEqual(self.note(1,75,0)['activeNotes'],0)
        self.assertEqual(self.note(1,75,100)['activeNotes'],1)
        self.assertEqual(self.note(1,75,0)['activeNotes'],0)

    def test_all_can_play_smart_switch_command_after_silent_learn(self):
        ident=self.control.request()['switches'][0]['id']
        self.cmd(op=50,target=ident,arg=0)
        self.assertEqual(self.note(2,38,100)['activeNotes'],0)
        self.note(2,38,0)
        self.assertEqual(self.note(1,38,100)['activeNotes'],0)
        self.note(1,38,0)
        modes=list(self.inputs);modes[5+2]=2
        self.cmd(op=57,midi_inputs=modes)
        self.assertEqual(self.note(1,38,100)['activeNotes'],1)
        self.assertEqual(self.note(1,38,0)['activeNotes'],0)

    def test_patch_roundtrip_and_empty_patch_keep_global_input_registry(self):
        modes=[-1]*16;modes[2]=0
        self.cmd(op=56,midi_thru=[1,1,1,*modes])
        state=self.control.request()
        patch=self.control.request(op=4,revision=state['revision'],session=state['engineSessionId'])
        self.assertEqual(patch['midiThru']['configuration'],[1,1,1,*modes])
        cleared=self.cmd(op=42)
        self.assertEqual(cleared['midiThru']['configuration'],[1,0])
        self.assertTrue(cleared['midiThruEnabled'])
        self.cmd(op=11,target=1,arg=1,ch=0,note=1,value=127)
        self.assertEqual(self.note(1,70,100)['activeNotes'],1)
        self.note(1,70,0)
        restored=self.cmd(op=5,target=patch['schema'],patch=patch)
        self.assertEqual(restored['midiThru'],patch['midiThru'])
        self.assertEqual(self.note(1,70,100)['activeNotes'],0)
        self.note(1,70,0)


if __name__=='__main__':unittest.main()
