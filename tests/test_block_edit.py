"""Lossless block edits, identity isolation, and occupied-destination protection."""
import copy,pathlib,sys,unittest,uuid
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'headless'))
from block_edit import capture,paste,snapshots,put_snapshots,phrase_addresses,model
from native_capacity import layouts
from conductor import encode,decode
from switch_presets import switches

def uid():return str(uuid.uuid4())
def fixture():
 c=layouts()[1];mem=[0]*c['PATCH_PAYLOAD_SIZE']
 for key,value in [('WORK_MEM_SIZE',2),('SW_LEGACY_PAYLOAD',3),('CC_LEGACY_PAYLOAD',4),('TF_LEGACY_PAYLOAD',5),('DS_LEGACY_PAYLOAD',6),('I_LEGACY_PAYLOAD',7),('NATIVE_LEGACY_PAYLOAD',8)]:mem[c[key]]=value
 mem[c['DS_LEGACY_PAYLOAD']+1]=5
 p=dict(format='MIDI_HUMAN_LOOPER_PATCH',schema=8,memory=mem,globals=[44100,1,0,0,0,0,0,0,0],work_mem_size=len(mem))
 m=model(p)
 for i in range(4):
  b=c['SW_LEGACY_PAYLOAD']+1+i*128
  for off,value in {0:1,2:1,3:0,4:60+i,7:300,8:800,11:1,14:1,17:i,18:i,19:i,20:1,21:i+1}.items():mem[b+off]=value
  mem[b+48]=i
  for j in range(24,32):mem[b+j]=100+j
  for j in range(112,120):mem[b+j]=1
 for slot in (1,2,128):
  i=slot-1;mem[i*c['LAYER_STRIDE']:i*c['LAYER_STRIDE']+10]=[0,144,60+slot%8,70,0,22050,128,60+slot%8,0,0]
  mem[c['COUNT_BASE']+i]=2;mem[c['LEN_BASE']+i]=44100+slot;mem[c['VEL_BASE']+i]=slot/128
  mem[c['MODE_BASE']+i]=slot%3;mem[c['PHRASE_NOTE_BASE']+i]=40+slot%16
  next(s for s in m['sources'] if s['slot']==slot)['muteGroup']=slot
 m['movements']=[dict(id=uid(),name='TEST',target=dict(type='CC',channel=1,number=5),points=[[0,0],[1,1]],duration=2,interpolation='LINEAR',retrigger='SOFT_RESTART',glideSeconds=.2)]
 block=dict(id=uid(),type='PHRASE',sourceId=m['sources'][0]['id'],overrides={})
 m['switches']=[dict(switchId=1,traversal='SEQUENTIAL',transition='IMMEDIATE',gesture='INSTANT',steps=[dict(id=uid(),transition='INHERIT',layers=[dict(id=uid(),block=block)])])]
 p['conductor']=encode(m)
 header,records,tail=snapshots(p)
 records.append([1,2,1,2,1]+[ord('A')]+[0]*48+[1,0,17,.7,1,0]);header[1]=2
 tail[:4]=[1,0,3,1];put_snapshots(p,header,records,tail)
 return p

class Edits(unittest.TestCase):
 def setUp(self):self.p=fixture();self.c=layouts()[1]
 def test_phrase_occupied_requires_explicit_mode(self):
  clip=capture(self.p,'phrase',1);before=copy.deepcopy(self.p)
  with self.assertRaisesRegex(ValueError,'occupied'):paste(self.p,clip,2)
  self.assertEqual(self.p,before)
 def test_copy_empty_and_overwrite_are_complete_but_slot_links_stay(self):
  clip=capture(self.p,'phrase',128)
  for target,mode in [(3,'empty'),(2,'overwrite')]:
   p,ident=paste(self.p,clip,target,mode);self.assertEqual(ident,target)
   got=capture(p,'phrase',target);self.assertEqual({k:v for k,v in got.items() if k!='source'},{k:v for k,v in clip.items() if k!='source'})
   self.assertEqual(p['memory'][self.c['PHRASE_NOTE_BASE']+target-1],self.p['memory'][self.c['PHRASE_NOTE_BASE']+target-1])
   self.assertEqual(decode(p['conductor'])['switches'],decode(self.p['conductor'])['switches'])
 def test_swap_and_changed_source_refusal(self):
  a=capture(self.p,'phrase',1);b=capture(self.p,'phrase',2)
  p,_=paste(self.p,a,2,'swap')
  for target,want in [(1,b),(2,a)]:
   got=capture(p,'phrase',target);got.pop('source');want=copy.deepcopy(want);want.pop('source');self.assertEqual(got,want)
  self.p['memory'][self.c['VEL_BASE']]=2
  with self.assertRaisesRegex(ValueError,'Source changed'):paste(self.p,a,2,'swap')
 def test_swap_with_empty_slot(self):
  p,_=paste(self.p,capture(self.p,'phrase',1),3,'swap')
  self.assertEqual(p['memory'][self.c['COUNT_BASE']],0)
  self.assertEqual(capture(p,'phrase',3)['events'],capture(self.p,'phrase',1)['events'])
 def test_swap_tolerates_native_float_normalization_only(self):
  self.p['memory'][self.c['DECAY_BASE']]=.8
  clip=capture(self.p,'phrase',1)
  self.p['memory'][self.c['DECAY_BASE']]=.8-1e-16
  paste(self.p,clip,2,'swap')
  self.p['memory'][self.c['DECAY_BASE']]=.79
  with self.assertRaisesRegex(ValueError,'Source changed'):paste(self.p,clip,2,'swap')
 def test_switch_preserves_shared_carriers_and_regenerates_conductor_ids(self):
  # Reuse a deleted legacy slot whose phrase/controller carrier values matter.
  b=self.c['SW_LEGACY_PAYLOAD']+1+128;self.p['memory'][b+20]=0
  self.p['memory'][self.c['SW_LEGACY_PAYLOAD']+1+14]=3
  p,ident=paste(self.p,capture(self.p,'switch',1))
  sw=switches(p)[ident];self.assertEqual(sw['slot'],1);self.assertEqual(sw['config']['settings'][1],0)
  for off in list(range(24,32))+list(range(112,120)):self.assertEqual(p['memory'][b+off],self.p['memory'][b+off])
  old,new=decode(p['conductor'])['switches'];self.assertNotEqual(old['steps'][0]['id'],new['steps'][0]['id'])
  self.assertEqual(old['steps'][0]['layers'][0]['block']['sourceId'],new['steps'][0]['layers'][0]['block']['sourceId'])
  self.assertEqual(sw['config']['settings'][15],1) # self action points at new slot
  _,_,tail=snapshots(p);self.assertEqual(tail[4:8],[ident,0,3,1])
 def test_movement_new_identity_same_curve(self):
  source=model(self.p)['movements'][0];p,ident=paste(self.p,capture(self.p,'movement',source['id']))
  cloned=model(p)['movements'][-1];self.assertNotEqual(ident,source['id']);self.assertEqual(cloned['points'],source['points'])
 def test_snapshot_new_identity_complete_record(self):
  p,ident=paste(self.p,capture(self.p,'snapshot',1));h,r,t=snapshots(p)
  self.assertEqual(ident,2);self.assertEqual(r[0][1:],r[1][1:]);self.assertEqual(t,snapshots(self.p)[2])
 def test_nonphrase_occupied_destinations_never_allowed(self):
  for kind,source in [('switch',1),('snapshot',1),('movement',model(self.p)['movements'][0]['id'])]:
   clip=capture(self.p,kind,source)
   for mode in ('empty','overwrite','swap'):
    with self.assertRaises(ValueError):paste(self.p,clip,1,mode)
 def test_invalid_phrase_ids_and_immutable_clipboard(self):
  clip=capture(self.p,'phrase',1);before=copy.deepcopy(clip)
  for target in (0,129,True,1.1,'1'):
   with self.assertRaises(ValueError):paste(self.p,clip,target)
  paste(self.p,clip,3);self.assertEqual(before,clip)

if __name__=='__main__':unittest.main()
