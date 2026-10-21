"""New switches use one empty Conductor step; existing switches stay untouched."""
import copy
import uuid
from native_capacity import layout
from switch_presets import switches
from block_edit import model
from conductor import encode


def add_switch(patch):
    if patch.get('schema') != 8:
        raise ValueError('Native schema 8 required; original preserved')
    result = copy.deepcopy(patch)
    c = layout(result)
    mem = result['memory']
    existing = switches(result)
    used = {s['slot'] for s in existing.values()}
    slot = next((i for i in range(c['SW_COUNT']) if i not in used), None)
    if slot is None:
        raise ValueError('Smart Switch capacity reached')
    identity = max(1, int(mem[c['DS_LEGACY_PAYLOAD']+1]), max(existing, default=0)+1)
    if identity > 16777215:
        raise ValueError('Switch identity capacity reached')
    base = c['SW_LEGACY_PAYLOAD']+1+slot*128 if slot < 4 else c['DS_LEGACY_PAYLOAD']+2+(slot-4)*128
    for offset in range(128):
        if slot < 4 and (24 <= offset < 32 or 112 <= offset < 120):
            continue  # Shared phrase/controller settings belong to other objects.
        mem[base+offset] = 0
    for offset, value in {0:1, 4:min(127,60+slot), 7:300, 8:800, 12:127,
                          14:1, 17:slot, 18:slot, 19:slot, 20:1, 21:identity}.items():
        mem[base+offset] = value
    mem[c['DS_LEGACY_PAYLOAD']+1] = identity+1
    document = model(result)
    document['switches'].append(dict(switchId=identity, traversal='SEQUENTIAL',
        transition='IMMEDIATE', gesture='INSTANT', steps=[dict(id=str(uuid.uuid4()),
            transition='INHERIT', layers=[dict(id=str(uuid.uuid4()), block=None)])]))
    result['conductor'] = encode(document)
    return result, identity
