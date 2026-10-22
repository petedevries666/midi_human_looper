"""Real native engine + HTTP worker on private sockets; never connects to JACK."""
import copy,json,pathlib,subprocess,sys,tempfile,threading,time,unittest,urllib.request,urllib.error
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'headless'))
from server import Control,make_server
from native_capacity import build_source,layout
from block_edit import capture,model
from conductor import encode

class NativeBlocks(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory(prefix='mbmf-blocks-');d=pathlib.Path(cls.tmp.name)
  source=d/'native.jsfx';source.write_text(build_source((ROOT/'midi_human_looper.jsfx').read_text()))
  cls.log=(d/'engine.log').open('w');cls.worker=subprocess.Popen([str(ROOT/'.build/midi-headless-engine'),str(source),str(d/'control.sock'),'--chain','--chain-timing','2'],stdout=cls.log,stderr=cls.log)
  for _ in range(400):
   if cls.worker.poll() is not None:raise RuntimeError((d/'engine.log').read_text())
   if (d/'control.sock').exists():break
   time.sleep(.05)
  cls.c=Control(str(d/'control.sock'))
  for _ in range(200):
   s=cls.c.request()
   if s.get('instruments'):break
   time.sleep(.05)
  cls.http=make_server('127.0.0.1',0,str(d/'control.sock'),token='private-test',patch_dir=d/'library');cls.http.control=cls.c
  cls.thread=threading.Thread(target=cls.http.serve_forever);cls.thread.start()
 @classmethod
 def tearDownClass(cls):
  cls.http.shutdown();cls.thread.join();cls.http.server_close();cls.worker.terminate();cls.worker.wait(timeout=10);cls.log.close();cls.tmp.cleanup()
 def cmd(self,op,**kwargs):
  s=self.c.request();return self.c.request(op=op,revision=s['revision'],session=s['engineSessionId'],**kwargs)
 def export(self):
  for _ in range(20):
   p=self.cmd(4,arg=1)
   if p.get('memory'):return p
   time.sleep(.05)
  self.fail('Native export failed')
 def api(self,**body):
  s=self.c.request();body=dict(expectedRevision=s['revision'],expectedEngineSessionId=s['engineSessionId'],**body)
  req=urllib.request.Request(f'http://127.0.0.1:{self.http.server_port}/api/v1/blocks',data=json.dumps(body).encode(),headers={'Content-Type':'application/json','X-Engine-Token':'private-test'})
  try:
   with urllib.request.urlopen(req,timeout=15) as r:return r.status,json.load(r)
  except urllib.error.HTTPError as e:return e.code,json.load(e)
 def test_atomic_native_roundtrips(self):
  p=self.export();c=layout(p)
  # Real engine phrase import, including two channels.
  self.assertEqual(self.cmd(35,target=0,arg=1,phrase=dict(lengthSeconds=.4,events=[[0,144,60,90],[.1,145,64,100],[.2,128,60,0],[.3,129,64,0]]))['status'],'ok')
  status,clip=self.api(action='copy',kind='phrase',source=1);self.assertEqual(status,200,clip)
  status,r=self.api(action='paste',kind='phrase',target=128,clipboardId=clip['clipboardId']);self.assertEqual(status,200,r)
  p=self.export();self.assertEqual(capture(p,'phrase',1)['events'],capture(p,'phrase',128)['events'])
  before=copy.deepcopy(p)
  status,r=self.api(action='paste',kind='phrase',target=128,clipboardId=clip['clipboardId']);self.assertEqual(status,422,r)
  self.assertEqual(self.export()['memory'],before['memory'])
  status,r=self.api(action='paste',kind='phrase',target=128,mode='swap',clipboardId=clip['clipboardId']);self.assertEqual(status,200,r)
  # Real native snapshot capture then worker clipboard clone.
  self.assertEqual(self.cmd(20)['status'],'ok');s=self.c.request();ident=s['snapshots'][0]['id']
  status,clip=self.api(action='copy',kind='snapshot',source=ident);self.assertEqual(status,200,clip)
  status,r=self.api(action='paste',kind='snapshot',clipboardId=clip['clipboardId']);self.assertEqual(status,200,r)
  self.assertEqual(len(self.c.request()['snapshots']),2)
  # Clone an actual Conductor with source references retained and UUIDs renewed.
  p=self.export();m=model(p);import uuid
  uid=lambda:str(uuid.uuid4())
  m['switches']=[dict(switchId=1,traversal='SEQUENTIAL',transition='IMMEDIATE',gesture='INSTANT',steps=[dict(id=uid(),transition='INHERIT',layers=[dict(id=uid(),block=dict(id=uid(),type='PHRASE',sourceId=m['sources'][0]['id'],overrides={}))])])]
  movement=dict(id=uid(),name='TEST',target=dict(type='CC',channel=1,number=5),points=[[0,0],[1,1]],duration=1,interpolation='LINEAR',retrigger='SOFT_RESTART',glideSeconds=.2)
  m['movements']=[movement];p['conductor']=encode(m)
  self.assertEqual(self.cmd(5,target=8,arg=1,patch=p)['status'],'ok')
  for kind,source in [('switch',1),('movement',movement['id'])]:
   status,clip=self.api(action='copy',kind=kind,source=source);self.assertEqual(status,200,clip)
   status,r=self.api(action='paste',kind=kind,clipboardId=clip['clipboardId']);self.assertEqual(status,200,r)
  restored=self.export();self.assertEqual(len(model(restored)['switches']),2);self.assertEqual(len(model(restored)['movements']),2)
  status,r=self.api(action='paste',kind='snapshot',clipboardId='expired');self.assertEqual(status,422,r)
  # Version guard refuses a stale client before any patch mutation.
  s=self.c.request();self.assertNotEqual(self.c.request(op=4,arg=1,revision=s['revision']-1,session=s['engineSessionId']).get('format'),'MIDI_HUMAN_LOOPER_PATCH')

if __name__=='__main__':unittest.main()
