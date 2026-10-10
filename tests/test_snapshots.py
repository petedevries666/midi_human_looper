#!/usr/bin/env python3
"""Actual native JSFX, command queue and HTTP snapshot capture tests."""
import sys,unittest,json,urllib.request,urllib.error,time,subprocess
from pathlib import Path
from test_headless_mvp import BINARY,ROOT
from test_headless_mvp import HeadlessTests
class SnapshotTests(HeadlessTests):
    def setUp(self):
        super().setUp()
        for a in self.call().get('snapshotActions',[]):
            self.command('snapshot_switch',switchId=a['switchId'],gesture=a['gesture'],snapshotAction=0)
        for r in self.call()['snapshots']:
            self.command('snapshot_delete',snapshotId=r['id'])
    def capture(self):
        return self.command('snapshot_capture')['snapshots'][-1]
    def test_capture_live_dirty_update_independence(self):
        self.command('instrument_route',instrumentId=1,field='level',value=64)
        self.command('midi',channel=1,note=60,value=100)
        before=self.call()['midiCount']
        a=self.capture();self.assertGreaterEqual(a['parameterCount'],35)
        self.assertFalse(a['dirty']);self.assertEqual(a['name'],'SNAPSHOT 01')
        self.assertEqual(self.call()['midiCount'],before)
        renamed=self.command('snapshot_rename',snapshotId=a['id'],name='VERSE')['snapshots'][0]
        self.assertEqual(renamed['name'],'VERSE')
        b=self.command('snapshot_duplicate',snapshotId=a['id'])['snapshots'][-1]
        self.command('instrument_route',instrumentId=1,field='level',value=96)
        self.assertTrue(all(r['dirty'] for r in self.call()['snapshots']))
        after=self.command('snapshot_update',snapshotId=a['id'])['snapshots']
        self.assertFalse(after[0]['dirty']);self.assertTrue(after[1]['dirty'])
        self.command('midi',channel=1,note=60,value=0)
        self.assertNotEqual(a['id'],b['id'])
    def test_order_ids_deletion_and_capacity(self):
        a=self.capture();b=self.capture()
        ordered=self.command('snapshot_move',snapshotId=b['id'])['snapshots']
        self.assertEqual([r['id'] for r in ordered],[b['id'],a['id']])
        self.command('snapshot_delete',snapshotId=a['id'])
        c=self.capture();self.assertGreater(c['id'],b['id'])
        for _ in range(14):self.capture()
        self.assertEqual(len(self.call()['snapshots']),16)
        self.command('snapshot_capture',expected=400)
        self.command('snapshot_update',snapshotId=a['id'],expected=400)
    def test_missing_target_recall_applies_only_surviving_identities(self):
        self.command('instrument_route',instrumentId=1,field='level',value=32)
        tf=self.command('module_structure',instrumentId=1,operation='add',engineType=1)['instruments'][0]['transformers'][-1]
        a=self.capture()
        self.command('module_structure',instrumentId=1,moduleId=tf['id'],operation='delete')
        self.command('instrument_route',instrumentId=1,field='level',value=96)
        result=self.command('snapshot_recall',snapshotId=a['id'])
        self.assertEqual(result['snapshotSkippedTargets'],1)
        self.assertEqual(self.call()['instruments'][0]['level'],32)
    def test_transactional_settings_and_validation(self):
        a=self.capture()
        before=self.call()
        self.command('snapshot_commit',snapshotId=a['id'],name='FAST',seconds=.2,ease=0,switching=3)
        r=self.call()['snapshots'][0]
        self.assertEqual((r['name'],r['seconds'],r['ease'],r['switching']),('FAST',.2,0,3))
        self.command('snapshot_commit',snapshotId=a['id'],name='INVALID',seconds=31,ease=0,switching=3,expected=400)
        self.assertEqual(self.call()['snapshots'][0]['name'],'FAST')
        self.call(dict(protocolVersion=1,action='snapshot_commit',snapshotId=a['id'],name='STALE',seconds=1,ease=1,switching=2,expectedRevision=before['revision']),expected=409)
        self.assertEqual(self.call()['snapshots'][0]['name'],'FAST')
    def test_worker_restart_preserves_engine_capture(self):
        a=self.capture();self.stop_web();self.start_web()
        self.assertEqual(self.call()['snapshots'][0]['id'],a['id'])
    def test_instant_and_timed_recall_real_values(self):
        self.command('instrument_route',instrumentId=1,field='level',value=32)
        a=self.capture()
        self.command('instrument_route',instrumentId=1,field='level',value=112)
        b=self.capture()
        self.command('snapshot_recall',snapshotId=a['id'])
        self.assertEqual(self.call()['instruments'][0]['level'],32)
        self.command('snapshot_morph',snapshotId=b['id'])
        time.sleep(.6)
        mid=self.call()['instruments'][0]['level'];self.assertGreater(mid,32);self.assertLess(mid,112)
        self.command('snapshot_morph',snapshotId=a['id'])
        start=self.call()['instruments'][0]['level'];self.assertLessEqual(abs(start-mid),3)
        time.sleep(2.1);self.assertEqual(self.call()['instruments'][0]['level'],32)
    def test_physical_policy_takes_morph_target(self):
        self.command('controller_source',sourceId=101,kind=2,channel=2,number=21)
        mapping=dict(id=1,sourceId=101,targetId=202,instrumentId=1,moduleId=0,kind=1,priority=0,takeover=0,returnMode=0,threshold=.02,glideSeconds=.2,slewPerSecond=1,idleSeconds=1,returnSeconds=.5,easing=0,enabled=1,points=[[0,0,0],[1,1,0]])
        self.command('mapping_commit',mapping=mapping)
        self.command('midi_cc',channel=2,number=21,value=32);a=self.capture()
        self.command('midi_cc',channel=2,number=21,value=112);b=self.capture()
        self.command('snapshot_recall',snapshotId=a['id'])
        self.command('snapshot_morph',snapshotId=b['id']);time.sleep(.2)
        self.command('midi_cc',channel=2,number=21,value=64)
        time.sleep(.3);self.assertEqual(self.call()['instruments'][0]['level'],64)
        time.sleep(1.8);self.assertEqual(self.call()['instruments'][0]['level'],64)
        self.command('mapping_delete',mappingId=1)
    def test_stable_target_inclusion_is_transactional(self):
        self.command('instrument_route',instrumentId=1,field='level',value=32);a=self.capture()
        details=json.load(urllib.request.urlopen(self.base+'/api/v1/snapshot/'+str(a['id'])))
        volume=next(v for v in details['parameters'] if v['instrumentId']==1 and v['moduleId']==0 and v['kind']==1)
        self.assertEqual(volume['value'],32)
        mask=dict(instrumentId=1,moduleId=0,kind=1,included=False)
        self.command('snapshot_commit',snapshotId=a['id'],name=a['name'],seconds=2,ease=1,switching=2,inclusions=[mask])
        self.command('instrument_route',instrumentId=1,field='level',value=96)
        self.command('snapshot_recall',snapshotId=a['id'])
        self.assertEqual(self.call()['instruments'][0]['level'],96)
        self.assertFalse(self.call()['snapshots'][0]['dirty'])
        self.command('snapshot_update',snapshotId=a['id'])
        details=json.load(urllib.request.urlopen(self.base+'/api/v1/snapshot/'+str(a['id'])))
        self.assertFalse(next(v for v in details['parameters'] if v['instrumentId']==1 and v['moduleId']==0 and v['kind']==1)['included'])
        bad=dict(instrumentId=999,moduleId=0,kind=1,included=False)
        self.command('snapshot_commit',snapshotId=a['id'],name='INVALID',seconds=1,ease=0,switching=1,inclusions=[bad],expected=400)
        self.assertEqual(self.call()['snapshots'][0]['name'],a['name'])
    def test_switch_snapshot_gestures_hardware_and_test(self):
        self.command('instrument_route',instrumentId=1,field='level',value=32);a=self.capture()
        self.command('instrument_route',instrumentId=1,field='level',value=112);b=self.capture()
        for gesture,action,target in ((0,1,0),(1,3,b['id']),(2,4,a['id'])):
            self.command('snapshot_switch',switchId=1,gesture=gesture,snapshotAction=action,snapshotId=target)
        self.command('test',switchId=1,gesture='tap')
        self.wait_for(lambda:self.call()['instruments'][0]['level']==32,'snapshot NEXT via TEST')
        self.command('test',switchId=1,gesture='double')
        self.wait_for(lambda:self.call()['instruments'][0]['level']==112,'snapshot RECALL via DOUBLE TEST')
        self.command('snapshot_commit',snapshotId=a['id'],name='A',seconds=.1,ease=0,switching=2)
        self.command('test',switchId=1,gesture='hold')
        self.wait_for(lambda:self.call()['instruments'][0]['level']==32,'snapshot MORPH via HOLD TEST')
        switch=next(sw for sw in self.call()['switches'] if sw['id']==1)
        self.command('midi',channel=switch['channel'],note=switch['number'],value=100)
        self.wait_for(lambda:self.call()['instruments'][0]['level']==112,'snapshot NEXT hardware press')
        self.command('midi',channel=switch['channel'],note=switch['number'],value=0)
        self.command('snapshot_switch',switchId=2,gesture=0,snapshotAction=7)
        self.command('test',switchId=2,gesture='tap')
        self.wait_for(lambda:self.call()['instruments'][0]['level']==32,'independent MORPH PREVIOUS')
        time.sleep(.35) # Finish the previous independent single-tap window.
        for _ in range(2):
            self.command('midi',channel=switch['channel'],note=switch['number'],value=100)
            self.command('midi',channel=switch['channel'],note=switch['number'],value=0)
        self.wait_for(lambda:self.call()['instruments'][0]['level']==112,'hardware DOUBLE routing')
        self.command('snapshot_switch',switchId=1,gesture=2,snapshotAction=3,snapshotId=b['id'])
        self.command('midi',channel=switch['channel'],note=switch['number'],value=100)
        time.sleep(1)
        self.assertEqual(self.call()['instruments'][0]['level'],112)
        self.command('midi',channel=switch['channel'],note=switch['number'],value=0)
        for sw,gesture in ((1,0),(1,1),(1,2),(2,0)):
            self.command('snapshot_switch',switchId=sw,gesture=gesture,snapshotAction=0)
    def test_invalid_persistence_and_export_preserve_data(self):
        a=self.capture()
        def patch(action,expected=200):
            state=self.call();body=dict(slot=2,expectedRevision=state['revision'],expectedEngineSessionId=state['engineSessionId'])
            req=urllib.request.Request(self.base+'/api/v1/patch/'+action,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
            try:response=urllib.request.urlopen(req,timeout=5)
            except urllib.error.HTTPError as error:response=error
            self.assertEqual(response.status,expected);return json.load(response)
        patch('save');path=Path(self.temp.name)/'patches/patch2.json';saved=json.loads(path.read_text())
        patch('export',422);self.assertEqual(json.loads(path.read_text()),saved)
        saved['globalSnapshots']['configuration'][1]=0
        path.write_text(json.dumps(saved));before=self.call()
        patch('load',400);after=self.call()
        self.assertEqual(after['revision'],before['revision']);self.assertEqual(after['snapshots'],before['snapshots'])
        saved['globalSnapshots']['version']=99;path.write_text(json.dumps(saved));raw=path.read_bytes()
        patch('save',422);self.assertEqual(path.read_bytes(),raw)
    def test_patch_persistence_roundtrip(self):
        a=self.capture();self.command('snapshot_rename',snapshotId=a['id'],name='VERSE')
        self.command('snapshot_switch',switchId=1,gesture=0,snapshotAction=6)
        def patch(action):
            s=self.call();body=dict(slot=1,expectedRevision=s['revision'],expectedEngineSessionId=s['engineSessionId'])
            req=urllib.request.Request(self.base+'/api/v1/patch/'+action,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
            return json.load(urllib.request.urlopen(req,timeout=5))
        self.assertEqual(patch('save')['status'],'saved')
        self.command('snapshot_delete',snapshotId=a['id'])
        patch('load');restored=self.call()['snapshots'];self.assertEqual(restored[0]['name'],'VERSE')
        self.assertEqual(restored[0]['id'],a['id'])
        cls=type(self);cls.engine.terminate();cls.engine.communicate(timeout=5)
        cls.engine=subprocess.Popen([BINARY,str(ROOT/'midi_human_looper.jsfx'),cls.sock,'--demo'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        cls.wait_for(lambda:Path(cls.sock).exists(),'restarted native engine')
        self.wait_for(lambda:self.call().get('status')=='ok','new engine state')
        self.assertEqual(self.call()['snapshots'],[])
        patch('load');self.assertEqual(self.call()['snapshots'][0]['name'],'VERSE')
        self.assertEqual(self.call()['snapshots'][0]['id'],a['id'])
        self.assertEqual(self.call()['snapshotActions'][0]['action'],6)
        path=Path(self.temp.name)/'patches/patch1.json';legacy=json.loads(path.read_text())
        extension=legacy['globalSnapshots'];extension['version']=1
        extension['configuration']=extension['configuration'][:-192];extension['configuration'][0]=1
        path.write_text(json.dumps(legacy));patch('load')
        self.assertEqual(self.call()['snapshots'][0]['name'],'VERSE')
        self.assertEqual(self.call()['snapshotActions'],[])

if __name__=='__main__':
    cases=[n for n in SnapshotTests.__dict__ if n.startswith('test_')]
    r=unittest.TextTestRunner().run(unittest.TestSuite(SnapshotTests(n) for n in cases));sys.exit(not r.wasSuccessful())
