"""Private native engines verify phrase ORIGINAL follows both Instrument OUTs."""
import os,sys,tempfile,pathlib,subprocess,time,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'headless'))
from server import Control
class PhraseRouting(unittest.TestCase):
 def check_mode(self,mode):
  with tempfile.TemporaryDirectory() as temp:
   sock=pathlib.Path(temp)/'control.sock';source=os.environ.get('ROUTING_SOURCE',str(ROOT/'midi_human_looper.jsfx'))
   with open(pathlib.Path(temp)/'engine.log','w') as log:
    process=subprocess.Popen([str(ROOT/'.build/midi-headless-engine'),source,str(sock),'--chain','--chain-timing','2'],stdout=log,stderr=log)
   try:
    for _ in range(100):
     if sock.exists():break
     self.assertIsNone(process.poll());time.sleep(.05)
    c=Control(str(sock))
    def cmd(**args):
     s=c.request();r=c.request(revision=s['revision'],session=s['engineSessionId'],**args);self.assertEqual(r.get('status'),'ok',r);return c.request()
    def wait(predicate,label,timeout=2):
     deadline=time.monotonic()+timeout
     while time.monotonic()<deadline:
      s=c.request()
      if predicate(s):return s
      time.sleep(.005)
     self.fail(label+': '+str({k:s[k] for k in ['activeNotes','midiCount','lastEvent','instances','chainRunning','instanceError']}))
    for i in c.request()['instruments']:cmd(op=11,target=i['id'],arg=0,ch=1,note=i['output'],value=127)
    cmd(op=33,target=2,arg=1);cmd(op=33,target=3,arg=1);cmd(op=33)
    ids=[i['id'] for i in c.request()['instruments']];self.assertEqual(ids,[1,4])
    for iid,out in zip(ids,(1,2)):cmd(op=11,target=iid,arg=1,ch=1,note=out,value=127)
    # The very same source note and input filters must own two output channels.
    cmd(op=3,ch=0,note=64,value=90);self.assertEqual(c.request()['activeNotes'],2);cmd(op=3,ch=0,note=64,value=0)
    cmd(op=35,target=0,arg=1,phrase={'lengthSeconds':2,'events':[[0,144,64,90],[1.5,128,64,0]]})
    def export():
     state=c.request();result=c.request(op=35,target=0,arg=0,revision=state['revision'],session=state['engineSessionId']);self.assertEqual(result['status'],'ok');return result['phraseData']
    original=export()
    cmd(op=32,target=1,arg=20,macro=[0,mode]);cmd(op=49,target=0,value=0)
    cmd(op=40,target=0,arg=1)
    state=wait(lambda s:s['activeNotes']>0,'phrase attack')
    self.assertEqual(state['activeNotes'],2,'phrase must sound on both output channels')
    self.assertEqual(state['lastEvent'][1]&15,1,'last attack must target channel 2')
    cmd(op=40,target=0,arg=6);wait(lambda s:s['activeNotes']==0,'stop releases both')
    # A live owner must survive stopping a phrase that shares its note.
    cmd(op=3,ch=0,note=64,value=90);cmd(op=40,target=0,arg=1)
    time.sleep(.06);cmd(op=40,target=0,arg=6);self.assertEqual(c.request()['activeNotes'],2)
    cmd(op=3,ch=0,note=64,value=0);self.assertEqual(c.request()['activeNotes'],0)
    self.assertEqual(export(),original)
    # A second instrument with a different IN must not receive channel 1 playback.
    cmd(op=11,target=4,arg=1,ch=14,note=2,value=127);cmd(op=40,target=0,arg=1)
    state=wait(lambda s:s['activeNotes']>0,'filtered phrase attack');self.assertEqual(state['activeNotes'],1)
    cmd(op=40,target=0,arg=6);self.assertEqual(c.request()['activeNotes'],0)
    cmd(op=11,target=4,arg=1,ch=1,note=2,value=127)
    for policy,expected in ((14,1),(17,16)):
     cmd(op=49,target=0,value=policy);cmd(op=40,target=0,arg=1)
     state=wait(lambda s:s['activeNotes']>0,'explicit channel policy')
     self.assertEqual(state['activeNotes'],expected)
     if policy==14:self.assertEqual(state['lastEvent'][1]&15,13)
     cmd(op=40,target=0,arg=6);self.assertEqual(c.request()['activeNotes'],0)
    self.assertEqual(export(),original)
   finally:process.terminate();process.wait(timeout=10)
 def test_loop(self):self.check_mode(0)
 def test_once(self):self.check_mode(1)
 def test_hold(self):self.check_mode(2)
if __name__=='__main__':unittest.main()
