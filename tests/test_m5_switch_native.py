import sys
from test_headless_mvp import HeadlessTests
from test_conductor_persistence import Control
import unittest


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

if __name__=='__main__':
    suite=unittest.TestSuite([NewSwitchNative('test_create_empty_conductor_and_recall_preserves_it')])
    sys.exit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
