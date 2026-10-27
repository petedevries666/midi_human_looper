import pathlib
import sys
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'headless'))
from native_expressive_config import decode

def valid():
    return {'version':1,'configuration':[1,1,1,10,1,15.5,-2,50,1,1,1,42,80,11,1,50,3,1,1,64,127,127,1]}

class NativeExpressiveConfigTests(unittest.TestCase):
    def test_round_trip_shape(self):
        row=decode(valid())[0]
        self.assertEqual(row[0:3],(1,10,1))
        self.assertEqual(row[3:11],(15.5,-2,50,1,1,1,42,80))
        self.assertEqual(row[11:14],(11,1,50))
        self.assertEqual(row[14],[(1,1),(64,127),(127,1)])

    def test_reject_duplicate_instrument(self):
        d=valid();row=d['configuration'][2:];d['configuration']=[1,2]+row+row
        with self.assertRaises(ValueError):decode(d)

    def test_reject_nonmonotone_curve(self):
        d=valid();d['configuration'][-4]=1
        with self.assertRaises(ValueError):decode(d)

    def test_reject_bad_live_latency_and_old_schema(self):
        d=valid();d['configuration'][12]=2001
        with self.assertRaises(ValueError):decode(d)
        d=valid();d['version']=2
        with self.assertRaises(ValueError):decode(d)

if __name__=='__main__':unittest.main()
