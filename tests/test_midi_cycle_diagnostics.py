import unittest
from midi_cycle_diagnostics import analyze
class Cycles(unittest.TestCase):
 def test_actual_reproduced_clock_repeat_retains_all_events(self):
  events=[[159744,64,144,61,100,151,38400,20],[159744,48,176,20,66,152,38656,20]]
  before=[x[:] for x in events];r=analyze(events,256)
  self.assertEqual(r['absoluteTimestampAmbiguityCount'],1);self.assertEqual(events,before)
 def test_same_callback_wrong_order_must_fail(self):
  with self.assertRaisesRegex(AssertionError,'inside receiver cycle'):analyze([[100,64,144,61,100,1,0,0],[100,48,128,61,0,1,0,0]],256)
 def test_normal_cycle_and_equal_timestamp_order(self):
  r=analyze([[100,64,144,61,100,1,0,0],[100,64,128,61,0,1,0,0],[356,16,144,62,90,2,256,0]],256)
  self.assertEqual(r['clockDiscontinuityCount'],0)
 def test_position_and_offset_corruption_never_hidden(self):
  with self.assertRaises(AssertionError):analyze([[0,0,144,60,100,1,0,0],[256,0,128,60,0,2,128,0]],256)
  with self.assertRaises(AssertionError):analyze([[0,256,144,60,100,1,0,0]],256)
if __name__=='__main__':unittest.main()
