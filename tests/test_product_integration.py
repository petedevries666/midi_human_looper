#!/usr/bin/env python3
"""Real engine workflow: instance isolation, deletion ownership and saved IDs."""
import sys,unittest,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'headless'))
from controller_config import decode
from test_snapshots import SnapshotTests
class ProductTests(SnapshotTests):
    def test_instrument_lifecycle_snapshot_controller_and_reload(self):
        initial=self.call()['instruments']
        self.assertEqual([i['id'] for i in initial],[1,2,3])
        self.assertTrue(all(not i['transformers'] for i in initial))
        self.command('phrase_learn',phraseId=2)
        before=self.call()['midiCount']
        self.command('midi',channel=2,note=89,value=100)
        state=self.call()
        self.assertEqual((state['phrases'][1]['triggerNote'],state['phrases'][1]['triggerChannel']),(89,2))
        self.assertEqual(state['midiCount'],before)
        self.command('midi',channel=2,note=89,value=0)
        self.command('midi',channel=2,note=89,value=100)
        self.assertEqual(self.call()['lastEvent'][2],64)
        self.command('midi',channel=2,note=89,value=0)
        self.command('panic')
        self.command('phrase_learn',phraseId=2)
        self.command('controller_source',sourceId=103,kind=1,channel=2,number=89,expected=400)
        self.command('phrase_learn_cancel',phraseId=2)
        self.command('phrase_learn',phraseId=1)
        self.command('midi',channel=2,note=89,value=100)
        self.assertEqual(self.call()['controllerLearn']['conflict'],-1)
        self.command('phrase_learn_cancel',phraseId=1)
        self.command('midi',channel=2,note=89,value=0)
        self.assertEqual(self.call()['phrases'][1]['triggerNote'],89)
        self.command('controller_source',sourceId=1,kind=1,channel=4,number=90)
        self.command('phrase_learn',phraseId=1)
        self.command('midi',channel=4,note=90,value=100)
        self.assertEqual(self.call()['controllerLearn']['conflict'],1) # Separate target domains, even with equal IDs.
        self.command('phrase_learn_confirm',phraseId=1)
        self.command('midi',channel=4,note=90,value=0)
        self.assertEqual(self.call()['phrases'][0]['triggerNote'],90)
        self.assertFalse(next(source for source in decode(self.call()['controllerEngine'])['sources'] if source['id']==1)['kind'])
        self.command('controller_source',sourceId=101,kind=2,channel=3,number=22)
        for mapping,kind,target in ((201,1,301),(202,14,302)):
            self.command('mapping_commit',mapping=dict(id=mapping,sourceId=101,targetId=target,
                instrumentId=1,moduleId=0,kind=kind,points=[[0,0,0],[1,1,0]]))
        snapshot=self.capture()
        self.command('parameter_set',targetId=1,kind=1,value=61)
        state=self.call()
        self.assertEqual(state['instruments'][0]['level'],61)
        self.assertEqual(state['instruments'][1]['level'],initial[1]['level'])
        self.command('module_structure',instrumentId=1,operation='add',engineType=1)
        module=self.call()['instruments'][0]['transformers'][0]['id']
        self.command('module_commit',instrumentId=1,moduleId=module,parameters=[dict(kind=7,value=12)])
        self.command('midi',channel=1,note=67,value=100)
        self.assertEqual(self.call()['lastEvent'][2],79)
        self.command('midi',channel=1,note=67,value=0)
        self.command('module_structure',instrumentId=1,operation='add',engineType=2)
        range_module=self.call()['instruments'][0]['transformers'][-1]['id']
        self.command('module_commit',instrumentId=1,moduleId=range_module,parameters=[dict(kind=8,value=3),dict(kind=9,value=75),dict(kind=10,value=127)])
        self.command('module_structure',instrumentId=1,moduleId=range_module,operation='up',expected=400)
        self.command('module_structure',instrumentId=1,operation='add',engineType=1)
        extra=self.call()['instruments'][0]['transformers'][-1]['id']
        self.command('module_structure',instrumentId=1,moduleId=extra,operation='bypass')
        self.assertTrue(self.call()['instruments'][0]['serialPitchOrder'])
        self.command('module_structure',instrumentId=1,moduleId=range_module,operation='up')
        before=self.call()['midiCount']
        self.command('midi',channel=1,note=67,value=100)
        self.assertEqual(self.call()['midiCount'],before) # Range precedes transpose.
        self.command('midi',channel=1,note=67,value=0)
        self.command('module_structure',instrumentId=1,moduleId=range_module,operation='down')
        self.command('midi',channel=1,note=67,value=100)
        self.assertEqual(self.call()['lastEvent'][2],79)
        before=self.call()['midiCount']
        self.command('instrument_delete',instrumentId=1)
        self.assertGreater(self.call()['midiCount'],before)
        self.command('midi',channel=1,note=67,value=0)
        state=self.call()
        self.assertEqual([i['id'] for i in state['instruments']],[2,3])
        self.assertEqual([m['id'] for m in decode(state['controllerEngine'])['mappings']],[202])
        import json,urllib.request
        detail=json.load(urllib.request.urlopen(self.base+'/api/v1/snapshot/'+str(snapshot['id'])))
        own=[p for p in detail['parameters'] if p['instrumentId']==1]
        self.assertTrue(own)
        self.assertTrue(all(p['kind'] in (14,15,17,18,19,20) for p in own))
        self.command('instrument_add')
        added=next(i for i in self.call()['instruments'] if i['id'] not in (2,3))
        self.assertGreater(added['id'],3)
        self.assertFalse(added['transformers'])
        self.patch('save');self.patch('load')
        self.assertEqual([i['id'] for i in self.call()['instruments']],[added['id'],2,3])
        self.command('snapshot_recall',snapshotId=snapshot['id'])
        self.assertEqual(self.call()['instruments'][0]['level'],127)
        for i in list(self.call()['instruments']):self.command('instrument_delete',instrumentId=i['id'])
        self.assertEqual(self.call()['instruments'],[])
        self.command('instrument_add')
        self.assertGreater(self.call()['instruments'][0]['id'],added['id'])
        self.command('panic');self.assertEqual(self.call()['activeNotes'],0)
        self.patch('save')
        path=Path(self.temp.name)/'patches/patch1.json'
        future=json.loads(path.read_text());future['futureTransformerConfiguration']={'version':99,'instances':[{'id':'keep-me'}]}
        original=json.dumps(future).encode();path.write_bytes(original)
        import urllib.error
        for action in ('load','save'):
            with self.assertRaises(urllib.error.HTTPError) as rejected:self.patch(action)
            self.assertEqual(rejected.exception.code,422)
            self.assertEqual(path.read_bytes(),original)

if __name__=='__main__':
    result=unittest.TextTestRunner().run(unittest.TestSuite([ProductTests('test_instrument_lifecycle_snapshot_controller_and_reload')]))
    sys.exit(not result.wasSuccessful())
