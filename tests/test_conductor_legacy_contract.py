#!/usr/bin/env python3
"""Frozen source-MIDI and identity contract before changing instance ownership."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'headless'))
import portable_project as portable
from phrase_midi import write_smf
from test_portable_project import fixture as empty_patch
import mido
import io

SOURCE = json.loads((ROOT/'tests/fixtures/conductor/legacy-source.json').read_text())

def patch_fixture():
    patch=empty_patch()
    memory=patch['memory']
    events=SOURCE['sourceEvents']
    memory[:20]=[0]*20
    memory[:len(events)*5]=[v for event in events for v in event]
    memory[portable.COUNT]=len(events)
    memory[portable.LENGTH]=SOURCE['lengthSamples']
    # Distinct authored source in the next slot; no implicit empty-track notes.
    start=portable.STRIDE
    memory[start:start+10]=[0,146,48,79,0,11025,130,48,19,0]
    memory[portable.COUNT+1]=2;memory[portable.LENGTH+1]=22050
    return patch

class LegacyContract(unittest.TestCase):
    def test_existing_parameter_identity_and_normalization_are_frozen(self):
        expected=json.loads((ROOT/'tests/fixtures/conductor/legacy-parameters.json').read_text())
        actual=json.loads((ROOT/'modules/catalog.json').read_text())
        self.assertEqual(actual['contractVersion'],expected['contractVersion'])
        by_id={p['id']:p for p in actual['parameters']}
        for parameter in expected['parameters']:
            self.assertEqual({key:by_id[parameter['id']][key] for key in parameter},parameter)

    def test_cross_host_sample_conversion_preserves_source_and_independence(self):
        original=patch_fixture();before=copy.deepcopy(original)
        project=portable.capture(original,44100,project_id='aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee')
        self.assertEqual(project['version'],SOURCE['portableVersion'])
        for rate in (44100,48000,96000):
            for adapter in ('native','reaper'):
                restored=portable.materialize(project,rate,adapter)
                self.assertEqual(restored['schema'],SOURCE['schema'])
                for i,event in enumerate(SOURCE['sourceEvents']):
                    base=i*5
                    self.assertEqual(restored['memory'][base],round(SOURCE['eventSeconds'][i]*rate))
                    self.assertEqual(restored['memory'][base+1:base+5],event[1:])
                self.assertEqual(restored['memory'][portable.STRIDE+1:portable.STRIDE+4],[146,48,79])
                self.assertTrue(all(restored['memory'][portable.COUNT+p]==0 for p in range(2,16)))
        self.assertEqual(original,before)
        self.assertEqual(portable.materialize(project,44100),original)

    def test_source_export_has_real_tick_zero_and_preserves_note_release_semantics(self):
        data=write_smf(dict(lengthSeconds=1,bpm=120,events=[
            [seconds,*event[1:4]] for seconds,event in zip(SOURCE['eventSeconds'],SOURCE['sourceEvents'])]))
        smf=mido.MidiFile(file=io.BytesIO(data))
        tick=0;actual=[]
        for message in smf.tracks[0]:
            tick+=message.time
            if not message.is_meta:
                actual.append((tick,list(message.bytes())))
        self.assertEqual(actual[0][0],0)
        for (tick,raw),seconds,event in zip(actual,SOURCE['eventSeconds'],SOURCE['sourceEvents']):
            self.assertEqual(raw,event[1:4])
            self.assertAlmostEqual(tick/smf.ticks_per_beat/2,seconds,places=8)
        self.assertEqual(len(actual),len(SOURCE['sourceEvents']))

    def test_unknown_data_rejected_without_mutating_original(self):
        patch=patch_fixture();patch['futureConductor']={'steps':[{'sourceId':99}]}
        original=copy.deepcopy(patch)
        with self.assertRaises(ValueError):portable.capture(patch,44100)
        self.assertEqual(patch,original)

    def test_runtime_playheads_not_project_authority(self):
        patch=patch_fixture()
        for offset in (portable.TRIGGER,portable.POSITION,portable.REPEAT):patch['memory'][offset]=7
        project=portable.capture(patch,44100)
        for offset in (portable.TRIGGER,portable.POSITION,portable.REPEAT):
            self.assertEqual(project['payload']['patch']['memory'][offset],0)
        self.assertEqual(project['payload']['patch']['memory'][portable.COUNT],6)

if __name__=='__main__':unittest.main()
