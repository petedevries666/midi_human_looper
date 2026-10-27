import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'headless'))
from midi_thru_service import Service


class Control:
    def __init__(self):
        self.state={'midiThruAvailable':True,'midiThruEnabled':False,'engineSessionId':123,
                    'physicalMidiInputs':[{'port':'ttymidi:MIDI_in','aliases':['DIN-5 MIDI']}]}
    def request(self):return copy.deepcopy(self.state)


class MidiThruService(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.control=Control();self.refreshes=[]
        self.service=Service(Path(self.temp.name)/'midi-inputs.json',self.control,lambda:self.refreshes.append(True),['ttymidi:MIDI_in'])

    def edit(self):
        status=self.service.status()
        return {'key':'ttymidi:MIDI_in','enabled':True,'channels':[0]*16,
                'expectedConfigurationRevision':status['configurationRevision'],
                'expectedEngineSessionId':status['engineSessionId']}

    def test_channel_off_keeps_source_enrolled_for_learn_and_commands(self):
        result=self.service.update_source(self.edit())
        self.assertTrue(result['inputs'][0]['enabled'])
        self.assertEqual(result['inputs'][0]['channels'],[0]*16)
        self.assertEqual(len(self.refreshes),1)

    def test_stale_browser_does_not_replace_another_edit(self):
        edit=self.edit();self.service.update_source(edit)
        before=self.service.store.path.read_bytes()
        with self.assertRaises(ValueError):self.service.update_source(edit)
        self.assertEqual(self.service.store.path.read_bytes(),before)
        self.assertEqual(len(self.refreshes),1)

    def test_engine_restart_and_playing_initial_activation_leave_registry_unsaved(self):
        edit=self.edit();self.control.state['engineSessionId']=124
        with self.assertRaises(ValueError):self.service.update_source(edit)
        self.control.state['engineSessionId']=123;self.control.state['activeNotes']=1
        with self.assertRaises(ValueError):self.service.update_source(edit)
        self.assertFalse(self.service.store.path.exists());self.assertFalse(self.refreshes)

    def test_ambiguous_usb_device_is_never_enrolled(self):
        self.control.state['physicalMidiInputs']=[{'port':f'a2j:KEYBOARD [{n}] (capture): MIDI 1'} for n in (1,2)]
        edit=self.edit();edit['key']='a2j:KEYBOARD (capture): MIDI 1'
        with self.assertRaises(ValueError):self.service.update_source(edit)
        self.assertFalse(self.service.store.path.exists())


if __name__=='__main__':unittest.main()
