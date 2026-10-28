"""Stopped, atomic native block copies. No scheduling or runtime memory access."""
import copy
import math
import uuid
from native_capacity import layout
from switch_presets import switches, FIELDS
from conductor import decode, encode, migrate, with_mute_groups

KINDS = ('phrase', 'switch', 'movement', 'snapshot')
PHRASE_FIELDS = ('COUNT_BASE', 'MUTE_BASE', 'SOLO_BASE', 'VEL_BASE',
                 'MODE_BASE', 'LEN_BASE', 'DECAY_BASE', 'REPEAT_BASE')

def model(patch):
    return with_mute_groups(decode(patch['conductor']) if patch.get('conductor') else migrate(patch))

def phrase_source(m, slot):
    src=next((s for s in m['sources'] if s['slot']==slot),None)
    if src is None:
        src=dict(id=str(uuid.uuid4()),type='PHRASE',slot=slot,muteGroup=0);m['sources'].append(src)
    return src

def phrase_addresses(patch, slot):
    c = layout(patch)
    if type(slot) is not int or not 1 <= slot <= c['LAYERS']:
        raise ValueError('Phrase missing')
    i = slot - 1
    addresses = [c[k] + i for k in PHRASE_FIELDS]
    addresses += list(range(c['PHRASE_NAME_BASE'] + i * 16, c['PHRASE_NAME_BASE'] + (i + 1) * 16))
    for offset, native in ((112, 1), (116, 129)):
        addresses.append(c['SW_LEGACY_PAYLOAD'] + 1 + (i // 4) * 128 + offset + i % 4
                         if i < 16 else c['NATIVE_LEGACY_PAYLOAD'] + native + i)
    return addresses

def snapshots(patch):
    ext = patch.get('globalSnapshots', {'version':4, 'configuration':[4,1,0,0]+[0]*196})
    w = ext['configuration']
    if ext['version'] not in (1,2,3,4) or w[0] != ext['version']:
        raise ValueError('Unsupported snapshot layout')
    records = []; pos = 4
    for _ in range(int(w[3])):
        end = pos + 54 + 6 * int(w[pos+4])
        if end > len(w): raise ValueError('Truncated snapshot')
        records.append(list(w[pos:end])); pos = end
    tail = list(w[pos:])
    expected = (192 if w[0] >= 2 else 0) + (4 if w[0] >= 3 else 0)
    if len(tail) != expected: raise ValueError('Unsupported snapshot tail')
    return list(w[:4]), records, tail

def put_snapshots(patch, header, records, tail):
    header[3] = len(records)
    patch['globalSnapshots'] = dict(version=int(header[0]), configuration=header+sum(records, [])+tail)

def capture(patch, kind, source, allow_empty=False):
    if kind not in KINDS: raise ValueError('Unknown block type')
    c = layout(patch); mem = patch['memory']
    if patch['schema'] != 8: raise ValueError('Native patch required')
    if kind == 'phrase':
        addresses = phrase_addresses(patch, source); i = source-1
        count = int(mem[c['COUNT_BASE']+i])
        if not count and not allow_empty: raise ValueError('This phrase is empty')
        src = phrase_source(model(patch), source)
        return dict(kind=kind, source=source, values=[mem[a] for a in addresses],
                    events=list(mem[i*c['LAYER_STRIDE']:i*c['LAYER_STRIDE']+count*5]), muteGroup=src['muteGroup'], tune=src.get('tune',0))
    if kind == 'movement':
        item = next((m for m in model(patch)['movements'] if m['id'] == source), None)
        if not item: raise ValueError('Movement missing')
        return dict(kind=kind, source=source, item=copy.deepcopy(item))
    if kind == 'snapshot':
        if type(source) is not int:raise ValueError('Invalid snapshot')
        _, records, _ = snapshots(patch)
        item = next((r for r in records if r[0] == source), None)
        if not item: raise ValueError('Snapshot missing')
        return dict(kind=kind, source=source, item=item)
    if type(source) is not int:raise ValueError('Invalid switch')
    all_switches = switches(patch); sw = all_switches.get(source)
    if not sw: raise ValueError('Smart Switch missing')
    b = sw['base']; offsets = list(FIELDS)+list(range(32,112))+[120,121,122]
    header, _, tail = snapshots(patch)
    actions = [tail[j:j+4] for j in range(0,192,4) if tail[j] == source] if header[0]>=2 else []
    return dict(kind=kind, source=source, slot=sw['slot'], offsets=offsets,
                values=[mem[b+j] for j in offsets],
                conductor=copy.deepcopy(next((s for s in model(patch)['switches'] if s['switchId']==source), None)), actions=actions)

def remap_ids(value):
    # STEP/LAYER/block UUIDs are globally unique, including charge block references.
    mapping = {}
    def collect(v):
        if isinstance(v,dict):
            if 'id' in v: mapping[v['id']] = str(uuid.uuid4())
            for x in v.values(): collect(x)
        elif isinstance(v,list):
            for x in v: collect(x)
    collect(value)
    def replace(v):
        if isinstance(v,dict): return {k:replace(x) for k,x in v.items()}
        if isinstance(v,list): return [replace(x) for x in v]
        return mapping.get(v,v) if isinstance(v,str) else v
    return replace(value)

def paste(patch, clip, target=None, mode='empty'):
    if mode not in ('empty','overwrite','swap'): raise ValueError('Invalid paste mode')
    kind = clip['kind']
    if kind != 'phrase' and (target is not None or mode != 'empty'):
        raise ValueError('Paste is only allowed on an empty location')
    result = copy.deepcopy(patch); c=layout(result); mem=result['memory']; m=model(result)
    if kind == 'phrase':
        addresses=phrase_addresses(result,target); i=target-1
        occupied=bool(mem[c['COUNT_BASE']+i])
        if occupied and mode=='empty': raise ValueError('Destination occupied: choose OVERWRITE or SWAP')
        if mode=='swap':
            if target==clip['source']: raise ValueError('Choose another phrase')
            current=capture(result,'phrase',clip['source'])
            same=all(current[k]==v for k,v in clip.items() if k!='values') and all(math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-12) for a,b in zip(current['values'],clip['values']))
            if not same:
                raise ValueError('Source changed since COPY; copy it again before SWAP')
            other=capture(result,'phrase',target,allow_empty=True)
        def write(slot, data):
            idx=slot-1; base=idx*c['LAYER_STRIDE']
            mem[base:base+c['LAYER_STRIDE']]=[0]*c['LAYER_STRIDE']
            mem[base:base+len(data['events'])]=data['events']
            for a,v in zip(phrase_addresses(result,slot),data['values']):mem[a]=v
            mem[c['TRIG_BASE']+idx]=mem[c['ONCEPOS_BASE']+idx]=0
            phrase_source(m,slot)['muteGroup']=data['muteGroup']
            phrase_source(m,slot)['tune']=data.get('tune',0)
        write(target,clip)
        if mode=='swap':
            write(clip['source'],other)
        result['conductor']=encode(m)
        # Phrase identities, MIDI triggers, and external references stay in their slots.
        return result,target
    if kind=='movement':
        if len(m['movements'])>=512: raise ValueError('Movement capacity reached')
        item=copy.deepcopy(clip['item']);item['id']=str(uuid.uuid4());m['movements'].append(item)
        result['conductor']=encode(m);return result,item['id']
    if kind=='snapshot':
        header,records,tail=snapshots(result)
        if len(records)>=16: raise ValueError('Snapshot capacity reached')
        ident=max(int(header[1]),max((int(r[0])+1 for r in records),default=1))
        if ident>16777215: raise ValueError('Snapshot identity capacity reached')
        item=list(clip['item']);item[0]=ident;records.append(item);header[1]=ident+1
        put_snapshots(result,header,records,tail);return result,ident
    items=switches(result);used={s['slot'] for s in items.values()}
    slot=next((s for s in range(c['SW_COUNT']) if s not in used),None)
    if slot is None: raise ValueError('Smart Switch capacity reached')
    ident=max(int(mem[c['DS_LEGACY_PAYLOAD']+1]),max(items,default=0)+1)
    if ident>16777215: raise ValueError('Switch identity capacity reached')
    b=c['SW_LEGACY_PAYLOAD']+1+slot*128 if slot<4 else c['DS_LEGACY_PAYLOAD']+2+(slot-4)*128
    for offset,v in zip(clip['offsets'],clip['values']):mem[b+offset]=v
    mem[b+2]=0 # A duplicate must not share the original physical pedal's input.
    mem[b+20]=1;mem[b+21]=ident;mem[c['DS_LEGACY_PAYLOAD']+1]=ident+1
    for action,target_offset in ((14,17),(15,18),(16,19),(121,122)):
        if mem[b+action] in (3,5) and mem[b+target_offset]==clip['slot']:mem[b+target_offset]=slot
    if clip['conductor']:
        owner=remap_ids(clip['conductor']);owner['switchId']=ident
        for step in owner['steps']:
            for layer in step['layers']:
                block=layer['block']
                if block and block.get('target')==dict(type='SWITCH',switchId=clip['source']):block['target']['switchId']=ident
        m['switches'].append(owner)
    result['conductor']=encode(m)
    if clip['actions']:
        header,records,tail=snapshots(result)
        if header[0]<2:raise ValueError('Snapshot action version unsupported')
        for action in clip['actions']:
            free=next((j for j in range(0,192,4) if not tail[j]),None)
            if free is None:raise ValueError('Snapshot switch action capacity reached')
            tail[free:free+4]=[ident]+action[1:]
        put_snapshots(result,header,records,tail)
    return result,ident
