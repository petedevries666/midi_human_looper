"""Actual native HOLD output balance without JACK or a musical synth."""
import os,sys,pathlib,subprocess,tempfile,time,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'headless'))
from server import Control
class HoldBalance(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);sock=pathlib.Path(self.temp.name)/'control.sock'
  source=os.environ.get('ROUTING_SOURCE',str(ROOT/'midi_human_looper.jsfx'))
  log=open(pathlib.Path(self.temp.name)/'engine.log','w');self.addCleanup(log.close)
  self.engine=subprocess.Popen([str(ROOT/'.build/midi-headless-engine'),source,str(sock),'--chain','--chain-timing','2'],stdout=log,stderr=log)
  self.addCleanup(self.stop)
  for _ in range(100):
   if sock.exists():break
   self.assertIsNone(self.engine.poll());time.sleep(.05)
  self.c=Control(str(sock))
  for i in self.c.request()['instruments']:self.cmd(op=11,target=i['id'],arg=int(i['id']==1),ch=1,note=2,value=127)
 def stop(self):self.engine.terminate();self.engine.wait(timeout=10)
 def cmd(self,**args):
  s=self.c.request();r=self.c.request(revision=s['revision'],session=s['engineSessionId'],**args);self.assertEqual(r.get('status'),'ok',r.get('status'));return self.c.request()
 def load(self,slot,repeated=False):
  events=[[0,144,64,90],[.1,128,64,0]]
  if repeated:events += [[.2,144,64,80],[.3,128,64,0]]
  self.cmd(op=35,target=slot,arg=1,phrase={'lengthSeconds':.4,'events':events});self.cmd(op=32,target=slot+1,arg=20,macro=[0,2]);self.cmd(op=49,target=slot,value=0)
 def test_repeated_same_pitch_has_one_physical_attack_and_release(self):
  self.load(0,True);time.sleep(.03);before=self.c.request()['midiCount'];self.cmd(op=40,target=0,arg=1);time.sleep(.5)
  state=self.c.request();self.assertEqual(state['activeNotes'],1)
  self.assertEqual(state['midiCount']-before,1,'HOLD must not stack repeated attacks without balancing releases')
  self.cmd(op=40,target=0,arg=6);state=self.c.request();self.assertEqual(state['activeNotes'],0);self.assertEqual(state['midiCount']-before,2)
 def test_overlapping_hold_owners_release_only_the_last_voice(self):
  self.load(0);self.load(1);time.sleep(.03);before=self.c.request()['midiCount']
  self.cmd(op=40,target=0,arg=7);self.cmd(op=40,target=1,arg=7);time.sleep(.2)
  state=self.c.request();self.assertEqual(len(state['instances']),2);self.assertEqual(state['midiCount']-before,1)
  first=state['instances'][0];self.cmd(op=44,instance=[first['id'],first['generation']]);state=self.c.request();self.assertEqual(state['activeNotes'],1);self.assertEqual(state['midiCount']-before,1)
  last=state['instances'][0];self.cmd(op=44,instance=[last['id'],last['generation']]);state=self.c.request();self.assertEqual(state['activeNotes'],0);self.assertEqual(state['midiCount']-before,2)
if __name__=='__main__':unittest.main()
