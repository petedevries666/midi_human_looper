"""Read-only diagnostic wording and storm guard, no JACK service commands."""
import contextlib, importlib.util, io
from pathlib import Path
import unittest
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('smoke',Path(__file__).resolve().parents[1]/'scripts/zynthian-m3-safe-smoke.py')
smoke=importlib.util.module_from_spec(spec);spec.loader.exec_module(smoke)
class Smoke(unittest.TestCase):
    def run_case(self,old,new):
        output=io.StringIO()
        with patch('sys.argv',['smoke','--seconds','1']), patch.object(smoke,'virtual_targets',return_value=['ZynMidiRouter:dev2_in']), patch.object(smoke,'status',side_effect=[old,new]), patch.object(smoke,'emergency_disconnect') as disconnect, patch.object(smoke.time,'monotonic',side_effect=[0,0,0,2]), patch.object(smoke.time,'sleep'), contextlib.redirect_stdout(output):
            result=smoke.main()
        return result,output.getvalue(),disconnect.call_count
    def test_legacy_never_claims_delivery(self):
        a=dict(status='ok',midiCount=100,lateBlocks=0,chainError=0,outputOverflow=0)
        result,out,n=self.run_case(a,dict(a,midiCount=103))
        self.assertEqual((result,n),(0,0));self.assertIn('legacy generation counter',out)
        self.assertNotIn('emitted MIDI',out)
    def test_boundary_counts_reported_separately(self):
        a=dict(status='ok',midiCount=100,midiGenerated=100,midiReceived=20,midiWritten=60,
               midiDropped=0,midiWriteFailures=0,midiRecoveries=0,lateBlocks=0)
        result,out,n=self.run_case(a,dict(a,midiCount=103,midiGenerated=103,midiReceived=22,midiWritten=61))
        self.assertEqual((result,n),(0,0));self.assertIn("'midiWritten': 1",out)
        self.assertIn("'midiGenerated': 3",out)
    def test_receive_storm_disconnects_even_without_generated_output(self):
        a=dict(status='ok',midiCount=100,midiGenerated=100,midiReceived=20,midiWritten=60,lateBlocks=0)
        result,out,n=self.run_case(a,dict(a,midiReceived=521))
        self.assertEqual((result,n),(1,1));self.assertIn('ALERT',out)
if __name__=='__main__':unittest.main()
