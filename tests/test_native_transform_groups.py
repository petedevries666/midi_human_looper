"""Actual private native engines: source groups with stateful Transformers."""
import sys,pathlib,time,unittest
from test_native_hold_release_balance import HoldBalance as Base
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'headless'))
from conductor import migrate,with_mute_groups,encode
class TransformGroups(Base):
 def exercise(self,mode,mono,arp,latch,stack=False):
  if stack:
   for kind in (1,2,4,6):self.cmd(op=13,target=1,arg=1,note=kind)
  if mono:
   self.cmd(op=13,target=1,arg=1,note=3);m=next(t for t in self.c.request()['instruments'][0]['transformers'] if t['type']==3)
   self.cmd(op=32,target=1,arg=11,macro=[m['id'],mono])
  if arp:
   self.cmd(op=13,target=1,arg=1,note=5);m=next(t for t in self.c.request()['instruments'][0]['transformers'] if t['type']==5)
   for k,v in ((3,1),(4,1),(5,16),(6,.3),(12,latch)):self.cmd(op=32,target=1,arg=k,macro=[m['id'],v])
  for slot,pitch in enumerate((60,72,55)):
   self.cmd(op=35,target=slot,arg=1,phrase={'lengthSeconds':2,'events':[[0,144,pitch,90],[1.8,128,pitch,0]]});self.cmd(op=32,target=slot+1,arg=20,macro=[0,mode])
  s=self.c.request();patch=self.c.request(op=4,arg=1,revision=s['revision'],session=s['engineSessionId']);self.assertEqual(patch.get('format'),'MIDI_HUMAN_LOOPER_PATCH')
  model=with_mute_groups(migrate(patch))
  for source in model['sources']:source['muteGroup']=1 if source['slot'] in (1,2) else 2 if source['slot']==3 else 0
  patch['conductor']=encode(model);self.cmd(op=5,target=patch['schema'],arg=1,patch=patch)
  self.cmd(op=40,target=2,arg=1);self.cmd(op=40,target=0,arg=1);time.sleep(.12)
  s=self.c.request();self.assertEqual(s['instanceError'],0);self.assertEqual(s['phrases'][0]['state'],'PLAYING');self.assertEqual(s['phrases'][2]['state'],'PLAYING')
  self.cmd(op=40,target=1,arg=1);time.sleep(.12);s=self.c.request()
  self.assertEqual(s['instanceError'],0);self.assertEqual(s['phrases'][0]['state'],'STOPPED');self.assertEqual(s['phrases'][1]['state'],'PLAYING');self.assertEqual(s['phrases'][2]['state'],'PLAYING')
  self.cmd(op=40,target=1,arg=6);self.assertEqual(self.c.request()['phrases'][2]['state'],'PLAYING')
  self.cmd(op=40,target=2,arg=6);time.sleep(.12);s=self.c.request();self.assertEqual(s['activeNotes'],0)
  before=s['midiCount'];time.sleep(.15);self.assertEqual(self.c.request()['midiCount'],before,'stopped source left an ARP latch')
  if not latch:
   self.cmd(op=3,ch=0,note=84,value=90);self.cmd(op=40,target=0,arg=1);time.sleep(.08);self.cmd(op=40,target=1,arg=1);time.sleep(.08);self.cmd(op=40,target=1,arg=6)
   before=self.c.request()['midiCount'];time.sleep(.15);s=self.c.request()
   if arp:self.assertGreater(s['midiCount'],before,'group STOP cut the physical ARP source')
   else:self.assertEqual(s['activeNotes'],1,'group STOP cut the physical mono source')
   self.cmd(op=3,ch=0,note=84,value=0);time.sleep(.12);self.assertEqual(self.c.request()['activeNotes'],0)
  self.cmd(op=2);self.assertFalse(self.c.request()['instances'])

def scenario(mode,mono,arp,latch,stack=False):
 def test(self):self.exercise(mode,mono,arp,latch,stack)
 return test
for mode in (0,1,2):
 for mono,arp,latch in ((0,1,0),(0,1,1),(1,0,0),(2,0,0),(3,0,0),(1,1,0),(2,1,0),(3,1,0),(1,1,1),(2,1,1),(3,1,1)):
  setattr(TransformGroups,f'test_mode_{mode}_mono_{mono}_arp_{arp}_latch_{latch}',scenario(mode,mono,arp,latch))
setattr(TransformGroups,'test_full_transformer_stack',scenario(2,3,1,1,True))
if __name__=='__main__':unittest.main()
