#!/usr/bin/env python3
"""Opt-in interruption of a private Cloud JACK fixture; never a device updater.
The positive three-chain test is unchanged and must run separately.
"""
import os,sys
from pathlib import Path
root=Path(os.environ.get('COMPARE_ROOT',Path(__file__).resolve().parents[2])).resolve()
sys.path.insert(0,str(root/'tests'))
source=(root/'tests/test_zynthian_chains.py').read_text()
source=source.replace('ROOT=Path(__file__).resolve().parents[1]', 'ROOT=Path(os.environ["COMPARE_ROOT"])')
os.environ['COMPARE_ROOT']=str(root)
source=source.replace('import importlib.util,json,os,subprocess,sys,tempfile,time,types', 'import importlib.util,json,os,subprocess,sys,tempfile,time,types,signal')
source=source.replace('BLOCK=int(os.environ.get', 'class ExpectedInterruption(Exception):pass\nBLOCK=int(os.environ.get',1)
needle="            wait(i,'chainRecording',True);wait(i,'chainRecording',False)"
replacement="            wait(i,'chainRecording',True)\n            # Fault only the private process this fixture just started. The\n            # original positive JACK test stays intact and runs separately.\n            worker=engines[i-1].instances[i]['engine']\n            os.kill(worker.pid,signal.SIGSTOP)\n            time.sleep(.6)\n            os.kill(worker.pid,signal.SIGCONT)\n            deadline=time.monotonic()+5\n            interrupted=state(i)\n            while not interrupted['chainError'] and time.monotonic()<deadline:\n                time.sleep(.02);interrupted=state(i)\n            source(0)\n            assert interrupted['chainError']==1,interrupted\n            assert not interrupted['chainRecording'] and not interrupted['chainRunning'],interrupted\n            assert interrupted['activeNotes']==0 and interrupted['outputOverflow']==0,interrupted\n            print('INJECTED GAP RESULT',json.dumps({key:interrupted[key] for key in (\n                'chainError','chainRecording','chainRunning','activeNotes','outputOverflow',\n                'lateBlocks','chainFrameGap','chainClockGap','maxCallbackUs')}),flush=True)\n            raise ExpectedInterruption()\n\n"
assert source.count(needle)==1,'JACK fixture changed: review the injection before execution'
source=source.replace(needle,replacement,1)
needle='    finally:\n        if sys.exc_info()[0]:'
assert source.count(needle)==1,'JACK cleanup fixture changed: review before execution'
source=source.replace(needle,"    except ExpectedInterruption:\n        print('PASS controlled callback interruption: existing guard aborts recording, no active notes/overflow',flush=True)\n"+needle,1)
exec(compile(source,str(root/'tests/test_zynthian_chains.py'), 'exec'), {'__name__':'__main__'})
