#!/usr/bin/env python3
"""Delay only private fixture engines before JACK activation; preserve all tests.
Compile delayed_jack_activate.cpp as a shared library and set JACK_ACTIVATE_SHIM.
COMPARE_ROOT selects the actual source checkout; JACK_READINESS_TEST may select
an unchanged historical test for comparative diagnosis. Never use on hardware.
"""
import os
from pathlib import Path
root=Path(os.environ.get('COMPARE_ROOT',Path(__file__).resolve().parents[2])).resolve()
case=Path(os.environ.get('JACK_READINESS_TEST',root/'tests/test_jack_graph.py'))
source=case.read_text().replace('ROOT=Path(__file__).resolve().parents[1]', 'ROOT=Path(os.environ["COMPARE_ROOT"])')
os.environ['COMPARE_ROOT']=str(root)
needle='    server=subprocess.Popen'
assert source.count(needle)==1
source=source.replace(needle,'    engine_env=dict(env,LD_PRELOAD=os.environ["JACK_ACTIVATE_SHIM"],MBMF_TEST_DELAY_ACTIVATE="1")\n'+needle,1)
needle="path,'--jack','--demo'],env=env,"
assert source.count(needle)==2
source=source.replace(needle,"path,'--jack','--demo'],env=engine_env,")
needle="assert observer.wait(timeout=10)==0,'same-block timestamp/tie ordering failed'"
assert source.count(needle)==1
source=source.replace(needle,"result=observer.wait(timeout=10)\n        print('ORDERING_PROBE_EXIT',result,flush=True)\n        assert result==0,'same-block timestamp/tie ordering failed'")
exec(compile(source,str(case),'exec'),{'__name__':'__main__'})
