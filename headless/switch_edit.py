"""Stopped native patch edits, preserving unrelated source allocations."""
import copy
from conductor import decode,encode
from switch_presets import switches

def remove_switch(patch,ident):
    result=copy.deepcopy(patch);items=switches(result)
    if type(ident) is not int or ident not in items:raise ValueError('Smart Switch missing')
    victim=items[ident];base=victim['base'];slot=victim['slot'];mem=result['memory']
    # Legacy switch slots also contain phrase/expression settings. Do not wipe
    # their whole allocation or renumber any surviving persistent identity.
    for offset in (0,2,11,20):mem[base+offset]=0
    for other in items.values():
        b=other['base']
        for action,target in ((14,17),(15,18),(16,19),(121,122)):
            if mem[b+action] in (3,5) and mem[b+target]==slot:mem[b+action]=mem[b+target]=0
    if result.get('conductor'):
        model=decode(result['conductor']);model['switches']=[s for s in model['switches'] if s['switchId']!=ident];result['conductor']=encode(model)
    wire=result.get('globalSnapshots',{}).get('configuration',[])
    if wire and wire[0]>=2:
        index=4
        for _ in range(int(wire[3])):index+=54+6*int(wire[index+4])
        if len(wire)<index+192:raise ValueError('Unknown snapshot layout preserved')
        for i in range(index,index+192,4):
            if wire[i]==ident:wire[i:i+4]=[0,0,0,0]
    return result
