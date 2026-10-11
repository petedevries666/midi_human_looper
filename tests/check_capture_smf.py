"""Inspect SMF ticks generated from actual EEL capture fixtures, at the MIDI tick level."""
import json,struct,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'headless'))
from phrase_midi import write_smf,vlq
sources=[json.loads(line) for line in Path(sys.argv[1]).read_text().splitlines()]
assert len(sources)==18,len(sources)
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
    assert len(notes)==6,notes
    expected=[(0,146,65,97),(0,147,69,83),(128,130,65,31),
              (192,131,69,21),(256,146,72,91),(384,130,72,17)]
    for actual,(sample,status,note,velocity) in zip(notes,expected):
        assert actual==(round(sample/48000*2*ppq),status,note,velocity),(actual,expected,ppq)
    assert notes[0][0]==notes[1][0]==0,notes
print('PASS 18 actual capture fixtures: tick-zero multichannel chords, staggered durations and rests')
