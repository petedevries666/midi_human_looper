#!/usr/bin/env python3
"""Private dummy JACK: production B binary, actual port MIDI and targeted STOP.
Uses the existing bounded three-destination probe (observe destination zero).
No physical device, mocked engine or modified JSFX fixture.
"""
import json,os,subprocess,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'headless'))
from server import Control
with tempfile.TemporaryDirectory(prefix='mbmf-instance-jack-') as temp:
 env=dict(os.environ,JACK_DEFAULT_SERVER='mbmf-instance-test',CHAIN_FANOUT='1')
 log=Path(temp)/'jack.log'
 with log.open('wb') as out:
  server=subprocess.Popen([os.environ['JACKD'],'--name',env['JACK_DEFAULT_SERVER'],'--no-realtime','-d','dummy','-r','48000','-p','8192'],env=env,stdout=out,stderr=out)
 engine=probe=None
 try:
  time.sleep(1);assert server.poll() is None,log.read_text()
  sock=str(Path(temp)/'engine.sock')
  engine=subprocess.Popen([os.environ['HEADLESS_BINARY'],str(ROOT/'midi_human_looper.jsfx'),sock,'--chain','--jack','--client','mbh_1'],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  deadline=time.monotonic()+15
  while not Path(sock).exists() and time.monotonic()<deadline:
   assert engine.poll() is None,engine.stderr.read().decode();time.sleep(.05)
  c=Control(sock)
  def command(**args):
   state=c.request();result=c.request(revision=state['revision'],session=state['engineSessionId'],**args)
   assert result['status']=='ok',result
   return result
  command(op=2)
  for id in (2,3):command(op=32,target=id,arg=21,macro=[0,0])
  for phrase,pitch in ((0,60),(1,62)):
   command(op=32,target=phrase+1,arg=20,macro=[0,1])
   command(op=35,target=phrase,arg=1,phrase=dict(lengthSeconds=10,bpm=120,events=[[0,144,pitch,91],[9,128,pitch,23]]))
  probe=subprocess.Popen([os.environ['CHAIN_JACK_PROBE']],env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
  assert probe.stdout.readline().strip()=='READY'
  command(op=3,ch=0,note=60,value=100) # Real engine input, actual JACK output.
  command(op=40,target=0,arg=7);time.sleep(.2)
  a=c.request()['instances'][0]
  command(op=40,target=1,arg=7);time.sleep(.2)
  b=next(i for i in c.request()['instances'] if i['phraseId']==2)
  command(op=44,instance=(a['id'],a['generation']));time.sleep(.2)
  assert c.request()['activeNotes']==2,'targeted STOP cut held physical note'
  command(op=3,ch=0,note=60,value=0);time.sleep(.2)
  command(op=44,instance=(b['id'],b['generation']));time.sleep(.2)
  command(op=2);time.sleep(.3)
  state=c.request();assert state['activeNotes']==0 and state['outputOverflow']==0,state
  probe.stdin.close();lines=probe.stdout.read().splitlines();assert probe.wait(timeout=5)==0;probe=None
  events=[list(map(int,line.split())) for line in lines]
  own=[e for e in events if e[0]==0 and (e[3]&240) in (128,144)]
  notes=[[e[3],e[4],e[5]] for e in own]
  assert notes==[[144,60,100],[144,60,91],[144,62,91],[128,60,0],[128,62,0]],notes
  assert all(a[1]+a[2]<=b[1]+b[2] for a,b in zip(own,own[1:])),own
  print('PASS actual JACK ownership: targeted STOP preserves live note, final releases and stable ordering',json.dumps(own),flush=True)
 finally:
  if probe is not None:probe.terminate();probe.communicate(timeout=5)
  if engine is not None:engine.terminate();engine.communicate(timeout=10)
  server.terminate();server.wait(timeout=5)
