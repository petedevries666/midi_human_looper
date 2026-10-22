"""Actual native worker/API integration; host snapshot APIs are fixtures only."""
import sys,unittest
import test_native_capacity as fixtures
from patch_recall import RecallService
from unittest.mock import patch
import types

class Dickinson(unittest.TestCase):
 setUpClass=classmethod(fixtures.Capacity.setUpClass.__func__)
 tearDownClass=classmethod(fixtures.Capacity.tearDownClass.__func__)
 export=classmethod(fixtures.Capacity.export.__func__)
 setUp=fixtures.Capacity.setUp
 load=fixtures.Capacity.load
 cmd=fixtures.Capacity.cmd
 wait=fixtures.Capacity.wait
 def test_session_loaded_identity_and_pc_noop(self):
  self.assertEqual(self.control.request()['loadedPatchSlot'],0)
  saved=self.export();s=self.control.request()
  reply=self.control.request(op=5,target=8,loaded_slot=7,patch=saved,revision=s['revision'],session=s['engineSessionId'])
  self.assertEqual(reply['status'],'ok');self.assertEqual(self.control.request()['loadedPatchSlot'],7)
  self.cmd('phrase_rename',phraseId=1,name='UNSAVED')
  s=self.control.request();self.control.request(op=3,ch=0,note=60,value=100,revision=s['revision'],session=s['engineSessionId'])
  before=self.wait(lambda s:s['activeNotes']>0)
  with patch('patch_recall.threading.Thread'):
   service=RecallService(types.SimpleNamespace(snapshot_dir=str(self.dir)),self.dir,self.dir/'patches',{1:dict(control=self.control)})
  for _ in range(10):service.recall(7,midi=True)
  after=self.control.request()
  for field in ('engineSessionId','revision','activeNotes','instances','loadedPatchSlot'):
   self.assertEqual(after[field],before[field],field)
  self.assertEqual(after['phrases'][0]['name'],'UNSAVED')
  bad=self.export();bad['globals'][0]=-1;s=self.control.request()
  self.assertNotEqual(self.control.request(op=5,target=8,loaded_slot=8,patch=bad,revision=s['revision'],session=s['engineSessionId'])['status'],'ok')
  self.assertEqual(self.control.request()['loadedPatchSlot'],7)
 def test_arp_controls_snapshots_and_migration(self):
  self.cmd('module_structure',instrumentId=1,operation='add',engineType=5)
  arp=next(t for t in self.control.request()['instruments'][0]['transformers'] if t['type']==5)
  def values():return {p['kind']:p['value'] for p in next(t for t in self.control.request()['instruments'][0]['transformers'] if t['id']==arp['id'])['parameters']}
  self.assertEqual((values()[27],values()[28]),(2,0))
  self.cmd('module_commit',instrumentId=1,moduleId=arp['id'],parameters=[dict(kind=k,value=v) for k,v in [(4,11),(5,8),(6,.5),(12,0),(3,1),(27,4),(28,1)]])
  self.assertEqual((values()[27],values()[28]),(4,1))
  self.cmd('snapshot_capture');snap=self.control.request()['snapshots'][-1]['id']
  self.cmd('parameter_set',targetId=1,moduleId=arp['id'],kind=27,value=1)
  self.cmd('parameter_set',targetId=1,moduleId=arp['id'],kind=28,value=0)
  self.cmd('snapshot_recall',snapshotId=snap)
  self.wait(lambda s:values()[27]==4 and values()[28]==1)
  patch=self.export();self.assertIn([1,4,1],[patch['nativeArp']['configuration'][i:i+3] for i in range(2,len(patch['nativeArp']['configuration']),3)])
  self.cmd('parameter_set',targetId=1,moduleId=arp['id'],kind=27,value=1)
  self.cmd('parameter_set',targetId=1,moduleId=arp['id'],kind=28,value=0)
  self.load(patch);self.assertEqual((values()[27],values()[28]),(4,1),'native LOAD must restore saved ARP state')
  self.assertEqual(self.export()['nativeArp'],patch['nativeArp'])
  old=dict(patch);old.pop('nativeArp');old.pop('globalSnapshots');self.load(old)
  self.assertEqual((values()[27],values()[28]),(2,0),'missing extension migrates old native patch neutrally')
  # Native worker rejects a well-shaped but missing stable destination atomically.
  bad=self.export();bad['nativeArp']={'version':1,'configuration':[1,1,16777000,4,1]}
  s=self.control.request();reply=self.control.request(op=5,target=8,patch=bad,revision=s['revision'],session=s['engineSessionId'])
  self.assertNotEqual(reply['status'],'ok');self.assertEqual((values()[27],values()[28]),(2,0))
 def test_arp_controller_ownership(self):
  self.cmd('module_structure',instrumentId=1,operation='add',engineType=5)
  arp=next(t for t in self.control.request()['instruments'][0]['transformers'] if t['type']==5)
  self.cmd('controller_source',sourceId=101,kind=2,channel=2,number=21)
  self.cmd('mapping_commit',mapping=dict(id=2,targetId=2,sourceId=101,instrumentId=1,moduleId=arp['id'],kind=27,enabled=1,points=[[0,0,0],[1,1,0]]))
  for value,want in ((0,1),(127,4)):
   self.cmd('midi_cc',channel=2,number=21,value=value)
   got=next(t for t in self.control.request()['instruments'][0]['transformers'] if t['id']==arp['id'])
   self.assertEqual(next(p['value'] for p in got['parameters'] if p['kind']==27),want)
