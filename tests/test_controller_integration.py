#!/usr/bin/env python3
"""Real ysfx/API integration, no synthetic replacement for the MIDI scheduler."""
import sys,time,json,urllib.request
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'headless'))
from controller_config import decode
from test_headless_mvp import HeadlessTests
class ControllerTests(HeadlessTests):
    def setUp(self):
        super().setUp()
        state=decode(self.call()['controllerEngine'])
        for b in state['mappings']:self.command('mapping_delete',mappingId=b['id'])
        for s in state['sources']:self.command('controller_forget',sourceId=s['id'])
        self.command('instrument_route',instrumentId=1,field='level',value=100)
    def mapping(self,**kw):
        m=dict(id=1,sourceId=101,targetId=201,instrumentId=1,moduleId=0,kind=1,points=[[0,0,0],[1,1,0]])
        m.update(kw);return self.command('mapping_commit',mapping=m)
    def source(self,id=101,**kw):return self.command('controller_source',sourceId=id,**kw)
    def cc(self,v,**kw):return self.command('midi_cc',channel=2,number=21,value=v,**kw)
    def test_controller_direct_glide_return_and_base(self):
        self.source(kind=2,channel=2,number=21)
        self.mapping(takeover=2,glideSeconds=.2,returnMode=1,idleSeconds=.25,returnSeconds=.15)
        self.cc(0)
        time.sleep(.1);mid=self.call()['instruments'][0]['level'];self.assertGreater(mid,0);self.assertLess(mid,100)
        time.sleep(.14);self.assertLess(self.call()['instruments'][0]['level'],5)
        time.sleep(.25);self.assertEqual(self.call()['instruments'][0]['level'],100)
        self.command('instrument_route',instrumentId=1,field='level',value=64)
        self.cc(127);time.sleep(.5);self.assertEqual(self.call()['instruments'][0]['level'],64)
    def test_learn_isolation_conflict_cancel_forget(self):
        self.source();self.source(102)
        self.command('controller_learn',sourceId=101);self.cc(30)
        sources=decode(self.call()['controllerEngine'])['sources'];self.assertEqual(next(s for s in sources if s['id']==101)['number'],21);self.assertEqual(next(s for s in sources if s['id']==102)['kind'],0)
        self.command('controller_learn',sourceId=102);self.cc(45)
        self.assertEqual(self.call()['controllerLearn']['conflict'],101)
        self.command('controller_cancel',sourceId=102)
        self.assertEqual(next(s for s in decode(self.call()['controllerEngine'])['sources'] if s['id']==101)['kind'],2)
        self.command('controller_learn',sourceId=102);self.cc(45);self.command('controller_confirm',sourceId=102)
        sources=decode(self.call()['controllerEngine'])['sources'];self.assertEqual(next(s for s in sources if s['id']==101)['kind'],0);self.assertEqual(next(s for s in sources if s['id']==102)['kind'],2)
        self.command('controller_forget',sourceId=101)
        self.assertEqual(next(s for s in decode(self.call()['controllerEngine'])['sources'] if s['id']==102)['kind'],2)
        self.command('controller_learn',sourceId=101)
        before=self.call()['midiCount'];self.command('midi',channel=1,note=72,value=100)
        self.assertEqual(self.call()['controllerLearn']['conflict'],-1)
        self.command('controller_confirm',sourceId=101,expected=400)
        self.command('controller_cancel',sourceId=101)
        self.command('midi',channel=1,note=72,value=0);self.assertEqual(self.call()['midiCount'],before)
    def test_pickup_wait_and_crossing(self):
        self.source(kind=2,channel=2,number=21);self.mapping(takeover=1,threshold=.02)
        self.cc(50);state=self.call();self.assertEqual(state['instruments'][0]['level'],100)
        self.assertTrue(state['controllerRuntime'][0]['pickup'])
        self.cc(102);self.assertEqual(self.call()['instruments'][0]['level'],102)
        self.assertEqual(self.call()['controllerRuntime'][0]['owner'],1)

    def test_cc_release_returns_without_zero_jump(self):
        self.source(kind=2,channel=2,number=21);self.mapping(returnMode=2,returnSeconds=.1)
        self.cc(127);state=self.cc(0);self.assertGreater(state['instruments'][0]['level'],120)
        time.sleep(.15);self.assertEqual(self.call()['instruments'][0]['level'],100)
        self.assertEqual(self.call()['controllerRuntime'][0]['owner'],0)

    def test_extra_instance_and_held_pending_base(self):
        self.source(kind=2,channel=2,number=21)
        first=self.command('module_structure',instrumentId=1,operation='add',engineType=1)['instruments'][0]['transformers'][-1]
        second=self.command('module_structure',instrumentId=1,operation='add',engineType=1)['instruments'][0]['transformers'][-1]
        self.command('midi',channel=1,note=60,value=90)
        self.command('module_commit',instrumentId=1,moduleId=second['id'],parameters=[dict(kind=7,value=12)])
        self.mapping(moduleId=second['id'],kind=7)
        binding=decode(self.call()['controllerEngine'])['mappings'][0]
        self.assertAlmostEqual(binding['base'],.625)
        self.command('midi',channel=1,note=60,value=0)
        result=self.command('midi',channel=1,note=60,value=90)
        self.assertEqual(result['lastEvent'][2],72)
        self.command('midi',channel=1,note=60,value=0)
        for tf in (first,second):self.command('module_structure',instrumentId=1,moduleId=tf['id'],operation='delete')

    def test_independent_phrase_decay_targets(self):
        self.source(kind=2,channel=2,number=21)
        self.mapping(kind=14)
        self.mapping(id=2,targetId=202,instrumentId=2,kind=15)
        before=self.call()['phrases'];self.cc(0)
        after=self.call()['phrases']
        self.assertEqual(after[0]['timeDecay'],.5);self.assertAlmostEqual(after[1]['velocityDecay'],.2)
        self.assertEqual(after[2],before[2]);self.assertEqual(after[0]['events'],before[0]['events'])
        self.patch('save');self.patch('load');restored=self.call()['phrases']
        self.assertEqual(restored[0]['timeDecay'],1);self.assertEqual(restored[1]['velocityDecay'],1)
        self.cc(127);after=self.call()['phrases'];self.assertEqual(after[0]['timeDecay'],2);self.assertEqual(after[1]['velocityDecay'],1)

    def test_learn_keeps_preexisting_note_off_safe(self):
        self.source()
        self.command('midi',channel=1,note=61,value=90)
        self.assertGreater(self.call()['activeNotes'],0)
        self.command('controller_learn',sourceId=101)
        self.command('midi',channel=1,note=61,value=0)
        self.assertEqual(self.call()['activeNotes'],0)
        self.assertEqual(self.call()['controllerLearn']['target'],101)
        self.command('controller_cancel',sourceId=101)

    def patch(self,action,slot=1,expected=200):
        state=self.call();body=dict(slot=slot,expectedRevision=state['revision'],expectedEngineSessionId=state['engineSessionId'])
        req=urllib.request.Request(self.base+'/api/v1/patch/'+action,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
        try:r=urllib.request.urlopen(req,timeout=10)
        except urllib.error.HTTPError as error:r=error
        self.assertEqual(r.status,expected);return json.load(r)
    def test_persistence_base_not_runtime_and_invalid_atomic_load(self):
        self.source(kind=2,channel=2,number=21);self.mapping();self.cc(0)
        self.assertEqual(self.call()['instruments'][0]['level'],0);self.patch('save');self.patch('export')
        exported=json.loads((Path(self.temp.name)/'patches/patch1-reaper.json').read_text());self.assertNotIn('controllerEngine',exported)
        self.assertTrue(json.loads((Path(self.temp.name)/'patches/patch1.json').read_text())['controllerEngine'])
        self.command('controller_forget',sourceId=101);self.patch('load')
        self.assertEqual(self.call()['instruments'][0]['level'],100)
        self.cc(127);self.assertEqual(self.call()['instruments'][0]['level'],127)
        path=Path(self.temp.name)/'patches/patch1.json';patch=json.loads(path.read_text());patch['controllerEngine']['configuration'][65+3]=999
        path.write_text(json.dumps(patch));self.patch('load',expected=400)
        self.assertEqual(self.call()['instruments'][0]['level'],127)
        self.assertEqual(decode(self.call()['controllerEngine'])['mappings'][0]['instrumentId'],1)
        patch['controllerEngine']['configuration'][65+17]=1000000000;path.write_text(json.dumps(patch));self.patch('load',expected=400)
        self.assertEqual(self.call()['instruments'][0]['level'],127)
    def test_two_targets_curve_output_and_delete_ownership(self):
        self.source(kind=2,channel=2,number=21)
        state=self.command('module_structure',instrumentId=1,operation='add',engineType=1);tf=state['instruments'][0]['transformers'][-1]
        self.mapping();self.mapping(id=2,targetId=202,moduleId=tf['id'],kind=7,points=[[0,0,0],[.5,.75,0],[1,1,0]])
        self.cc(64)
        result=self.command('midi',channel=1,note=60,value=90)
        self.assertEqual(result['lastEvent'][2],84)
        self.command('midi',channel=1,note=60,value=0)
        self.command('module_structure',instrumentId=1,moduleId=tf['id'],operation='delete');time.sleep(.02)
        self.assertEqual(len(decode(self.call()['controllerEngine'])['mappings']),1)
        self.command('panic');self.assertTrue(all(r['owner']==0 for r in self.call()['controllerRuntime']))
if __name__=='__main__':
    import unittest
    # Run integration cases only; baseline suite is run by combined-test.py.
    tests=[name for name in ControllerTests.__dict__ if name.startswith('test_')]
    result=unittest.TextTestRunner().run(unittest.TestSuite(ControllerTests(name) for name in tests));sys.exit(not result.wasSuccessful())
