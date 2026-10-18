#!/usr/bin/env python3
"""Run the unchanged legacy sequence assertion and log its actual reply on failure.
Use HEADLESS_BINARY to compare real native builds. Never changes assertions.
"""
import inspect,json,unittest
from test_native_free_capture import FreeCapture
class Observed(FreeCapture):
    def assertEqual(self,a,b,*args,**kwargs):
        if a!=b:
            state=inspect.currentframe().f_back.f_locals.get('state',{})
            if isinstance(state,dict) and 'lastEvent' in state:
                print('M4 FAILURE REPLY',json.dumps({k:state[k] for k in
                      ('buildRevision','lastEvent','sampleClock','instances','switches') if k in state}),flush=True)
        return super().assertEqual(a,b,*args,**kwargs)
if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite([
        Observed('test_controller_removal_sequence_and_clear_patch')]))
    raise SystemExit(not result.wasSuccessful())
