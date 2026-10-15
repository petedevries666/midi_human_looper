"""Actual JACK input during UPDATE lease; no hardware or service activation."""
import json,os,subprocess,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'headless'),str(ROOT/'tests')]
from server import Control
from midi_cycle_diagnostics import analyze
with tempfile.TemporaryDirectory(prefix='mbmf-admission-jack-') as tmp:
 env=dict(os.environ,JACK_DEFAULT_SERVER='mbmf-admission-'+str(os.getpid()));server=engine=probe=None;logs=[]
 try:
  logs=[open(Path(tmp)/n,'w') for n in ('jack.log','engine.log')]
  server=subprocess.Popen([env['JACKD'],'--name',env['JACK_DEFAULT_SERVER'],'--no-realtime','-d','dummy','-r','48000','-p','256'],env=env,stdout=logs[0],stderr=subprocess.STDOUT);time.sleep(1)
  sock=str(Path(tmp)/'engine.sock');engine=subprocess.Popen([env['HEADLESS_BINARY'],str(ROOT/'midi_human_looper.jsfx'),sock,'--jack','--chain','--managed-admission','--client','mbmf_d'],env=env,stdout=logs[1],stderr=subprocess.STDOUT)
  end=time.monotonic()+15
  while not Path(sock).exists():
   assert engine.poll() is None
   assert time.monotonic()<end;time.sleep(.02)
  c=Control(sock)
  def command(**args):
   s=c.request();return c.request(revision=s['revision'],session=s['engineSessionId'],**args)
  command(op=2)
  for i in (2,3):assert command(op=32,target=i,arg=21,macro=[0,0])['status']=='ok'
  command(op=35,target=0,arg=1,phrase=dict(lengthSeconds=.2,events=[[0,144,67,100],[.1,128,67,0]]))
  sw=c.request()['switches'][0]['settings'];sw[:4]=[1,1,0,110];sw[11]=1;command(op=41,target=1,settings=sw+[0]*64+[0]*16)
  command(op=2);time.sleep(.2)
  probe=subprocess.Popen([env['ADMISSION_JACK_PROBE']],env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True);assert probe.stdout.readline().strip()=='READY'
  def midi(st,n,v):probe.stdin.write(f'{st} {n} {v} 16\n');probe.stdin.flush();time.sleep(.08)
  assert command(op=50,target=555)['admissionClosed']
  for message in [(144,60,100),(128,60,0),(176,1,99),(176,64,127),(176,64,0),(144,110,127),(128,110,0)]:midi(*message)
  assert not c.request()['instances'] and c.request()['activeNotes']==0
  assert command(op=50,target=556,arg=1)['status']!='ok';assert c.request()['admissionClosed']
  assert not command(op=50,target=555,arg=1)['admissionClosed']
  midi(144,62,100);assert command(op=50,target=555)['status']!='ok';midi(128,62,0)
  command(op=2);time.sleep(.15);assert command(op=50,target=555)['admissionClosed']
  midi(144,64,100);midi(128,64,0);command(op=2);assert c.request()['admissionClosed']
  assert not command(op=50,target=555,arg=1)['admissionClosed']
  midi(144,66,100);midi(128,66,0);midi(144,110,127);midi(128,110,0);time.sleep(.3);command(op=2);time.sleep(.2)
  probe.stdin.close();events=[list(map(int,s.split())) for s in probe.stdout.read().splitlines()];assert probe.wait(timeout=5)==0;analyze(events,256)
  ons=[e[3] for e in events if e[2]&240==144 and e[4]>0];assert ons==[62,66,67],ons
  assert not [e for e in events if e[2]&240==176 and (e[3:5]==[1,99] or e[3:5]==[64,127])]
  output=Path(os.environ.get('ADMISSION_JACK_EVIDENCE','/tmp/mbmf-admission-jack-evidence.json'));output.write_text(json.dumps(dict(backend='actual private JACK',physicalHardware=False,events=events,notes=ons),indent=2)+'\n')
  print('PASS actual JACK admission: closed MIDI notes/CC/sustain/Smart Switch suppressed, held-note refusal, wrong-owner refusal, no queued attacks, explicit resume, PANIC stays closed; actual notes',ons)
 finally:
  for child in (probe,engine,server):
   if child and child.poll() is None:
    child.terminate()
    try:child.wait(timeout=10)
    except subprocess.TimeoutExpired:child.kill();child.wait()
  for f in logs:f.close()
