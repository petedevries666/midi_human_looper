"""Actual native admission leases and worker UPDATE boundary, no device services."""
import contextlib, importlib.util, json, os, subprocess, sys, tempfile, time, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'headless'))
from server import Control
from controller_config import binding_wire
from update_admission import Admission, startup_owner, file_guard
spec=importlib.util.spec_from_file_location('update',ROOT/'scripts/zynthian-update.py');u=importlib.util.module_from_spec(spec);spec.loader.exec_module(u)
class AdmissionTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(prefix='mbmf-admission-');self.addCleanup(self.temp.cleanup);self.directory=Path(self.temp.name);self.children=[];self.addCleanup(self.stop)
 def stop(self):
  for p in self.children:
   p.terminate()
   try:p.wait(timeout=10)
   except subprocess.TimeoutExpired:p.kill();p.wait()
 def launch(self,index,owner=0):
  d=self.directory/f'processor-{index}';d.mkdir();path=d/'control.sock'
  args=[os.environ['HEADLESS_BINARY'],str(ROOT/'midi_human_looper.jsfx'),str(path),'--chain','--managed-admission']
  if owner:args+=['--update-admission',str(owner)]
  p=subprocess.Popen(args,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);self.children.append(p)
  end=time.monotonic()+10
  while not path.exists():
   assert p.poll() is None
   if time.monotonic()>end:raise AssertionError('native startup')
   time.sleep(.01)
  return Control(str(path))
 def command(self,c,**args):
  s=c.request();return c.request(revision=s['revision'],session=s['engineSessionId'],**args)
 def test_real_leases_reject_held_notes_and_armed_recording(self):
  c=self.launch(1)
  self.assertEqual(self.command(c,op=3,note=60,value=100)['status'],'ok')
  self.assertNotEqual(self.command(c,op=50,target=41)['status'],'ok')
  self.command(c,op=2);time.sleep(.04)
  self.command(c,op=40,target=0,arg=2)
  self.assertNotEqual(self.command(c,op=50,target=41)['status'],'ok')
  self.command(c,op=2);time.sleep(.04)
  self.assertTrue(self.command(c,op=50,target=41)['admissionClosed'])
  before=c.request()['midiCount']
  for args in [dict(op=3,note=60,value=100),dict(op=1,target=1),dict(op=40,target=0,arg=2)]:self.assertNotEqual(self.command(c,**args)['status'],'ok')
  self.assertEqual(c.request()['midiCount'],before)
  self.assertNotEqual(self.command(c,op=50,target=42,arg=1)['status'],'ok')
  self.command(c,op=2);self.assertTrue(c.request()['admissionClosed'])
  self.assertFalse(self.command(c,op=50,target=41,arg=1)['admissionClosed'])
  self.assertEqual(self.command(c,op=3,note=62,value=100)['status'],'ok');self.command(c,op=2)
 def test_empty_switch_held_refuses_update(self):
  c=self.launch(1);sw=c.request()['switches'][0]['settings'];sw[:4]=[1,1,0,110]
  self.assertEqual(self.command(c,op=41,target=1,settings=sw+[0]*64+[0]*16)['status'],'ok')
  self.command(c,op=3,note=110,value=127)
  self.assertNotEqual(self.command(c,op=50,target=41)['status'],'ok')
  self.command(c,op=3,note=110,value=0);time.sleep(.05)
  self.assertTrue(self.command(c,op=50,target=41)['admissionClosed'])
  self.command(c,op=50,target=41,arg=1)
 def test_controller_glide_cannot_mutate_frozen_checkpoint(self):
  c=self.launch(1)
  self.assertEqual(self.command(c,op=14,target=101,arg=2,ch=1,note=21)['status'],'ok')
  wire=binding_wire(dict(id=1,sourceId=101,targetId=201,instrumentId=1,kind=1,takeover=2,glideSeconds=1,points=[[0,0,0],[1,1,0]]))
  self.assertEqual(self.command(c,op=16,target=1,binding=wire)['status'],'ok')
  self.assertEqual(self.command(c,op=19,ch=1,note=21,value=0)['status'],'ok')
  time.sleep(.05)
  self.assertTrue(self.command(c,op=50,target=41)['admissionClosed'])
  level=c.request()['instruments'][0]['level'];time.sleep(.15)
  self.assertEqual(c.request()['instruments'][0]['level'],level)
  self.command(c,op=50,target=41,arg=1);self.command(c,op=2)
 def test_worker_fence_new_processor_restore_and_checkpoint(self):
  c=self.launch(1);runtime=u.Runtime(ROOT)
  with runtime.quiesce(self.directory) as gate:
   self.assertTrue(c.request()['admissionClosed']);self.assertIn('processor-1',gate.expected)
   with file_guard(self.directory,shared=True):
    owner=startup_owner(self.directory);other=self.launch(2,owner)
   self.assertTrue(other.request()['admissionClosed'])
   self.assertNotEqual(self.command(other,op=3,note=64,value=100)['status'],'ok')
   patch=self.command(other,op=4);self.assertEqual(patch['format'],'MIDI_HUMAN_LOOPER_PATCH')
   self.assertNotEqual(self.command(other,op=5,target=7,patch=patch)['status'],'ok')
   other.admission_owner=owner
   self.assertEqual(self.command(other,op=5,target=7,patch=patch)['status'],'ok')
   self.assertTrue(other.request()['admissionClosed']);self.assertEqual(other.request()['activeNotes'],0)
  self.assertFalse(c.request()['admissionClosed']);self.assertFalse(other.request()['admissionClosed']);self.assertFalse((self.directory/'update-admission.json').exists())
 def test_failed_multi_processor_acquire_releases_only_own_lease(self):
  c=self.launch(1);other=self.launch(2);self.command(other,op=40,target=0,arg=2)
  with self.assertRaisesRegex(ValueError,'STOP all'):
   with u.Runtime(ROOT).quiesce(self.directory):self.fail('must refuse')
  self.assertFalse(c.request()['admissionClosed']);self.assertFalse(other.request()['admissionClosed']);self.assertFalse((self.directory/'update-admission.json').exists());self.command(other,op=2)
 def test_activation_holds_native_boundary_through_restart_and_health(self):
  c=self.launch(1);runtime=u.Runtime(ROOT);config=self.directory/'install.json';old=dict(repository=str(ROOT),binary=os.environ['HEADLESS_BINARY']);u.atomic(config,old);calls=[];created=[]
  def service(action):
   calls.append(action);self.assertTrue(c.request()['admissionClosed'])
   self.assertNotEqual(self.command(c,op=3,note=60,value=100)['status'],'ok')
   if action=='start':
    with file_guard(self.directory,shared=True):created.append(self.launch(2,startup_owner(self.directory)))
  def healthy(config,expected):
   self.assertTrue(c.request()['admissionClosed']);self.assertTrue(created[0].request()['admissionClosed'])
  runtime.service=service;runtime.healthy=healthy
  u.activate(config,{**old,'runtime_revision':'test'},runtime,{})
  self.assertEqual(calls,['stop','start']);self.assertFalse(c.request()['admissionClosed']);self.assertFalse(created[0].request()['admissionClosed'])
  self.assertEqual(json.loads((self.directory/'runtime-update.json').read_text())['phase'],'active')
 def test_rollback_failure_retains_fence_until_explicit_recovery(self):
  c=self.launch(1);runtime=u.Runtime(ROOT);config=self.directory/'install.json';old=dict(repository=str(ROOT),binary=os.environ['HEADLESS_BINARY']);u.atomic(config,old)
  runtime.service=lambda action:None
  runtime.healthy=lambda *a:(_ for _ in ()).throw(ValueError('test health failed'))
  with self.assertRaisesRegex(RuntimeError,'rollback needs recovery'):u.activate(config,old,runtime,{})
  self.assertTrue(c.request()['admissionClosed']);self.assertTrue(startup_owner(self.directory))
  runtime.resume_admission(self.directory)
  self.assertFalse(c.request()['admissionClosed']);self.assertEqual(startup_owner(self.directory),0)
 def test_startup_guard_excludes_marker_race(self):
  with file_guard(self.directory):
   with self.assertRaisesRegex(ValueError,'busy'):
    with file_guard(self.directory,shared=True):self.fail('startup must refuse')
 def test_activation_rechecks_activity_after_checkpoint_before_stop(self):
  c=self.launch(1);config=self.directory/'install.json';old=dict(repository=str(ROOT),binary=os.environ['HEADLESS_BINARY']);u.atomic(config,old)
  runtime=u.Runtime(ROOT);expected=runtime.checkpoint(self.directory)
  self.command(c,op=40,target=0,arg=2);calls=[];runtime.service=lambda action:calls.append(action)
  with self.assertRaisesRegex(ValueError,'STOP all'):u.activate(config,old,runtime,expected)
  self.assertEqual(calls,[]);self.assertEqual(json.loads(config.read_text()),old);self.assertFalse((self.directory/'runtime-update.json').exists());self.command(c,op=2)
if __name__=='__main__':unittest.main(verbosity=2)
