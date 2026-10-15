import os,runpy,subprocess,tempfile
from pathlib import Path
root=Path('/workspace/mbmf-conductor-a')
base=tempfile.TemporaryDirectory
class Retain(base):
 def cleanup(self):
  self._finalizer.detach()
  print('RETAINED JACK FIXTURE',self.name,flush=True)
tempfile.TemporaryDirectory=Retain
popen=subprocess.Popen
def traced(args,*a,**kw):
 if isinstance(args,list) and args and args[0]==os.environ['HEADLESS_BINARY'] and '--rt-trace' not in args:
  args=args+['--rt-trace',str(Path(args[2]).parent/'callback.csv')]
 return popen(args,*a,**kw)
subprocess.Popen=traced
runpy.run_path(str(root/'tests/test_zynthian_chains.py'),run_name='__main__')
