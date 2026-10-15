import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'headless'))
from reliability_report import summarize

class ReliabilityTests(unittest.TestCase):
    def state(self,**changes):
        return dict(dict(engineSessionId=1,backend='jack',sampleRate=48000,blockSize=256,
                         lateBlocks=0,outputOverflow=0,maxCallbackUs=500,
                         chainError=0,chainFrameGap=0,chainClockGap=0),**changes)
    def test_interval_without_diagnostics_is_not_certification(self):
        result=summarize([self.state(),self.state()])
        self.assertEqual(result['problems'],[])
        self.assertIn('not hardware certification',result['qualification'])
    def test_missed_callback_even_below_callback_deadline(self):
        result=summarize([self.state(),self.state(lateBlocks=1,chainFrameGap=256,chainClockGap=256)])
        self.assertIn('lateBlocks increased',result['problems'])
        self.assertIn('transport/recording interruption reported',result['problems'])
    def test_restarts_and_counter_resets_cannot_mask_failure(self):
        result=summarize([self.state(lateBlocks=5),self.state(engineSessionId=2)])
        self.assertIn('engineSessionId changed: interval cannot be compared',result['problems'])
        self.assertIn('lateBlocks counter reset',result['problems'])
    def test_deadline_and_mock_backend(self):
        result=summarize([self.state(),self.state(maxCallbackUs=6000,backend='mock')])
        self.assertEqual(len(result['problems']),2)
    def test_queue_overflow_is_retained(self):
        result=summarize([self.state(),self.state(outputOverflow=1)])
        self.assertIn('outputOverflow increased',result['problems'])
    def test_invalid_metrics_cannot_pass(self):
        for value in (None,float('nan'),float('inf'),-1,0):
            with self.assertRaises(ValueError):
                summarize([self.state(),self.state(sampleRate=value)])
if __name__=='__main__':unittest.main()
