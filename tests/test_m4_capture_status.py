#!/usr/bin/env python3
"""Real native API, actual bounded EEL capture errors and rollback; no fixture DSP."""
import sys,time,unittest
from pathlib import Path
from test_native_free_capture import FreeCapture
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'headless'))
from server import Control
class CaptureStatus(FreeCapture):
    def test_capture_overflow_is_distinct_from_output_overflow(self):
        c=Control(self.sock)
        def cmd(**args):
            s=c.request();r=c.request(revision=s['revision'],session=s['engineSessionId'],**args)
            self.assertEqual(r['status'],'ok',r);return r
        for event_count,attacks,reason in ((2048,1,'record_overflow'),(2046,2,'release_capacity')):
            self.command('panic');self.command('phrase_clear',phraseId=8)
            self.command('parameter_set',targetId=8,kind=20,value=1)
            events=[]
            for i in range(event_count//2):
                at=.5+i*.001
                events += [[at,146,60,81],[at+.0005,130,60,23]]
            cmd(op=35,target=7,arg=1,phrase=dict(lengthSeconds=2,bpm=120,events=events))
            original=cmd(op=35,target=7,arg=0)['phraseData']
            before=self.call();self.command('phrase_record',phraseId=8)
            for n in range(attacks):self.command('midi',channel=3,note=67+n,value=92)
            if reason=='release_capacity':self.command('phrase_finish',phraseId=8)
            self.wait_for(lambda:self.call()['chainErrorReason']==reason,'precise capture error '+reason)
            state=self.call()
            self.assertTrue(state['chainError']);self.assertEqual(state['chainErrorPhraseId'],8)
            self.assertFalse(state['chainRecording']);self.assertFalse(state['chainArmed'])
            self.assertEqual(state['captureRejected'],before['captureRejected']+1)
            self.assertEqual(state['captureOverflows']-before['captureOverflows'],int(reason=='record_overflow'))
            self.assertEqual(state['outputOverflow'],before['outputOverflow'],'capture failure is not JACK output overflow')
            self.assertEqual(cmd(op=35,target=7,arg=0)['phraseData'],original,'failed take must preserve every original event')
            for n in range(attacks):self.command('midi',channel=3,note=67+n,value=0)
            self.command('panic');self.patch('save');self.patch('load')
            self.assertEqual(cmd(op=35,target=7,arg=0)['phraseData'],original)
            self.assertFalse(self.call()['chainRunning']);self.assertFalse(self.call()['instances'])
            print('M4 actual native status',reason,{k:state[k] for k in ('chainErrorCode','chainErrorPhraseId','captureRejected','captureOverflows','outputOverflow')},flush=True)
if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite([CaptureStatus('test_capture_overflow_is_distinct_from_output_overflow')]))
    raise SystemExit(not result.wasSuccessful())
