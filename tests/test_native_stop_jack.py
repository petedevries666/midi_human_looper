"""Opt-in native STOP/PANIC audit on an existing JACK server.

Creates only its own disconnected MIDI client. Never starts/stops JACK, connects
hardware or reads user patches. NATIVE_STOP_JACK=1 enables it; an optional
NATIVE_STOP_BUDGET_MS checks the observed callback deadline on qualified hardware.
"""
import csv,json,os,pathlib,subprocess,sys,tempfile,time,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'headless'))
from native_capacity import build_source,layout
from server import Control

@unittest.skipUnless(os.environ.get('NATIVE_STOP_JACK')=='1','Explicit JACK audit opt-in required')
class NativeStopJack(unittest.TestCase):
 def test_global_stop_replay_preserves_sources_and_bounds_callbacks(self):
  with tempfile.TemporaryDirectory(prefix='mbmf-stop-jack-') as tmp:
   folder=pathlib.Path(tmp);sock=folder/'control.sock';trace=folder/'trace.csv';source=folder/'native.jsfx'
   source.write_text(build_source((ROOT/'midi_human_looper.jsfx').read_text()))
   binary=os.environ.get('HEADLESS_BINARY',str(ROOT/'.build/midi-headless-engine'))
   intervals=[]
   with (folder/'engine.log').open('w') as log:
    worker=subprocess.Popen([binary,str(source),str(sock),'--jack','--chain','--chain-timing','2','--client','mbmf_stop_test_'+str(os.getpid()),'--rt-trace',str(trace)],stdout=log,stderr=log)
    try:
     deadline=time.monotonic()+15
     while not sock.exists():
      self.assertIsNone(worker.poll(),(folder/'engine.log').read_text())
      self.assertLess(time.monotonic(),deadline);time.sleep(.02)
     c=Control(str(sock))
     def command(op=40,arg=0,**kw):
      s=c.request();reply=c.request(op=op,arg=arg,revision=s['revision'],session=s['engineSessionId'],**kw)
      if op==4:self.assertEqual(reply['schema'],8)
      else:self.assertEqual(reply['status'],'ok')
      return reply
     patch=command(op=4);cfg=layout(patch);base=127*10240
     patch['memory'][base:base+10]=[0,144,67,90,0,4800,128,67,0,0]
     patch['memory'][cfg['COUNT_BASE']+127]=2;patch['memory'][cfg['LEN_BASE']+127]=9600
     for mode in (0,1,2):
      patch['memory'][cfg['MODE_BASE']+127]=mode
      command(op=5,target=8,patch=patch);time.sleep(.3)
      for op in (40,2,40,2):
       command(arg=7,target=127);time.sleep(.02)
       self.assertTrue(c.request()['instances'])
       start=time.monotonic_ns();command(op=op,target=0);end=time.monotonic_ns()
       intervals.append((start,end));time.sleep(.3)
       stopped=c.request();self.assertFalse(stopped['instances']);self.assertFalse(stopped['activeNotes'])
       self.assertFalse(stopped['chainRunning']);self.assertEqual(stopped['pendingOutput'],0)
       before=stopped['midiCount'];time.sleep(.06);self.assertEqual(c.request()['midiCount'],before)
      after=command(op=4);allowed=set(range(cfg['TRIG_BASE'],cfg['TRIG_BASE']+128))
      self.assertEqual(len(patch['memory']),len(after['memory']))
      self.assertTrue(all(a==b or i in allowed for i,(a,b) in enumerate(zip(patch['memory'],after['memory']))))
     # A new play requested immediately after STOP must wait for cleanup, then
     # survive it; a later cleanup chunk must never erase the new voice.
     command(arg=7,target=127);command(op=40,target=0)
     command(arg=7,target=127);time.sleep(.025)
     self.assertTrue(c.request()['instances'])
     command(op=40,target=0);time.sleep(.3)
     self.assertFalse(c.request()['instances'])
    finally:
     worker.terminate();worker.wait(timeout=15)
   rows=list(csv.DictReader(line for line in trace.read_text().splitlines() if not line.startswith('#')))
   maximum=max(float(row['wall_ns'])/1e6 for row in rows if any(a<=int(row['entry_ns'])<=b+10000000 for a,b in intervals))
   print(json.dumps(dict(operations=len(intervals),maxStopBlockMs=maximum)),flush=True)
   budget=os.environ.get('NATIVE_STOP_BUDGET_MS')
   if budget:self.assertLess(maximum,float(budget))

if __name__=='__main__':unittest.main(verbosity=2)
