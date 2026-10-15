"""Private dummy JACK negative control, no application, notes or automation."""
import argparse,csv,gzip,json,os,subprocess,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--seconds',type=int,default=20);p.add_argument('--buffers',default='256,512');a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
for frames in map(int,a.buffers.split(',')):
 d=a.output/str(frames);d.mkdir(exist_ok=True);env=dict(os.environ,JACK_DEFAULT_SERVER='mbmf-idle-'+str(os.getpid()));server=None
 with (d/'jack.log').open('w') as log:
  try:
   server=subprocess.Popen([env['JACKD'],'--name',env['JACK_DEFAULT_SERVER'],'--no-realtime','-d','dummy','-r','48000','-p',str(frames)],env=env,stdout=log,stderr=subprocess.STDOUT);time.sleep(1)
   result=subprocess.run([env['IDLE_JACK_PROBE'],str(d/'callback.csv'),str(a.seconds)],env=env,text=True,capture_output=True,timeout=a.seconds+15);(d/'probe.log').write_text(result.stderr);assert result.returncode==0,result.stderr
   r=json.loads(result.stdout);rows=[{k:int(v) for k,v in x.items()} for x in csv.DictReader(s for s in (d/'callback.csv').read_text().splitlines() if not s.startswith('#'))];rows=[x for x in rows if r['startNs']<=x['entry_ns']<=r['endNs']];v=sorted(x['wall_ns'] for x in rows)
   r.update(frames=frames,engine=False,phrases=0,movements=0,physicalHardware=False,callbacks=len(rows),wall=dict(p95Us=v[int((len(v)-1)*.95)]/1000,p99Us=v[int((len(v)-1)*.99)]/1000,maxUs=v[-1]/1000),deadlineOverruns=sum(x>frames/48000*1e9 for x in v),slowest=sorted(rows,key=lambda x:x['wall_ns'],reverse=True)[:5]);(d/'summary.json').write_text(json.dumps(r,indent=2)+'\n');print(frames,'no engine',r['wall'],'XRUN',r['xruns'],'overruns',r['deadlineOverruns'],flush=True)
   with gzip.open(d/'callback.csv.gz','wb') as out:out.write((d/'callback.csv').read_bytes())
   (d/'callback.csv').unlink()
  finally:
   if server:server.terminate();server.wait(timeout=10)
