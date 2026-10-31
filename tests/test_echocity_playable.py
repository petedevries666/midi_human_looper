"""Private real-engine ECHOCITY qualification; JACK mode connects only test ports."""
import copy,json,os,pathlib,subprocess,sys,tempfile,time,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'headless'))
from echocity_config import decode,encode,DEFAULTS
from native_capacity import build_source,layout
from server import Control

class Wire(unittest.TestCase):
 def test_destination_transforms_roundtrip_and_refusals(self):
  cfg={'version':5,'configuration':[5,1,1,*DEFAULTS[1:],0,0,0,1,0,*([0]*16),2]}
  self.assertEqual(encode(decode(cfg)),cfg)
  for value in (-1,3,True,.5):
   bad=copy.deepcopy(cfg);bad['configuration'][-1]=value
   with self.assertRaises(ValueError):decode(bad)
  unit=decode(cfg)[0]
  for value in (-1,3,True,.5):
   unit['destinationTransforms']=value
   with self.assertRaises(ValueError):encode([unit])
 def test_multichannel_roundtrip_and_refusals(self):
  for routing in (0,1,2,3):
   cfg={'version':4,'configuration':[4,1,1,*DEFAULTS[1:],2,routing,18,1,4,1,4,1,15,*([0]*12)]}
   self.assertEqual(encode(decode(cfg)),cfg)
   for index,value in ((15,4),(16,65536),(17,True),(18,17),(19,16)):
    bad=copy.deepcopy(cfg);bad['configuration'][2+index]=value
    with self.assertRaises(ValueError):decode(bad)
  for routing in (1,2):
   with self.assertRaises(ValueError):decode({'version':4,'configuration':[4,1,1,*DEFAULTS[1:],0,routing,0,1,0,*([0]*16)]})
  with self.assertRaises(ValueError):decode({'version':4,'configuration':[4,1,1,*DEFAULTS[1:],0,3,0,1,0,*([0]*16)]})
 def test_roundtrip_and_refusals(self):
  good={'version':2,'configuration':[2,1,1,*DEFAULTS[1:]]}
  self.assertEqual(encode(decode(good)),good)
  bad=[]
  for index,value in ((0,True),(1,2),(3,float('nan')),(9,33),(10,49),(12,16),(13,1.1)):
   p=copy.deepcopy(good);p['configuration'][2+index]=value;bad.append(p)
  p=copy.deepcopy(good);p['version']=3;bad.append(p)
  p=copy.deepcopy(good);p['configuration']=[2,2]+p['configuration'][2:]*2;bad.append(p)
  old={'version':1,'configuration':[1,1,1,*DEFAULTS[1:13]]}
  migrated=encode(decode(old));self.assertEqual(migrated['version'],2);self.assertEqual(migrated['configuration'][-1],.5)
  for p in bad:
   with self.assertRaises(ValueError):decode(p)

 def test_fragment_modes_roundtrip_and_refusals(self):
  for mode in (1,2,3):
   extension={'version':3,'configuration':[3,1,1,*DEFAULTS[1:],mode]}
   self.assertEqual(encode(decode(extension)),extension)
  for mode in (-1,4,True,1.5):
   with self.assertRaises(ValueError):decode({'version':3,'configuration':[3,1,1,*DEFAULTS[1:],mode]})

class RealEngine(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory(prefix='mbmf-echo-qualified-');cls.directory=pathlib.Path(cls.tmp.name)
  cls.source=cls.directory/'native.jsfx';cls.source.write_text(build_source((ROOT/'midi_human_looper.jsfx').read_text()))
  cls.sock=cls.directory/'control.sock';cls.log=(cls.directory/'engine.log').open('w')
  cls.jack=os.environ.get('ECHOCITY_JACK')=='1'
  args=[str(ROOT/'.build/midi-headless-engine'),str(cls.source),str(cls.sock),'--chain','--chain-timing','2']
  if cls.jack:args+=['--jack','--client','mbmf_d']
  cls.worker=subprocess.Popen(args,stdout=cls.log,stderr=cls.log)
  for _ in range(400):
   if cls.worker.poll() is not None:raise RuntimeError((cls.directory/'engine.log').read_text())
   if cls.sock.exists():break
   time.sleep(.05)
  cls.control=Control(str(cls.sock))
  for _ in range(200):
   s=cls.control.request()
   if s.get('echocityAvailable') and s.get('instruments'):break
   time.sleep(.05)
  else:raise RuntimeError('Native ECHOCITY fixture unavailable')
  cls.instrument=s['instruments'][0]['id']
 @classmethod
 def tearDownClass(cls):
  cls.worker.terminate()
  try:cls.worker.wait(timeout=10)
  except subprocess.TimeoutExpired:cls.worker.kill();cls.worker.wait()
  cls.log.close();cls.tmp.cleanup()
 def command(self,op,**extra):
  s=self.control.request();return self.control.request(op=op,revision=s['revision'],session=s['engineSessionId'],**extra)
 def export(self):
  for _ in range(20):
   p=self.command(4)
   if 'memory' in p:return p
   time.sleep(.05)
  self.fail('Patch export conflict')
 def config(self,rows):
  p={'version':2,'configuration':[2,len(rows)]+[x for r in rows for x in r]}
  self.assertEqual(self.command(54,echo=p)['status'],'ok');return p
 def test_01_configuration_persistence(self):
  row=[self.instrument,*DEFAULTS[1:]];row[3]=80;row[9]=2
  cfg=self.config([row]);p=self.export();self.assertEqual(p['echocity'],cfg)
  self.config([]);self.assertEqual(self.command(5,target=8,patch=p)['status'],'ok')
  self.assertEqual(self.export()['echocity'],cfg)
  state=self.control.request();self.assertNotEqual(self.control.request(op=54,echo=cfg,revision=state['revision'],session=state['engineSessionId']+1)['status'],'ok')
  wrong=copy.deepcopy(cfg);wrong['configuration'][2]=16777000
  self.assertNotEqual(self.command(54,echo=wrong)['status'],'ok');self.assertEqual(self.export()['echocity'],cfg)
  p.pop('echocity');self.assertEqual(self.command(5,target=8,patch=p)['status'],'ok')
  self.assertEqual(self.export()['echocity']['configuration'],[2,0])
  legacy={'version':1,'configuration':[1,1,*row[:13]]}
  self.assertEqual(self.command(54,echo=legacy)['status'],'ok')
  self.assertEqual(self.export()['echocity'],encode(decode(legacy)))
  self.config([])
 def test_01b_fragment_carrier_persistence(self):
  row=[self.instrument,*DEFAULTS[1:]]
  cfg={'version':3,'configuration':[3,1,*row,3]}
  self.assertEqual(self.command(54,echo=cfg)['status'],'ok')
  saved=self.export();self.assertEqual(saved['echocity'],cfg)
  self.config([]);self.assertEqual(self.command(5,target=8,patch=saved)['status'],'ok')
  self.assertEqual(self.export()['echocity'],cfg)
  self.config([])
 def test_01c_multichannel_carrier_persistence(self):
  cfg={'version':4,'configuration':[4,1,self.instrument,*DEFAULTS[1:],2,3,0,1,4,1,4,1,15,*([0]*12)]}
  self.assertEqual(self.command(54,echo=cfg)['status'],'ok');saved=self.export();self.assertEqual(saved['echocity'],cfg)
  self.config([]);self.assertEqual(self.command(5,target=8,patch=saved)['status'],'ok');self.assertEqual(self.export()['echocity'],cfg)
  bad=copy.deepcopy(cfg);bad['configuration'][2+19]=16
  with self.assertRaises(ValueError):self.command(54,echo=bad)
  self.assertEqual(self.export()['echocity'],cfg)
  self.config([])
 def test_01d_destination_transforms_persistence(self):
  cfg={'version':5,'configuration':[5,1,self.instrument,*DEFAULTS[1:],0,0,0,1,0,*([0]*16),2]}
  self.assertEqual(self.command(54,echo=cfg)['status'],'ok');saved=self.export();self.assertEqual(saved['echocity'],cfg)
  self.config([]);self.assertEqual(self.command(5,target=8,patch=saved)['status'],'ok');self.assertEqual(self.export()['echocity'],cfg)
  self.config([])
 def test_01e_full_destination_handoff(self):
  # Full production host callback, source journal, handoff, EEL and final ledger.
  # A terminal/direct echo never creates a destination input in the VM.
  for instrument in self.control.request()['instruments']:
   if instrument['id']!=self.instrument:self.assertEqual(self.command(11,target=instrument['id'],arg=0,ch=0,note=0,value=127)['status'],'ok')
  self.assertEqual(self.command(11,target=self.instrument,arg=1,ch=1,note=1,value=127)['status'],'ok')
  row=[self.instrument,*DEFAULTS[1:]];row[3]=120;row[5]=1;row[6]=1;row[7]=4;row[9]=1
  cfg={'version':5,'configuration':[5,1,*row,0,0,0,1,0,*([0]*16),2]}
  self.assertEqual(self.command(54,echo=cfg)['status'],'ok')
  try:
   self.assertEqual(self.command(3,ch=0,note=79,value=100)['status'],'ok');time.sleep(.03)
   self.assertEqual(self.command(3,ch=0,note=79,value=0)['status'],'ok')
   self.assertEqual(self.control.request()['activeNotes'],0,'physical source must stop before the delayed destination attack')
   seen=False;retired=False;deadline=time.monotonic()+3
   while time.monotonic()<deadline:
    state=self.control.request();seen|=state['activeNotes']>0
    if seen and not state['activeNotes'] and not state['echocityPending'] and not state['echocitySources']:retired=True;break
    time.sleep(.005)
   self.assertTrue(seen,'scheduled full echo never entered the destination native instrument')
   self.assertTrue(retired,'full destination handoff left active notes or echo leases')
  finally:
   self.command(2);self.config([])
 def test_02_isolated_jack_echoes_and_order(self):
  if not self.jack:self.skipTest('Set ECHOCITY_JACK=1 for actual isolated JACK ports')
  row=[self.instrument,*DEFAULTS[1:]];row[3]=80;row[5]=.5;row[6]=1;row[9]=2
  self.config([row]);time.sleep(.1)
  probe=subprocess.Popen([str(ROOT/'.build/echocity-jack-probe')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  try:
   self.assertEqual(probe.stdout.readline().strip(),'READY')
   def send(*packets):
    probe.stdin.write(''.join(' '.join(map(str,p))+'\n' for p in packets));probe.stdin.flush()
   send((144,60,100,16));time.sleep(.025);send((128,60,0,16));time.sleep(.35)
   # Same-frame reset before/after attack must preserve the exact source order.
   send((176,123,0,16),(144,62,100,16));time.sleep(.025);send((128,62,0,16));time.sleep(.35)
   send((144,64,100,16),(176,123,0,16));time.sleep(.025);send((128,64,0,16));time.sleep(.35)
   send((144,65,100,16));time.sleep(.22);send((128,65,0,16));time.sleep(.3)
   probe.stdin.close();probe.wait(timeout=10);lines=probe.stdout.read().splitlines()
   self.assertEqual(probe.returncode,0,probe.stderr.read())
  finally:
   if probe.poll() is None:probe.kill();probe.wait()
   probe.stdout.close();probe.stderr.close()
  events=[list(map(int,line.split())) for line in lines]
  for pitch in (60,62,64,65):
   attacks=[e for e in events if e[2]==144 and e[3]==pitch and e[4]]
   self.assertEqual(len(attacks),3,(pitch,events))
   times=[e[0]+e[1] for e in attacks]
   for a,b in zip(times,times[1:]):self.assertLessEqual(abs((b-a)-3528),1,(pitch,times))
  at62=next(i for i,e in enumerate(events) if e[2]==144 and e[3]==62)
  at64=next(i for i,e in enumerate(events) if e[2]==144 and e[3]==64)
  self.assertEqual(events[at62-1][2:4],[176,123]);self.assertEqual(events[at64+1][2:4],[176,123])
  held=set()
  for _,_,status,pitch,value in events:
   ch=status&15
   if status&240==176 and pitch in (120,123):held={k for k in held if k[0]!=ch}
   elif status&240==144 and value:held.add((ch,pitch))
   elif status&240 in (128,144):held.discard((ch,pitch))
  self.assertFalse(held,events)
  state=self.control.request();self.assertEqual(state['echocitySources'],0);self.assertEqual(state['echocityPending'],0)
  print('Observed',len(events),'actual JACK packets; 80ms echoes and CC123 order verified')

 def test_03_jack_phrase_arp_ping_pong_and_panic(self):
  if not self.jack:self.skipTest('Actual isolated JACK ports required')
  probe=subprocess.Popen([str(ROOT/'.build/echocity-jack-probe')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  try:
   self.assertEqual(probe.stdout.readline().strip(),'READY')
   def send(status,pitch,value):
    probe.stdin.write(f'{status} {pitch} {value} 16\n');probe.stdin.flush()
   row=[self.instrument,*DEFAULTS[1:]];row[3]=80;row[6]=1;row[9]=2;row[10]=7;row[11]=1
   self.config([row]);send(144,40,100);time.sleep(.025);send(128,40,0);time.sleep(.3)
   # Bypass must keep the direct note and remove future wet generations.
   row[1]=0;self.config([row]);send(144,41,100);time.sleep(.025);send(128,41,0);time.sleep(.3)
   row[1]=1;row[10]=12;row[11]=0;self.config([row])
   p=self.export();cfg=layout(p);p['globals'][0]=8820
   p['memory'][:10]=[0,144,44,100,0,1102,128,44,0,0]
   p['memory'][cfg['COUNT_BASE']]=2;p['memory'][cfg['LEN_BASE']]=8820;p['memory'][cfg['MODE_BASE']]=1
   self.assertEqual(self.command(5,target=8,patch=p)['status'],'ok')
   self.assertEqual(self.command(40,target=0,arg=7)['status'],'ok');time.sleep(.6)
   # Observe the true native ARP output followed by terminal echoes.
   self.assertEqual(self.command(13,target=self.instrument,arg=1,note=5,module=0)['status'],'ok')
   send(144,48,100);time.sleep(.35);send(128,48,0);time.sleep(.7)
   # PANIC must cancel a held note and all its scheduled echoes.
   send(144,50,100);time.sleep(.12);self.assertEqual(self.command(2)['status'],'ok');time.sleep(.7)
   send(128,50,0);time.sleep(.1)
   probe.stdin.close();probe.wait(timeout=10);lines=probe.stdout.read().splitlines()
   self.assertEqual(probe.returncode,0,probe.stderr.read())
  finally:
   if probe.poll() is None:probe.kill();probe.wait()
   probe.stdout.close();probe.stderr.close()
  events=[list(map(int,line.split())) for line in lines]
  attacks=[tuple(e[2:]) for e in events if e[2]&240==144 and e[4]]
  self.assertTrue(any(s==145 and p==47 for s,p,v in attacks),attacks)
  self.assertTrue(any(s==144 and p==54 for s,p,v in attacks),attacks)
  self.assertEqual(sum(p==41 for s,p,v in attacks),1)
  self.assertFalse(any(p in (48+7,41+14) for s,p,v in attacks[:4]))
  for pitch in (44,56,68):self.assertTrue(any(p==pitch for s,p,v in attacks),attacks)
  self.assertTrue(any(p==48 for s,p,v in attacks),attacks)
  self.assertTrue(any(p==60 for s,p,v in attacks),attacks)
  held=set()
  for _,_,status,pitch,value in events:
   ch=status&15
   if status&240==176 and pitch in (120,123):held={k for k in held if k[0]!=ch}
   elif status&240==144 and value:held.add((ch,pitch))
   elif status&240 in (128,144):held.discard((ch,pitch))
  self.assertFalse(held)
  s=self.control.request();self.assertEqual(s['echocityPending'],0);self.assertEqual(s['echocitySources'],0)
  print('Verified actual JACK phrase, ARP, pitch, ping-pong, bypass and PANIC:',len(events),'packets')

 def test_04_native_velocity_eight_and_patch_restore(self):
  self.assertEqual(self.command(13,target=self.instrument,arg=1,note=4,module=0)['status'],'ok')
  for _ in range(100):
   instrument=next(i for i in self.control.request()['instruments'] if i['id']==self.instrument)
   velocity=next((t for t in instrument['transformers'] if t['type']==4),None)
   if velocity:break
   time.sleep(.01)
  self.assertIsNotNone(velocity)
  self.assertEqual(self.command(12,target=self.instrument,module=velocity['id'],parameters=[{'kind':0,'value':8}])['status'],'ok')
  p=self.export();self.assertEqual(self.command(5,target=8,patch=p)['status'],'ok')
  i=next(i for i in self.control.request()['instruments'] if i['id']==self.instrument)
  self.assertEqual(next(t for t in i['transformers'] if t['id']==velocity['id'])['parameters'][0]['value'],8)
  self.assertNotEqual(self.command(12,target=self.instrument,module=velocity['id'],parameters=[{'kind':0,'value':8.01}])['status'],'ok')

if __name__=='__main__':unittest.main(verbosity=2)
