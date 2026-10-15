#!/usr/bin/env python3
"""M1 source metadata through actual native configuration/save/load paths."""
import copy,sys,unittest
from test_conductor_execution_native import Execution
from test_conductor_persistence import step,block
import conductor
class Groups(Execution):
    def test_source_groups_roundtrip_and_warning(self):
        old=copy.deepcopy(self.model);model=conductor.with_mute_groups(old)
        self.assertEqual(self.model,old,'migration must not mutate old document')
        for s in model['sources'][:2]:s['muteGroup']=7
        model['switches'][0]['steps']=[step([block(model['sources'][1]['id']),block(model['sources'][0]['id'])])]
        warning=conductor.mute_group_warnings(model)
        self.assertEqual(warning[0]['winnerPhraseId'],1)
        self.commit(model);self.press()
        self.assertEqual([i['phraseId'] for i in self.call()['instances']],[1],'native compiled winner independent of layer order')
        self.command('panic');self.patch('save');self.patch('load')
        state=self.call();patch=self.c.request(op=4,revision=state['revision'],session=state['engineSessionId'])
        self.assertEqual(conductor.decode(patch['conductor']),model)
        self.assertFalse(self.call()['instances'],'LOAD must not play')
        # Changing only SOURCE group removes the warning and admits both layers.
        model['sources'][1]['muteGroup']=8
        self.assertFalse(conductor.mute_group_warnings(model));self.commit(model);self.press()
        self.assertEqual({i['phraseId'] for i in self.call()['instances']},{1,2})
    def test_patch_banks_portable_and_fresh_engine(self):
        import subprocess,time
        from pathlib import Path
        from test_headless_mvp import BINARY,ROOT,HeadlessTests
        from server import Control
        import portable_project
        model=conductor.with_mute_groups(self.model)
        for source in model['sources'][:2]:source['muteGroup']=7
        self.commit(model);HeadlessTests.patch(self,'save',slot=1)
        other=copy.deepcopy(model);other['sources'][0]['muteGroup']=0
        self.commit(other);HeadlessTests.patch(self,'save',slot=2)
        HeadlessTests.patch(self,'load',slot=1)
        state=self.call();patch=self.c.request(op=4,revision=state['revision'],session=state['engineSessionId'])
        self.assertEqual(conductor.decode(patch['conductor']),model)
        project=portable_project.capture(patch,48000)
        self.assertEqual(conductor.decode(portable_project.materialize(project,96000)['conductor']),model)
        HeadlessTests.patch(self,'load',slot=2)
        state=self.call();other_patch=self.c.request(op=4,revision=state['revision'],session=state['engineSessionId'])
        self.assertEqual(conductor.decode(other_patch['conductor']),other)
        fresh_socket=str(Path(self.temp.name)/'fresh.sock')
        process=subprocess.Popen([BINARY,str(ROOT/'midi_human_looper.jsfx'),fresh_socket,'--chain'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            self.wait_for(lambda:Path(fresh_socket).exists(),'fresh native engine')
            fresh=Control(fresh_socket)
            def send(**args):
                state=fresh.request();result=fresh.request(revision=state['revision'],session=state['engineSessionId'],**args);self.assertEqual(result['status'],'ok');return result
            send(op=5,target=7,patch=patch)
            self.assertFalse(fresh.request()['instances'],'restart/LOAD must not start sources')
            send(op=6,target=0);send(op=6,target=1)
            self.assertEqual([i['phraseId'] for i in fresh.request()['instances']],[2])
        finally:
            process.terminate();out,err=process.communicate(timeout=5)
            self.assertNotIn('AddressSanitizer',err)
    def test_version_three_preserves_movement_execution(self):
        from test_movement_persistence import movement
        model=conductor.with_mute_groups(self.model)
        movement_source=movement();movement_source['duration']=30
        model['movements']=[movement_source];model['sources'][0]['muteGroup']=7
        self.commit(model);self.command('movement_preview',movementId=movement_source['id'])
        self.assertEqual(self.call()['movements']['active'],1,'v3 must still prepare real MOVEMENT engine')
        self.command('phrase_play',phraseId=1)
        self.assertEqual(self.call()['movements']['active'],1,'phrase group must not cancel independent MOVEMENT')
        self.command('panic');self.assertEqual(self.call()['movements']['active'],0)
    def test_invalid_group_rollback_and_direct_sources(self):
        model=conductor.with_mute_groups(self.model)
        for s in model['sources'][:2]:s['muteGroup']=9
        self.commit(model)
        before=self.call()['revision'];bad=copy.deepcopy(model);bad['sources'][0]['muteGroup']=-1
        self.command('conductor_commit',conductor=bad,expected=400)
        self.assertEqual(self.call()['revision'],before)
        self.command('phrase_play',phraseId=1);self.command('phrase_play',phraseId=3)
        self.assertEqual({i['phraseId'] for i in self.call()['instances']},{1,3})
        self.command('phrase_play',phraseId=2)
        self.assertEqual({i['phraseId'] for i in self.call()['instances']},{2,3})
        self.command('panic');self.assertFalse(self.call()['instances'])
if __name__=='__main__':
    suite=unittest.TestSuite(Groups(n) for n in ('test_source_groups_roundtrip_and_warning','test_invalid_group_rollback_and_direct_sources','test_version_three_preserves_movement_execution','test_patch_banks_portable_and_fresh_engine'))
    sys.exit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
