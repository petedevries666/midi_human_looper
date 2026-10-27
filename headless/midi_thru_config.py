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
