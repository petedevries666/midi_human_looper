"""Instrument/host identity and MIDI-channel synchronization; no JACK operations."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'headless'))
from zynthian_chains import ChainLinks, Bridge, bridge_request


def chain(number, channel=0, name='Piano', engine='JV/synthv1', processor=3):
    return types.SimpleNamespace(chain_id=number, midi_chan=channel,
        synth_slots=[[types.SimpleNamespace(id=processor, eng_code=engine)]],
        midi_slots=[], get_title=lambda: name)


class Control:
    def __init__(self):
        self.state = dict(status='ok', revision=1, engineSessionId=123,
            instruments=[dict(id=1, name='', output=0, input=0, level=127, enabled=1)])
        self.commands = []
    def request(self, **args):
        if not args:return copy.deepcopy(self.state)
        self.commands.append(args)
        if args['revision'] != self.state['revision'] or args['session'] != self.state['engineSessionId']:
            return {'status': 'conflict'}
        instrument=next(i for i in self.state['instruments'] if i['id']==args['target'])
        if args['op'] == 9:instrument['output'] = args['value']
        elif args['op'] == 36:instrument['name'] = args['name']
        else:raise AssertionError('Unexpected engine mutation')
        self.state['revision'] += 1
        return {'status': 'ok'}


class LinksTest(unittest.TestCase):
    def setUp(self):
        self.manager = types.SimpleNamespace(chains={2: chain(2)}, will_midi_howl=lambda a,b: False)
        self.control = Control()
        self.links = ChainLinks(self.manager, 1, self.control)
    def bind(self, identity=None):
        status = self.links.status()
        if identity is None:identity = status['chains'][0]['identity']
        return self.links.bind(1, identity, status['inventoryRevision'], status['engineRevision'], status['engineSessionId'])
    def test_explicit_binding_tracks_name_and_channel_without_touching_other_parameters(self):
        self.assertEqual(self.control.commands, [])
        self.assertEqual(self.bind()['bindings']['1']['status'], 'synchronized')
        self.assertEqual(self.control.state['instruments'][0],dict(id=1,name='Piano',output=1,input=0,level=127,enabled=1))
        self.manager.chains[2].midi_chan = 4
        self.manager.chains[2].get_title = lambda:'Bass'
        self.links.synchronize()
        self.assertEqual(self.control.state['instruments'][0]['output'],5)
        self.assertEqual(self.control.state['instruments'][0]['name'],'Bass')
        self.assertTrue(all(c['op'] in (9,36) for c in self.control.commands))
        self.assertFalse(self.links.status()['routesManaged'])
    def test_deleted_and_recycled_chain_id_never_rebinds(self):
        self.bind();identity=self.links.snapshot()['1'];self.control.commands.clear()
        self.manager.chains[2]=chain(2)  # Same IDs, processor and engine; different object.
        self.links.synchronize()
        self.assertNotEqual(self.links.status()['chains'][0]['identity'],identity)
        self.assertEqual(self.links.status()['bindings']['1']['status'],'destination-unavailable')
        self.assertEqual(self.control.commands,[])
    def test_snapshot_restores_identity_only_for_matching_chain_signature(self):
        self.bind();saved=self.links.snapshot();identities=self.links.identities()
        manager=types.SimpleNamespace(chains={2:chain(2)},will_midi_howl=lambda a,b:False)
        restored=ChainLinks(manager,1,self.control,saved,identities)
        self.assertEqual(restored.status()['bindings']['1']['status'],'synchronized')
        manager.chains[2]=chain(2,processor=77)
        restored=ChainLinks(manager,1,self.control,saved,identities)
        self.assertEqual(restored.status()['bindings']['1']['status'],'destination-unavailable')
    def test_performance_and_armed_capture_defer_automatic_updates(self):
        self.bind()
        for key,value in [('activeNotes',1),('chainRecording',1),('chainArmed',1),('chainRunning',1),('instances',[1]),('movements',{'active':1}),('targetSnapshotId',12)]:
            with self.subTest(key=key):
                self.manager.chains[2].midi_chan=6
                self.control.state[key]=value;self.control.commands.clear()
                self.links.synchronize();self.assertEqual(self.control.commands,[])
                self.assertEqual(self.links.status()['bindings']['1']['status'],'pending')
                self.control.state.pop(key)
        self.links.synchronize();self.assertEqual(self.control.state['instruments'][0]['output'],7)
    def test_stale_inventory_or_engine_generation_rejected(self):
        status=self.links.status();identity=status['chains'][0]['identity']
        for args in [('old',status['engineRevision'],123),(status['inventoryRevision'],999,123),(status['inventoryRevision'],status['engineRevision'],456)]:
            with self.assertRaises(ValueError):self.links.bind(1,identity,*args)
        self.assertEqual(self.links.snapshot(),{})
    def test_new_link_refused_while_armed(self):
        self.control.state['chainArmed']=1
        with self.assertRaises(ValueError):self.bind()
        self.assertEqual(self.links.snapshot(),{})
    def test_all_channel_destination_requires_explicit_fixed_channel(self):
        self.manager.chains[2].midi_chan=65535
        with self.assertRaises(ValueError):self.bind()
        self.assertEqual(self.control.commands,[])
    def test_mb_containing_self_and_feedback_chains_excluded(self):
        self.manager.chains[1]=chain(1)
        self.manager.chains[3]=chain(3)
        self.manager.chains[3].midi_slots=[[types.SimpleNamespace(eng_code='MB')]]
        self.manager.chains[4]=chain(4)
        self.manager.will_midi_howl=lambda a,b:b==4
        self.assertEqual([c['chainId'] for c in self.links.status()['chains']],[2])
    def test_unlink_retains_musical_settings(self):
        self.bind();before=copy.deepcopy(self.control.state['instruments'])
        s=self.links.status();self.links.bind(1,None,s['inventoryRevision'],s['engineRevision'],s['engineSessionId'])
        self.manager.chains[2].midi_chan=5;self.links.synchronize()
        self.assertEqual(self.control.state['instruments'],before)
        self.assertEqual(self.links.snapshot(),{})
    def test_idle_unlinked_bridge_does_not_observe_engine(self):
        def forbidden(**args):raise AssertionError('Unlinked idle bridge queried engine')
        self.control.request=forbidden;self.links.mixer=object()
        self.links.synchronize();self.links.synchronize_mixer()
    def test_relink_by_channel_preserves_input_and_refuses_ambiguity(self):
        self.control.state['instruments'][0].update(output=1,input=14)
        s=self.links.status();result=self.links.relink_channels(s['inventoryRevision'],s['engineRevision'],s['engineSessionId'])
        self.assertEqual(result['relinkReport'][0]['status'],'linked')
        self.assertEqual(self.control.state['instruments'][0]['input'],14)
        self.links.bindings.clear();self.manager.chains[3]=chain(3)
        s=self.links.status();result=self.links.relink_channels(s['inventoryRevision'],s['engineRevision'],s['engineSessionId'])
        self.assertEqual(result['relinkReport'][0]['status'],'ambiguous');self.assertEqual(self.links.bindings,{})
    def test_relink_missing_original_channel_and_busy_are_safe(self):
        s=self.links.status();result=self.links.relink_channels(s['inventoryRevision'],s['engineRevision'],s['engineSessionId'])
        self.assertEqual(result['relinkReport'][0]['status'],'missing');self.assertEqual(self.links.bindings,{})
        self.control.state['activeNotes']=1;s=self.links.status()
        with self.assertRaises(ValueError):self.links.relink_channels(s['inventoryRevision'],s['engineRevision'],s['engineSessionId'])
        self.assertEqual(self.links.bindings,{})
    def test_two_instruments_follow_distinct_destinations_independently(self):
        self.control.state['instruments'].append(dict(id=2,name='',output=0,input=0,level=100,enabled=1))
        self.manager.chains[3]=chain(3,channel=5,name='Bass',processor=4)
        self.bind()
        s=self.links.status();destination=next(c for c in s['chains'] if c['chainId']==3)
        self.links.bind(2,destination['identity'],s['inventoryRevision'],s['engineRevision'],s['engineSessionId'])
        self.assertEqual([(i['name'],i['output'],i['level']) for i in self.control.state['instruments']],[('Piano',1,127),('Bass',6,100)])
        self.manager.chains[3].midi_chan=8;self.links.synchronize()
        self.assertEqual([i['output'] for i in self.control.state['instruments']],[1,9])
    def test_native_name_limit_does_not_truncate_host_inventory(self):
        self.manager.chains[2].get_title=lambda:'Très long nom de chaîne avec accents'
        self.bind()
        self.assertLessEqual(len(self.control.state['instruments'][0]['name']),16)
        self.assertIn('chaîne',self.links.status()['chains'][0]['name'])
    @unittest.skipIf(sys.platform=='win32','Production IPC uses Unix sockets on Zynthian')
    def test_local_bridge_round_trip_and_cleanup(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'host.sock';bridge=Bridge(path,self.links)
            try:
                state=bridge_request(path,{'action':'status'})
                self.assertEqual(state['chains'][0]['name'],'Piano')
                self.assertIn('error',bridge_request(path,{'action':'execute','path':'/tmp/no'}))
                self.assertEqual(path.stat().st_mode & 0o777,0o600)
            finally:bridge.close()
            self.assertFalse(path.exists())


class VolumeLinksTest(unittest.TestCase):
    bind=LinksTest.bind
    def setUp(self):
        LinksTest.setUp(self)
        self.levels={0:.7,1:.4,16:.9};self.writes=[]
        self.manager.chains[2].mixer_chan=0
        self.links.mixer=types.SimpleNamespace(MAX_NUM_CHANNELS=17,get_level=lambda i:self.levels[i],set_level=self.set_level)
        self.bind();self.control.commands.clear()
    def set_level(self,index,value):self.writes.append((index,value));self.levels[index]=value
    def volume(self,value,status=None):
        s=status or self.links.status();b=s['bindings']['1']
        return self.links.set_volume(1,b['identity'],value,b['volume'],s['inventoryRevision'],s['engineSessionId'])
    def test_two_way_mixer_without_midi_mutation(self):
        self.assertEqual(self.links.status()['bindings']['1']['volume'],.7)
        self.control.state['activeNotes']=3
        self.assertEqual(self.volume(.3)['bindings']['1']['volume'],.3)
        self.assertEqual(self.writes,[(0,.3)]);self.assertEqual(self.control.commands,[])
        self.levels[0]=.85;self.assertEqual(self.links.status()['bindings']['1']['volume'],.85)
    def test_stale_physical_fader_rejected(self):
        s=self.links.status();self.levels[0]=.2
        with self.assertRaises(ValueError):self.volume(.8,s)
        self.assertFalse(self.writes)
    def test_deleted_chain_and_main_bus_never_written(self):
        for index in (None,-1,16,17):
            self.manager.chains[2].mixer_chan=index
            with self.assertRaises(ValueError):self.volume(.5)
        self.assertFalse(self.writes)
    def test_session_and_identity_guard(self):
        s=self.links.status();self.control.state['engineSessionId']=999
        with self.assertRaises(ValueError):self.volume(.1,s)
        self.control.state['engineSessionId']=123
        self.manager.chains[2]=chain(2);self.manager.chains[2].mixer_chan=0
        with self.assertRaises(ValueError):self.volume(.1,s)
        self.assertFalse(self.writes)
    def test_shared_chain_has_one_volume(self):
        self.control.state['instruments'].append(dict(id=2,name='Piano',output=1,input=2,level=90,enabled=1))
        self.links.restore({'1':self.links.snapshot()['1'],'2':self.links.snapshot()['1']})
        status=self.volume(.25)
        self.assertEqual([v['volume'] for v in status['bindings'].values()],[.25,.25])
        self.assertEqual(self.control.state['instruments'][1]['level'],90)
    @unittest.skipIf(sys.platform=='win32','Production IPC uses Unix sockets on Zynthian')
    def test_volume_command_uses_bounded_bridge_protocol(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'host.sock';bridge=Bridge(path,self.links)
            try:
                status=bridge_request(path,{'action':'status'});binding=status['bindings']['1']
                result=bridge_request(path,dict(action='volume',instrumentId=1,identity=binding['identity'],value=.45,expectedVolume=binding['volume'],inventoryRevision=status['inventoryRevision'],expectedEngineSessionId=status['engineSessionId']))
                self.assertEqual(result['bindings']['1']['volume'],.45)
            finally:bridge.close()
    def test_invalid_values_and_failed_readback(self):
        for value in (-1,1.1,float('nan'),float('inf'),True):
            with self.assertRaises(ValueError):self.volume(value)
        self.links.mixer.set_level=lambda i,v:None
        with self.assertRaises(ValueError):self.volume(.5)

class PanLinksTest(unittest.TestCase):
    bind=LinksTest.bind
    set_level=VolumeLinksTest.set_level
    def setUp(self):
        VolumeLinksTest.setUp(self);self.pans={0:0.,1:.2,16:.1};self.pan_writes=[]
        self.links.mixer.get_balance=lambda i:self.pans[i]
        self.links.mixer.set_balance=self.set_pan
    def set_pan(self,index,value):self.pan_writes.append((index,value));self.pans[index]=value
    def pan(self,value,status=None):
        s=status or self.links.status();b=s['bindings']['1']
        return self.links.set_pan(1,b['identity'],value,b['pan'],s['inventoryRevision'],s['engineSessionId'])
    def test_left_center_right_and_native_readback_without_changing_volume_or_midi(self):
        for value in (-1,0,1,-.35):self.assertAlmostEqual(self.pan(value)['bindings']['1']['pan'],value)
        self.assertEqual(self.levels[0],.7);self.assertFalse(self.control.commands)
        self.pans[0]=.6;self.assertEqual(self.links.status()['bindings']['1']['pan'],.6)
    def test_invalid_stale_main_and_removed_destinations_fail_closed(self):
        for value in (-1.1,1.1,float('nan'),float('inf'),True):
            with self.assertRaises(ValueError):self.pan(value)
        old=self.links.status();self.pans[0]=.5
        with self.assertRaises(ValueError):self.pan(.1,old)
        self.manager.chains[2].mixer_chan=16
        with self.assertRaises(ValueError):self.pan(.1)
        self.assertFalse(self.pan_writes)
    @unittest.skipIf(sys.platform=='win32','Production IPC uses Unix sockets on Zynthian')
    def test_pan_bridge_protocol(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'host.sock';bridge=Bridge(path,self.links)
            try:
                s=bridge_request(path,{'action':'status'});b=s['bindings']['1']
                result=bridge_request(path,dict(action='pan',instrumentId=1,identity=b['identity'],value=-.4,expectedPan=b['pan'],inventoryRevision=s['inventoryRevision'],expectedEngineSessionId=s['engineSessionId']))
                self.assertEqual(result['bindings']['1']['pan'],-.4)
            finally:bridge.close()

if __name__=='__main__':unittest.main()
