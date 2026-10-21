import sys
from test_headless_mvp import HeadlessTests
from test_conductor_persistence import Control
import unittest
from unittest.mock import patch as mock_patch
from pathlib import Path
import copy
import switch_presets


class NewSwitchNative(HeadlessTests):
    def test_create_empty_conductor_and_recall_preserves_it(self):
        before=self.call();ids={s['id'] for s in before['switches']}
        self.command('switch_add')
        state=self.call();new=next(s for s in state['switches'] if s['id'] not in ids)
        self.assertEqual(new['conductor']['steps'],1)
        self.assertEqual(new['kind'],0)
        self.command('test',switchId=new['id'])
        self.assertEqual(self.call()['switches'][-1]['conductor']['result'],0)
        self.command('panic')
        c=Control(self.sock);state=self.call()
        patch=c.request(op=4,revision=state['revision'],session=state['engineSessionId'])
        result=c.request(op=5,arg=1,target=patch['schema'],patch=patch,revision=state['revision'],session=state['engineSessionId'])
        self.assertEqual(result['status'],'ok')
        again=next(s for s in self.call()['switches'] if s['id']==new['id'])
        self.assertEqual(again['conductor']['steps'],1)
        self.assertEqual(again['conductor']['step'],0)
        # Utility presets remain applicable to the new empty placeholder.
        store=switch_presets.Store(Path(self.temp.name)/'utility-presets',c)
        store.directory.mkdir()
        config=copy.deepcopy(switch_presets.switches(patch)[new['id']]['config'])
        config['settings'][12]=2;config['name']='UTIL STOP'
        library=switch_presets.default_library();preset='11111111-1111-4111-8111-111111111111'
        library['presets'][preset]=dict(name='UTIL STOP',config=config,references={})
        switch_presets.atomic_json(store.path,library)
        def preview():
            state=self.call()
            return store.preview(dict(operation='apply',switchId=new['id'],presetId=preset,slot=1,
                expectedRevision=state['revision'],expectedEngineSessionId=state['engineSessionId']))
        review=preview();self.assertFalse(review['errors'])
        original_write=switch_presets.atomic_json;failed=[]
        def fail_once(path,data):
            if Path(path)==store.path and not failed:
                failed.append(True);raise OSError('test library write failure')
            return original_write(path,data)
        with mock_patch.object(switch_presets,'atomic_json',side_effect=fail_once):
            with self.assertRaises(OSError):store.execute(review['previewId'])
        restored=next(s for s in self.call()['switches'] if s['id']==new['id'])
        self.assertEqual(restored['conductor']['steps'],1,'failed preset write restores blank native model')
        review=preview();store.execute(review['previewId'])
        applied=next(s for s in self.call()['switches'] if s['id']==new['id'])
        self.assertEqual(applied['conductor']['steps'],0)
        self.assertEqual(applied['settings'][12],2)
        self.assertEqual(applied['name'],'UTIL STOP')

if __name__=='__main__':
    suite=unittest.TestSuite([NewSwitchNative('test_create_empty_conductor_and_recall_preserves_it')])
    sys.exit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
