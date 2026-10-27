import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'headless'))
from midi_inputs import bootstrap,enroll,inventory,runtime_wire,validate,ingress_plan,Store
from midi_thru_config import decode,validate_inputs


class MidiInputs(unittest.TestCase):
    def test_usb_reconnection_does_not_change_saved_source_identity(self):
        registry=bootstrap(['ttymidi:MIDI_in','a2j:AKAI [20] (capture): MIDI 1'])
        row=inventory(registry,[{'port':'a2j:AKAI [42] (capture): MIDI 1','aliases':['AKAI keyboard']}])[1]
        self.assertEqual((row['id'],row['slot'],row['present']),(2,2,True))
        self.assertEqual(row['name'],'AKAI keyboard')
        self.assertEqual(registry['sources'][1]['id'],2)

    def test_two_identical_usb_names_fail_closed(self):
        registry=bootstrap(['a2j:AKAI [20] (capture): MIDI 1'])
        observed=[{'port':f'a2j:AKAI [{n}] (capture): MIDI 1'} for n in (20,42)]
        row=inventory(registry,observed)[0]
        self.assertTrue(row['ambiguous']);self.assertFalse(row['present'])
        self.assertEqual(runtime_wire(registry,observed)[4],0)

    def test_inventory_does_not_enroll_unknown_or_reconnect_disabled_inputs(self):
        registry=bootstrap(['ttymidi:MIDI_in']);enroll(registry,'ttymidi:MIDI_in',enabled=False)
        before=copy.deepcopy(registry)
        rows=inventory(registry,[{'port':'ttymidi:MIDI_in'},{'port':'system:midi_capture_1'}])
        self.assertEqual(registry,before)
        self.assertFalse(rows[0]['enabled']);self.assertIsNone(rows[1]['id'])
        self.assertEqual(runtime_wire(registry,[]),[1,0])

    def test_reused_runtime_slot_does_not_reuse_patch_identity(self):
        registry=bootstrap(['ttymidi:MIDI_in'])
        enroll(registry,'ttymidi:MIDI_in',enabled=False)
        new=enroll(registry,'a2j:KEYBOARD [33] (capture): MIDI 1')
        self.assertEqual((new['slot'],new['id']),(1,2))
        patch={'version':1,'configuration':[1,1,1,*([0]*16)]}
        self.assertEqual(decode(patch)[0]['sourceId'],1)
        self.assertNotEqual(decode(patch)[0]['sourceId'],new['id'])

    def test_unknown_registry_and_patch_fields_are_preserved_by_refusal(self):
        registry=bootstrap();registry['future']=True
        with self.assertRaises(ValueError):validate(registry)
        with self.assertRaises(ValueError):decode({'version':1,'configuration':[1,0],'future':True})

    def test_failed_enable_does_not_allocate_identity_or_change_registry(self):
        registry=bootstrap([f'input:{n}' for n in range(15)])
        before=copy.deepcopy(registry)
        with self.assertRaises(ValueError):enroll(registry,'input:overflow')
        self.assertEqual(registry,before)
        with self.assertRaises(ValueError):enroll(registry,'input:invalid',enabled='false')
        self.assertEqual(registry,before)

    def test_global_defaults_expand_per_channel_without_changing_patch_rules(self):
        registry=bootstrap(['ttymidi:MIDI_in'])
        registry['defaults'][2]=0
        registry['sources'][0]['channels'][4]=2
        wire=runtime_wire(registry,[{'port':'ttymidi:MIDI_in'}])
        self.assertEqual(wire[:5],[1,1,1,1,1])
        self.assertEqual(wire[5+2],0)
        self.assertEqual(wire[5+4],2)
        self.assertEqual(registry['sources'][0]['channels'][2],-1)

    def test_runtime_requires_real_dedicated_connection_when_requested(self):
        registry=bootstrap(['ttymidi:MIDI_in'])
        observed=[{'port':'ttymidi:MIDI_in','connections':['ZynMidiRouter:dev0_in']}]
        self.assertEqual(runtime_wire(registry,observed,client='mbh_4')[4],0)
        observed[0]['connections'].append('mbh_4:midi_in_1')
        self.assertEqual(runtime_wire(registry,observed,client='mbh_4')[4],1)
        validate_inputs(runtime_wire(registry,observed,client='mbh_4'))

    def test_ingress_plan_never_falls_back_to_merged_legacy_port(self):
        registry=bootstrap(['ttymidi:MIDI_in'])
        observed=[{'port':'ttymidi:MIDI_in'}]
        with self.assertRaises(ValueError):ingress_plan(registry,observed,'mbh_4',['mbh_4:midi_in'])
        self.assertEqual(ingress_plan(registry,observed,'mbh_4',['mbh_4:midi_in_1']),[('ttymidi:MIDI_in','mbh_4:midi_in_1')])
        self.assertEqual(ingress_plan(registry,[],'mbh_4',['mbh_4:midi_in_1']),[])

    def test_store_bootstrap_is_read_only_and_corrupt_file_is_retained(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'midi-inputs.json';store=Store(path,['ttymidi:MIDI_in'])
            registry=store.read();self.assertFalse(path.exists())
            store.save(registry);self.assertEqual(store.read(),registry)
            path.write_text('{"version":999}',encoding='utf-8')
            before=path.read_bytes()
            with self.assertRaises(ValueError):store.save(registry)
            self.assertEqual(path.read_bytes(),before)

    def test_runtime_carrier_rejects_duplicate_slot_and_boolean_values(self):
        wire=[1,2,1,7,1,*([1]*16),1,8,1,*([1]*16)]
        with self.assertRaises(ValueError):validate_inputs(wire)
        with self.assertRaises(ValueError):validate_inputs([1,1,1,7,True,*([1]*16)])


if __name__=='__main__':unittest.main()
