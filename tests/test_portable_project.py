import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'headless'))
import portable_project as p


def fixture():
    m=[0]*p.SIZE
    m[p.COUNT]=4; m[p.LENGTH]=44100
    m[:20]=[0,146,60,100,0, 2205,146,64,91,0, 11025,130,60,30,0, 22050,130,64,20,0]
    return dict(format='MIDI_HUMAN_LOOPER_PATCH',schema=7,work_mem_size=p.SIZE,
                memory=m,globals=[44100,0,0,0,120,0,0,1,0])

class PortableTests(unittest.TestCase):
    def test_samples_are_not_portable_seconds_are(self):
        original=fixture();project=p.capture(original,44100)
        restored=p.materialize(project,48000)
        self.assertEqual(restored['memory'][5],2400)
        self.assertEqual(restored['memory'][15],24000)
        self.assertEqual(restored['globals'][0],48000)
        self.assertEqual(restored['memory'][1:4],original['memory'][1:4])
        self.assertEqual(original,fixture())
        self.assertEqual(p.materialize(project,44100),original)
    def test_revision_parent_identity_tamper_and_unknown(self):
        a=p.capture(fixture(),44100)
        b=p.capture(fixture(),44100,a['projectId'],a['revisionId'])
        self.assertEqual(a['projectId'],b['projectId']);self.assertNotEqual(a['revisionId'],b['revisionId'])
        for change in ('hash','version','unknown'):
            bad=copy.deepcopy(a)
            if change=='hash':bad['payload']['name']='tampered'
            elif change=='version':bad['version']=2
            else:bad['future']=True
            with self.assertRaises(ValueError):p.validate(bad)
    def test_invalid_patch_and_unsupported_data_preserved(self):
        bad=fixture();bad['memory'][p.COUNT]=2049
        with self.assertRaises(ValueError):p.capture(bad,44100)
        bad=fixture();bad['future']=1
        with self.assertRaises(ValueError):p.capture(bad,44100)
        native=fixture();native['controllerEngine']={'version':1,'configuration':[1,1,0,0,7]+[0]*2172}
        project=p.capture(native,44100)
        with self.assertRaises(ValueError):p.materialize(project,48000,'reaper')
        self.assertEqual(project['payload']['patch']['controllerEngine'],native['controllerEngine'])
    def test_no_playhead_recall_and_independent_phrases(self):
        patch=fixture();patch['memory'][p.TRIGGER]=1;patch['memory'][p.REPEAT]=4
        project=p.capture(patch,44100);self.assertEqual(project['payload']['patch']['memory'][p.TRIGGER],0)
        self.assertEqual(project['payload']['patch']['memory'][p.COUNT+1],0)

if __name__=='__main__':unittest.main()
