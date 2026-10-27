"""Versioned patch rules use stable source IDs, never transient JACK slots."""
LIMIT=16_777_215
SLOTS=16


def decode(extension):
    if not isinstance(extension,dict) or set(extension)!={'version','configuration'} or type(extension['version']) is not int or extension['version']!=1:
        raise ValueError('Unsupported MIDI THRU configuration; original retained')
    wire=extension['configuration']
    if not isinstance(wire,list) or len(wire)<2 or any(type(v) is not int for v in wire) or wire[0]!=1 or not 0<=wire[1]<=SLOTS or len(wire)!=2+wire[1]*17:
        raise ValueError('Invalid MIDI THRU carrier')
    rows=[];seen=set()
    for at in range(2,len(wire),17):
        ident=wire[at];channels=wire[at+1:at+17]
        if not 1<=ident<=LIMIT or ident in seen or any(v not in (-1,0,1,2) for v in channels):
            raise ValueError('Invalid MIDI THRU source or channel policy')
        rows.append({'sourceId':ident,'channels':channels});seen.add(ident)
    return rows


def wire(extension):
    decode(extension)
    return extension['configuration']


def validate_inputs(values):
    if not isinstance(values,list) or len(values)<2 or any(type(v) is not int for v in values) or values[0]!=1 or not 0<=values[1]<SLOTS or len(values)!=2+values[1]*19:
        raise ValueError('Invalid MIDI input runtime carrier')
    slots=set();sources=set()
    for at in range(2,len(values),19):
        slot,source,connected=values[at:at+3]
        if not 1<=slot<SLOTS or slot in slots or not 1<=source<=LIMIT or source in sources or connected not in (0,1) or any(mode not in (0,1,2) for mode in values[at+3:at+19]):
            raise ValueError('Invalid MIDI input runtime source or policy')
        slots.add(slot);sources.add(source)
    return values
