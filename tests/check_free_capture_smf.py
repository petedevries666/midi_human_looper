"""Compare actual shared/native capture memory with production SMF tick data."""
import json, struct, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'headless'))
from phrase_midi import write_smf, vlq
sources=[json.loads(line) for line in Path(sys.argv[1]).read_text().splitlines()]
assert len(sources)==36,len(sources)
for source in sources:
    raw=write_smf(source); ppq=struct.unpack_from('>H',raw,12)[0]
    pos=22; tick=0; notes=[]
    while pos<len(raw):
        delta,pos=vlq(raw,pos,len(raw));tick+=delta
        status=raw[pos];pos+=1
        if status==255:
            pos+=1;length,pos=vlq(raw,pos,len(raw));pos+=length
        else:
            note,velocity=raw[pos:pos+2];pos+=2
            notes.append((tick,status,note,velocity))
    expected=[(round(e[0]*2*ppq),*e[1:]) for e in source['events']]
    assert notes==expected,(notes,expected)
    assert notes[0][0]==notes[1][0]==0,notes
    assert notes[2][0]>0,notes
print('PASS 36 shared/native free captures: actual exported ticks, same-block chords and durations')
