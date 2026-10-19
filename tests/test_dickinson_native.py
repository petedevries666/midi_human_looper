"""Actual native worker/API integration; host snapshot APIs are fixtures only."""
import sys,unittest
from test_native_capacity import Capacity
from patch_recall import RecallService
from unittest.mock import patch
import types

class Dickinson(Capacity):
 def test_session_loaded_identity_and_pc_noop(self):
  self.assertEqual(self.control.request()['loadedPatchSlot'],0)
  saved=self.export();s=self.control.request()
  reply=self.control.request(op=5,target=8,loaded_slot=7,patch=saved,revision=s['revision'],session=s['engineSessionId'])
  self.assertEqual(reply['status'],'ok');self.assertEqual(self.control.request()['loadedPatchSlot'],7)
  self.cmd('phrase_rename',phraseId=1,name='UNSAVED')
  s=self.control.request();self.control.request(op=3,ch=0,note=60,value=100,revision=s['revision'],session=s['engineSessionId'])
  before=self.control.request()
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
