#!/usr/bin/env python3
import io,struct,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'headless'))
from phrase_midi import read_smf,write_smf,encode_vlq

def fixture():
    # Format 1 with REAPER-style separate conductor track, running status,
    # overlapping repeated pitches, chord, rests, and velocity-zero release.
    conductor=b'\0\xff\x51\x03\x07\xa1\x20\0\xff\x58\x04\x04\x02\x18\x08'+encode_vlq(960)+b'\xff\x2f\0'
    notes=b'\0\x92\x3c\x64\0\x40\x5a'+encode_vlq(120)+b'\x3c\x50'+encode_vlq(120)+b'\x82\x3c\x20\0\x40\x00'+encode_vlq(120)+b'\x92\x3c\0'+encode_vlq(600)+b'\xff\x2f\0'
    return b'MThd'+struct.pack('>IHHH',6,1,2,480)+b''.join(b'MTrk'+struct.pack('>I',len(t))+t for t in (conductor,notes))

class SMFTests(unittest.TestCase):
    def test_format1_running_chords_and_roundtrip(self):
        phrase=read_smf(fixture());self.assertEqual(phrase['noteCount'],3)
        self.assertEqual(phrase['meters'],[[0,4,4]])
        self.assertEqual([e[0] for e in phrase['events']],[0,0,.125,.25,.25,.375])
        restored=read_smf(write_smf(phrase));self.assertEqual(restored['events'],phrase['events'])
        import mido
        independent=mido.MidiFile(file=io.BytesIO(write_smf(phrase)))
        self.assertEqual(independent.type,0);self.assertAlmostEqual(independent.length,1)
        self.assertEqual(sum(m.type=='note_on' and m.velocity>0 for m in independent.tracks[0]),3)
    def test_tempo_change_preserves_source_seconds(self):
        t=b'\0\xff\x51\x03\x07\xa1\x20\0\x90\x3c\x64'+encode_vlq(480)+b'\xff\x51\x03\x0f\x42\x40'+encode_vlq(480)+b'\x80\x3c\0\0\xff\x2f\0'
        midi=b'MThd'+struct.pack('>IHHH',6,0,1,480)+b'MTrk'+struct.pack('>I',len(t))+t
        self.assertEqual(read_smf(midi)['events'][-1][0],1.5)
    def test_malformed_and_bounded(self):
        for data in (b'',fixture()[:-1],fixture()+b'x',b'x'*1048577,fixture().replace(b'\x82\x3c\x20',b'\xb2\x01\x20')):
            with self.subTest(size=len(data)),self.assertRaises(ValueError):read_smf(data)
        for data in (b'\x81'*5,b'\x81'):
            from phrase_midi import vlq
            with self.assertRaises(ValueError):vlq(data,0,len(data))
    def test_unsupported_divisions_and_formats(self):
        for offset,value in ((8,2),(12,0),(12,0x8001)):
            data=bytearray(fixture());struct.pack_into('>H',data,offset,value)
            with self.assertRaises(ValueError):read_smf(bytes(data))
        # Too many notes: fail before any phrase mutation.
        events=[]
        for j in range(1025):events.extend([[j*.001,144,60,90],[j*.001+.0005,128,60,0]])
        with self.assertRaises(ValueError):write_smf({'events':events,'lengthSeconds':2})

    def test_empty_export_is_valid_smf(self):
        import mido
        result=mido.MidiFile(file=io.BytesIO(write_smf({'events':[], 'lengthSeconds':0})))
        self.assertEqual(result.length,0)

    def test_missing_note_off_is_not_repaired_silently(self):
        with self.assertRaises(ValueError):write_smf({'events':[[0,144,60,100]],'lengthSeconds':1})

if __name__=='__main__':unittest.main()
