import copy
import unittest
from test_block_edit import fixture, model, switches
from switch_model import add_switch
from native_capacity import layout


class NewSwitch(unittest.TestCase):
    def test_new_switch_is_one_empty_step_and_preserves_existing_data(self):
        before=fixture(); original=copy.deepcopy(before)
        after, identity=add_switch(before)
        self.assertEqual(before,original)
        self.assertEqual(identity,5)
        owner=next(s for s in model(after)['switches'] if s['switchId']==identity)
        self.assertEqual(len(owner['steps']),1)
        self.assertIsNone(owner['steps'][0]['layers'][0]['block'])
        for ident, old in switches(before).items():
            self.assertEqual(switches(after)[ident],old)
        self.assertEqual(model(after)['switches'][:-1],model(before)['switches'])
        self.assertEqual(model(after)['sources'],model(before)['sources'])
        self.assertEqual(after['globalSnapshots'],before['globalSnapshots'])

    def test_reused_primary_slot_preserves_shared_phrase_controller_settings(self):
        before=fixture();c=layout(before);b=c['SW_LEGACY_PAYLOAD']+1
        before['memory'][b+20]=0
        after, identity=add_switch(before)
        self.assertEqual(switches(after)[identity]['slot'],0)
        for offset in list(range(24,32))+list(range(112,120)):
            self.assertEqual(after['memory'][b+offset],before['memory'][b+offset])

    def test_full_capacity_refuses_without_mutation(self):
        patch=fixture();c=layout(patch)
        for slot in range(4,c['SW_COUNT']):
            b=c['DS_LEGACY_PAYLOAD']+2+(slot-4)*128
            for offset,value in {0:1,7:300,8:800,20:1,21:slot+1}.items():patch['memory'][b+offset]=value
        original=copy.deepcopy(patch)
        with self.assertRaisesRegex(ValueError,'capacity'):add_switch(patch)
        self.assertEqual(patch,original)

if __name__=='__main__':unittest.main()
