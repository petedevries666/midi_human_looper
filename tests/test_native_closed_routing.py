"""Private native/legacy engine checks: unmatched MIDI, OFF and note ownership."""
import os,sys,tempfile,pathlib,subprocess,time,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'headless'))
from server import Control
class Routing(unittest.TestCase):
 def run_mode(self,native):
  with tempfile.TemporaryDirectory() as temp:
   sock=pathlib.Path(temp)/'control.sock'
   source=os.environ.get('ROUTING_SOURCE',str(ROOT/'midi_human_looper.jsfx'))
   args=[str(ROOT/'.build/midi-headless-engine'),source,str(sock)]+(['--chain','--chain-timing','2'] if native else [])
   with open(pathlib.Path(temp)/'engine.log','w') as log:
    process=subprocess.Popen(args,stdout=log,stderr=log)
   try:
    for _ in range(100):
     if sock.exists():break
     self.assertIsNone(process.poll());time.sleep(.05)
    c=Control(str(sock))
    def command(**args):
     state=c.request();response=c.request(revision=state['revision'],session=state['engineSessionId'],**args);self.assertEqual(response.get('status'),'ok',response);return c.request()
    for i in c.request()['instruments']:command(op=11,target=i['id'],arg=0,ch=i['input'],note=i['output'],value=i['level'])
    first=c.request()['instruments'][0]['id']
    def note(ch,n=60):
     before=c.request()['midiCount'];command(op=3,ch=ch-1,note=n,value=90);attack=c.request();command(op=3,ch=ch-1,note=n,value=0);return c.request()['midiCount']-before,attack
    delta,_=note(1);self.assertEqual(delta,0 if native else 2)
    command(op=11,target=first,arg=1,ch=1,note=14,value=127)
    delta,attack=note(1);self.assertEqual(delta,2);self.assertEqual(attack['lastEvent'][1]&15,13)
    delta,_=note(2);self.assertEqual(delta,0 if native else 2)
    # Changing input/enable with a held note must still release its owner.
    command(op=3,ch=0,note=62,value=100)
    command(op=11,target=first,arg=0,ch=1,note=14,value=127)
    command(op=3,ch=0,note=62,value=0);self.assertEqual(c.request()['activeNotes'],0)
    if native:
     command(op=35,target=0,arg=1,phrase={'lengthSeconds':.2,'events':[[0,145,64,90],[.1,129,64,0]]})
     command(op=11,target=first,arg=1,ch=1,note=14,value=127)
     before=c.request()['midiCount'];command(op=40,target=0,arg=1);time.sleep(.4)
     self.assertEqual(c.request()['midiCount'],before)
    self.assertEqual(c.request()['activeNotes'],0)
   finally:
    process.terminate();process.wait(timeout=10)
 def test_native_routes_are_closed(self):self.run_mode(True)
 def test_legacy_passthrough_is_preserved(self):self.run_mode(False)
if __name__=='__main__':unittest.main()
