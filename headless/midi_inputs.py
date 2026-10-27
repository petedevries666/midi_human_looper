"""Stable physical input registry shared by MIDI THRU and the Zynthian router.

The registry assigns identities, not ALSA/JACK enumeration numbers. Reading an
inventory never enrolls a device or changes the musical routing graph.
"""
import copy
import json
import os
from pathlib import Path
import re
import tempfile
from midi_thru_config import LIMIT

MAX_INPUTS=15  # Bus zero remains the existing aggregated/native test input.


def port_key(name):
    if not isinstance(name,str) or not name or len(name.encode('utf-8'))>255 or any(ord(c)<32 for c in name):
        raise ValueError('Invalid physical MIDI input name')
    # a2j's numeric ALSA client changes on reconnection; duplicate textual keys
    # remain ambiguous and are never silently attached to one of two devices.
    return re.sub(r' \[\d+\](?= \(capture\):)', '', name) if name.startswith('a2j:') else name


def channels(value,inherit=False):
    if not isinstance(value,list) or len(value)!=16 or any(type(v) is not int or v not in ((-1,0,1,2) if inherit else (0,1,2)) for v in value):
        raise ValueError('Expected 16 MIDI THRU channel policies')
    return list(value)


def validate(registry):
    if not isinstance(registry,dict) or set(registry)!={'version','nextId','defaults','sources'} or type(registry['version']) is not int or registry['version']!=1:
        raise ValueError('Unsupported MIDI input registry; original retained')
    channels(registry['defaults'])
    if type(registry['nextId']) is not int or not 1<=registry['nextId']<=LIMIT:
        raise ValueError('Invalid next MIDI input identity')
    sources=registry['sources']
    if not isinstance(sources,list) or len(sources)>256:raise ValueError('Invalid MIDI input registry size')
    ids=set();keys=set();slots=set()
    for source in sources:
        if not isinstance(source,dict) or set(source)!={'id','key','name','slot','enabled','channels'}:
            raise ValueError('Unsupported MIDI input fields; original retained')
        ident=source['id'];slot=source['slot']
        if type(ident) is not int or not 1<=ident<registry['nextId'] or ident in ids:
            raise ValueError('Invalid or duplicate MIDI source identity')
        key=port_key(source['key'])
        if key!=source['key'] or key in keys:raise ValueError('Invalid or duplicate MIDI source key')
        if type(source['enabled']) is not bool or type(slot) is not int or not 0<=slot<=MAX_INPUTS:
            raise ValueError('Invalid MIDI input slot')
        if source['enabled'] and (slot==0 or slot in slots):raise ValueError('Duplicate or missing active MIDI input slot')
        if not source['enabled'] and slot!=0:raise ValueError('Disabled input must release its runtime slot')
        if not isinstance(source['name'],str) or len(source['name'])>128:raise ValueError('Invalid MIDI input display name')
        channels(source['channels'],True)
        ids.add(ident);keys.add(key)
        if source['enabled']:slots.add(slot)
    return registry


def bootstrap(legacy_ports=()):
    registry={'version':1,'nextId':1,'defaults':[1]*16,'sources':[]}
    for name in legacy_ports:
        enroll(registry,name,name,True)
    return validate(registry)


def enroll(registry,port,name=None,enabled=True):
    validate(registry)
    if type(enabled) is not bool:raise ValueError('MIDI input enabled must be boolean')
    key=port_key(port)
    source=next((s for s in registry['sources'] if s['key']==key),None)
    # Refuse before allocating an identity: an unsuccessful edit must leave the
    # saved configuration byte-for-byte equivalent, including nextId.
    if enabled and (source is None or not source['enabled']) and sum(s['enabled'] for s in registry['sources'])>=MAX_INPUTS:
        raise ValueError('At most 15 physical MIDI inputs may be active')
    if source is None:
        if registry['nextId']>=LIMIT or len(registry['sources'])>=256:raise ValueError('MIDI source identity capacity reached')
        source={'id':registry['nextId'],'key':key,'name':str(name or port)[:128],'slot':0,'enabled':False,'channels':[-1]*16}
        registry['nextId']+=1;registry['sources'].append(source)
    occupied={s['slot'] for s in registry['sources'] if s['enabled'] and s is not source}
    slot=source['slot'] if source['slot'] and source['slot'] not in occupied else next((n for n in range(1,MAX_INPUTS+1) if n not in occupied),0)
    if enabled and not slot:raise ValueError('At most 15 physical MIDI inputs may be active')
    source['enabled']=bool(enabled);source['slot']=slot if enabled else 0
    validate(registry)
    return source


def inventory(registry,observed):
    validate(registry)
    by_key={}
    for entry in observed:
        key=port_key(entry['port'])
        by_key.setdefault(key,[]).append(entry)
    result=[]
    for source in registry['sources']:
        matches=by_key.pop(source['key'],[])
        row=copy.deepcopy(source)
        row.update(present=len(matches)==1,ambiguous=len(matches)>1,
                   port=matches[0]['port'] if len(matches)==1 else None)
        if len(matches)==1:
            aliases=matches[0].get('aliases') or []
            if aliases:row['name']=str(aliases[-1])[:128]
            row['connections']=list(matches[0].get('connections',[]))
        result.append(row)
    for key,matches in by_key.items():
        entry=matches[0];aliases=entry.get('aliases') or []
        result.append({'id':None,'key':key,'name':str(aliases[-1] if aliases else entry['port'])[:128],
                       'slot':0,'enabled':False,'channels':[-1]*16,'present':len(matches)==1,
                       'ambiguous':len(matches)>1,'port':entry['port'] if len(matches)==1 else None})
    return result


def runtime_wire(registry,observed,client=None):
    rows=[row for row in inventory(registry,observed) if row['enabled']]
    wire=[1,len(rows)]
    for row in rows:
        modes=[registry['defaults'][ch] if mode<0 else mode for ch,mode in enumerate(row['channels'])]
        connected=row['present'] and not row['ambiguous']
        if client is not None:
            connected=connected and ingress_port(client,row['slot']) in row.get('connections',[])
        wire.extend([row['slot'],row['id'],int(connected),*modes])
    return wire


def ingress_port(client,slot):
    if not isinstance(client,str) or re.fullmatch(r'mbh_\d+',client) is None or type(slot) is not int or not 1<=slot<=MAX_INPUTS:
        raise ValueError('Expected a dedicated native MBMF physical input')
    return f'{client}:midi_in_{slot}'


def ingress_plan(registry,observed,client,available_inputs):
    """Read-only plan; caller isolates native bypasses before admitting edges."""
    rows=[row for row in inventory(registry,observed) if row['enabled']]
    edges=[]
    for row in rows:
        destination=ingress_port(client,row['slot'])
        if destination not in available_inputs:
            raise ValueError('Native engine lacks isolated physical MIDI inputs; routing refused')
        if row['present'] and not row['ambiguous']:
            edges.append((row['port'],destination))
    return edges


class Store:
    """Global opt-in registry, separate from patch rules and engine voice state."""
    def __init__(self,path,legacy_ports=()):
        self.path=Path(path)
        self.legacy_ports=tuple(legacy_ports)

    def read(self):
        if self.path.is_symlink():raise ValueError('MIDI input registry must not be a symbolic link')
        if not self.path.exists():return bootstrap(self.legacy_ports)
        if self.path.stat().st_size>262144:raise ValueError('MIDI input registry is too large')
        return validate(json.loads(self.path.read_text(encoding='utf-8')))

    def save(self,registry):
        validate(registry)
        self.read()  # Never silently replace an unsupported or corrupt registry.
        payload=(json.dumps(registry,ensure_ascii=False,sort_keys=True)+'\n').encode('utf-8')
        self.path.parent.mkdir(parents=True,exist_ok=True)
        fd,name=tempfile.mkstemp(prefix='.midi-inputs-',dir=self.path.parent)
        try:
            with os.fdopen(fd,'wb') as stream:
                stream.write(payload);stream.flush();os.fsync(stream.fileno())
            os.replace(name,self.path)
        finally:
            if os.path.exists(name):os.unlink(name)
