#!/usr/bin/env python3
"""Production native/JACK output failure: no mathematical scheduler substitute.
The private JSFX fixture adds only a CC-triggered call to the same admission
function used by the API. Source content and all output/cleanup paths are real.
"""
import json,os,subprocess,sys,tempfile,time
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'headless'))
from server import Control
with tempfile.TemporaryDirectory(prefix='mbmf-output-fault-') as temp:
 env=dict(os.environ,JACK_DEFAULT_SERVER='mbmf-output-fault-test',CHAIN_FANOUT='1')
 source=(ROOT/'midi_human_looper.jsfx').read_text()
 injection='\n!ownership_burst_fixture && msg1==190 && d1==126 && d2==127 ? (ownership_burst_fixture=1;ownership_burst_i=0;loop(5,phrase_admit_independent(0,0);ownership_burst_i+=1;););\n'
 fixture=Path(temp)/'burst.jsfx';fixture.write_text(source.replace('\n@gfx ',injection+'\n@gfx ',1))
 log=Path(temp)/'jack.log'
 with log.open('wb') as out:
  server=subprocess.Popen([os.environ['JACKD'],'--name',env['JACK_DEFAULT_SERVER'],'--no-realtime','-d','dummy','-r','48000','-p','8192'],env=env,stdout=out,stderr=out)
 engine=probe=None
 try:
  time.sleep(1);assert server.poll() is None,log.read_text()
  sock=str(Path(temp)/'engine.sock')
  engine=subprocess.Popen([os.environ['HEADLESS_BINARY'],str(fixture),sock,'--chain','--jack','--client','mbh_1'],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
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
  command(op=32,target=1,arg=20,macro=[0,1])
  events=[[0,144,60+i%3,90] for i in range(1024)]+[[9,128,60+i%3,0] for i in range(1024)]
  command(op=35,target=0,arg=1,phrase=dict(lengthSeconds=10,bpm=120,events=events))
  original=command(op=35,target=0,arg=0)['phraseData']
  probe=subprocess.Popen([os.environ['CHAIN_JACK_PROBE']],env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
  assert probe.stdout.readline().strip()=='READY'
  command(op=19,ch=14,note=126,value=127)
  deadline=time.monotonic()+10
  state=c.request()
  while (state['instanceError']!=6 or state['pendingOutput'] or state['instances'] or state['activeNotes']) and time.monotonic()<deadline:
   time.sleep(.05);state=c.request()
  assert state['instanceError']==6 and state['outputOverflow']>0,state
  assert state['activeNotes']==0 and not state['instances'] and state['pendingOutput']==0,state
  assert command(op=35,target=0,arg=0)['phraseData']==original,'overload corrupted source MIDI'
  probe.stdin.close();lines=probe.stdout.read().splitlines();assert probe.wait(timeout=5)==0;probe=None
  actual=[list(map(int,line.split())) for line in lines if line]
  own=[e for e in actual if e[0]==0];held=Counter();ons=0;emergency=0;panicSeen=False;last=-1
  for _,frame,offset,st,note,value in own:
   assert frame+offset>=last,('nonmonotonic JACK output',own);last=frame+offset
   ch=st&15;typ=st&240
   if typ==144 and value:
    assert not panicSeen,'stale queued attack emitted after emergency cleanup'
    ons+=1;held[(ch,note)]+=1
   elif typ==128 or (typ==144 and not value):held[(ch,note)]=max(0,held[(ch,note)]-1)
   elif typ==176 and note in (120,123):
    panicSeen=True;emergency+=1;held=Counter({k:v for k,v in held.items() if k[0]!=ch})
  assert 0<ons<=128 and emergency>=32 and not any(held.values()),(ons,emergency,held)
  print('PASS actual JACK shared-buffer overload: bounded partial emission, queued attacks cancelled, stacked-note cleanup, source preserved',json.dumps(dict(ons=ons,emergency=emergency,instanceError=state['instanceError'],outputOverflow=state['outputOverflow'])),flush=True)
 finally:
  if probe is not None:probe.terminate();probe.communicate(timeout=5)
  if engine is not None:engine.terminate();engine.communicate(timeout=10)
  server.terminate();server.wait(timeout=5)
