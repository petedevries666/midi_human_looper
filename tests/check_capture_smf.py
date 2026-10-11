"""Inspect SMF ticks generated from actual EEL capture fixtures, at the MIDI tick level."""
import json,struct,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'headless'))
from phrase_midi import write_smf,vlq
sources=[json.loads(line) for line in Path(sys.argv[1]).read_text().splitlines()]
assert len(sources)==12,len(sources)
for source in sources:
    raw=write_smf(source); ppq=struct.unpack_from('>H',raw,12)[0]
    pos=22;tick=0;notes=[]
    while pos<len(raw):
        delta,pos=vlq(raw,pos,len(raw));tick+=delta
        status=raw[pos];pos+=1
        if status==255:
            pos+=1;length,pos=vlq(raw,pos,len(raw));pos+=length
        else:
            note,velocity=raw[pos:pos+2];pos+=2
            if status&240 in (128,144):notes.append((tick,status,note,velocity))
    assert notes[0][0]==0,notes
    assert abs(notes[1][0]/ppq*.5-128/48000)<.00003,notes
    assert notes[0][1]&15==2 and notes[0][3]==97
print('PASS 12 actual capture fixtures exported at tick zero with paired durations')
