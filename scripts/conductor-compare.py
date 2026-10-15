#!/usr/bin/env python3
"""PR A differential audit. Private Cloud fixtures only, never deploys or merges.

A shared binary is valid ONLY when both checkouts have identical production code.
Counterexamples retain exit 1; no failure is silently retried or converted to PASS.
"""
import argparse, datetime, hashlib, json, os, platform, signal, subprocess, sys, time
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--base',type=Path,required=True)
p.add_argument('--candidate',type=Path,required=True)
p.add_argument('--binary',type=Path,required=True)
p.add_argument('--probe',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
p.add_argument('--tests',default='jack,original,a,unmodified,pending,editor,interruption')
p.add_argument('--repetitions',type=int,default=2)
a=p.parse_args()
if not 1<=a.repetitions<=4:p.error('repetitions must be 1..4')
base=a.base.resolve();candidate=a.candidate.resolve();output=a.output.resolve();output.mkdir(parents=True,exist_ok=True)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def git(root,*args):return subprocess.check_output(['git',*args],cwd=root,text=True).strip()
files=git(base,'ls-files','midi_human_looper.jsfx','headless','modules','zynthian').splitlines()
assert all((base/name).read_bytes()==(candidate/name).read_bytes() for name in files),'Different production code: build/use per-version binaries, not this PR A-only harness'
assert not git(base,'status','--porcelain','--untracked-files=no'),'Base must be a clean tracked checkout'
for name,root in [('original',base),('a',candidate)]:
    (output/f'browser-{name}.py').write_bytes((root/'tests/test_hardware_feedback_browser.py').read_bytes())
cases={'jack':lambda root:root/'tests/test_zynthian_chains.py',
       'original':lambda root:output/'browser-original.py',
       'a':lambda root:output/'browser-a.py',
       'unmodified':lambda root:root/'tests/test_hardware_feedback_browser.py',
       'pending':lambda root:candidate/'tests/conductor_diagnostics/pending_edit.py',
       'editor':lambda root:candidate/'tests/conductor_diagnostics/editor_click.py',
       'interruption':lambda root:candidate/'tests/conductor_diagnostics/callback_interruption.py'}
selected=a.tests.split(',')
if set(selected)-set(cases):p.error('unknown test selection')
env={**os.environ,'HEADLESS_BINARY':str(a.binary.resolve()),'CHAIN_JACK_PROBE':str(a.probe.resolve()),
     'CHAIN_JACK_BLOCK':'8192','CHAIN_TIMING_VERSION':'2','RUN_CHAIN_BROWSER':'1','TEST_PYTHON':sys.executable}
report={'versions':{'base':git(base,'rev-parse','HEAD'),'A':git(candidate,'rev-parse','HEAD')},
        'spec':'73cdee5604992ca3bd68e4c6c3b97c545333b127','machine':platform.machine(),
        'python':sys.version,'binarySha256':sha(a.binary.resolve()),'probeSha256':sha(a.probe.resolve()),
        'productionHashes':{name:sha(base/name) for name in files},
        'protocol':'serialized alternating base/A then A/base; fixed number of trials; assertions unchanged',
        'environment':{k:env.get(k) for k in ('JACKD','JACK_DRIVER_DIR','CHAIN_JACK_BLOCK','CHAIN_TIMING_VERSION','RUN_CHAIN_BROWSER','CHROMIUM_PATH')},'runs':[]}
order=[]
for repeat in range(a.repetitions):order.extend(('base','A') if repeat%2==0 else ('A','base'))
for case in selected:
    for number,version in enumerate(order,1):
        root=base if version=='base' else candidate;script=cases[case](root)
        path=output/f'{case}-{number}-{version}.log'
        entry={'test':case,'order':number,'version':version,'startedUTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'scriptSha256':sha(script),'log':path.name,'loadBefore':os.getloadavg()}
        print('START',case,number,version,flush=True);start=time.monotonic()
        with path.open('w') as log:
            child=subprocess.Popen([sys.executable,str(script)],cwd=root,env={**env,'COMPARE_ROOT':str(root),'PYTHONPATH':str(root/'tests')},stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            try:entry['returnCode']=child.wait(timeout=240)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid,signal.SIGTERM)
                try:child.wait(timeout=5)
                except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
                entry['returnCode']=124
        text=path.read_text();entry.update(seconds=round(time.monotonic()-start,3),loadAfter=os.getloadavg(),logSha256=sha(path))
        if 'FAIL contract:' in text and 'POSITIVE CONTROL' in text:entry['outcome']='REPRODUCED_UNMET_CONTRACT'
        elif entry['returnCode']:entry['outcome']='FAIL_OR_FIXTURE_ERROR'
        else:entry['outcome']='PASS'
        report['runs'].append(entry);(output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
        print('END',case,number,version,'exit',entry['returnCode'],entry['outcome'],flush=True)
# A comparison containing actual or reproduced failures is deliberately non-green.
sys.exit(1 if any(r['returnCode'] for r in report['runs']) else 0)
