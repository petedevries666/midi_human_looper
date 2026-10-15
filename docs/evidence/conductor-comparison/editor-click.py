import datetime,hashlib,json,os,platform,signal,subprocess,time
from pathlib import Path
OUT=Path('/tmp/mbmf-ab-compare');BASE=Path('/workspace/mbmf-conductor-base');A=Path('/workspace/mbmf-conductor-a')
PYTHON='/workspace/setup-tools/venv/bin/python';BINARY=str(BASE/'.build/midi-headless-engine')
env={**os.environ,'HEADLESS_BINARY':BINARY,'JACKD':'/workspace/scratch/midi-deps/root/usr/bin/jackd','JACK_DRIVER_DIR':'/workspace/scratch/midi-deps/root/usr/lib/x86_64-linux-gnu/jack','CHAIN_JACK_BLOCK':'8192','CHAIN_TIMING_VERSION':'2','CHAIN_JACK_PROBE':'/tmp/mbmf-compare-chain-probe','CHROMIUM_PATH':'/usr/bin/chromium','RUN_CHAIN_BROWSER':'1','TEST_PYTHON':PYTHON}
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
report={'versions':{'base':'25fcb1e458ffdce7286ff4c60cd4546d586e19a4','A':'706f90ca7f22d0ee5d8dcdcac361861143ef5519'},'spec':'73cdee5604992ca3bd68e4c6c3b97c545333b127','protocol':'Two repetitions each per checkout/test, order base/A/A/base, serialized, identical shared production binary and probe; diagnostic Chromium script leaves original assertions/timeouts unchanged','machine':platform.machine(),'python':subprocess.check_output([PYTHON,'--version'],text=True).strip(),'chromium':subprocess.check_output(['/usr/bin/chromium','--version'],text=True).strip(),'binarySha256':sha(BINARY),'probeSha256':sha(env['CHAIN_JACK_PROBE']),'testHashes':{name:sha(OUT/f'browser-{name}.py') for name in ('original','a')},'environment':{k:env[k] for k in ('HEADLESS_BINARY','JACKD','JACK_DRIVER_DIR','CHAIN_JACK_BLOCK','CHAIN_TIMING_VERSION','CHROMIUM_PATH','RUN_CHAIN_BROWSER')},'runs':[]}
(OUT/'editor-click.json').write_text(json.dumps(report,indent=2)+'\n')
for test in ('editor-click-loss',):
 for order,version in enumerate(('base','A','A','base'),1):
  root=BASE if version=='base' else A
  command=[PYTHON,str(root/'tests/test_hardware_feedback_browser.py')] if test=='chromium-unmodified' else [PYTHON,str(OUT/('browser-editor-click-loss.py' if test=='editor-click-loss' else 'jack-interruption.py'))]
  localenv={**env,'PYTHONPATH':str(root/'tests'),'COMPARE_ROOT':str(root)}
  path=OUT/f'{test}-{order}-{version}.log';started=time.monotonic();entry={'test':test,'order':order,'version':version,'startedUTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'loadBefore':os.getloadavg(),'log':path.name}
  print('START',test,order,version,flush=True)
  with path.open('w') as log:
   child=subprocess.Popen(command,cwd=root,env=localenv,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
   try:entry['returnCode']=child.wait(timeout=240)
   except subprocess.TimeoutExpired:
    os.killpg(child.pid,signal.SIGTERM)
    try:child.wait(timeout=5)
    except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
    entry['returnCode']=124
  entry['seconds']=round(time.monotonic()-started,3);entry['loadAfter']=os.getloadavg();entry['logSha256']=sha(path)
  report['runs'].append(entry);(OUT/'editor-click.json').write_text(json.dumps(report,indent=2)+'\n')
  print('END',test,order,version,'exit',entry['returnCode'],'seconds',entry['seconds'],flush=True)
print('COMPARISON COMPLETE',flush=True)
