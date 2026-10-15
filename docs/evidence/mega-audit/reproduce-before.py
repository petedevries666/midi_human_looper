import sys,json,copy,time,statistics,tracemalloc,os,subprocess
from pathlib import Path
root=Path(os.environ.get('MBMF_AUDIT_ROOT',Path(__file__).resolve().parents[3]));sys.path[:0]=[str(root/'tests'),str(root/'headless')]
from test_headless_mvp import HeadlessTests
from server import Control
import urllib.request,urllib.error
HeadlessTests.setUpClass();api=HeadlessTests('runTest')
try:
 api.command('panic');control=Control(api.sock);patch=control.request(op=4,revision=api.call()['revision'],session=api.call()['engineSessionId'])
 findings=[]
 for extension in ('controllerEngine','globalSnapshots'):
  document=copy.deepcopy(patch);document[extension]['futurePerformanceData']={'doNotDiscard':[1,2,3]}
  path=Path(api.temp.name)/'patches/patch1.json';path.parent.mkdir(exist_ok=True);path.write_text(json.dumps(document))
  before=path.read_bytes();state=api.call()
  req=urllib.request.Request(api.base+'/api/v1/patch/save',data=json.dumps(dict(slot=1,expectedRevision=state['revision'],expectedEngineSessionId=state['engineSessionId'])).encode(),headers={'Content-Type':'application/json'})
  try:response=urllib.request.urlopen(req)
  except urllib.error.HTTPError as error:response=error
  findings.append(dict(extension=extension,http=response.status,preserved=path.read_bytes()==before,unknownPresent='futurePerformanceData' in json.loads(path.read_text())[extension]))
 # Actual snapshot payload; all timing is Python-worker JSON encoding, not JACK.
 state=control.observation();samples=[];tracemalloc.start()
 for _ in range(9):
  start=time.process_time_ns()
  for _ in range(256):json.dumps(state,separators=(',',':')).encode()
  samples.append((time.process_time_ns()-start)/256/1000)
 peak=tracemalloc.get_traced_memory()[1];tracemalloc.stop()
 report=dict(sourceRevision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),runtimeBuildRevision=state['buildRevision'],findings=findings,encodingBenchmark=dict(payloadBytes=len(json.dumps(state,separators=(',',':')).encode()),iterationsPerSample=256,samplesUs=samples,medianUs=statistics.median(samples),tracemallocPeak=peak,scope='Python observation serialization only; CPU time with tracemalloc overhead, not a JACK measurement'))
 Path('/tmp/mbmf-audit-reproduction.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
finally:HeadlessTests.tearDownClass()
