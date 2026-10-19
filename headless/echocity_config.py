"""Versioned terminal ECHOCITY carrier; no callback, MIDI or browser dependency."""
import math

FIELDS=('instrumentId','enabled','timeUnit','interval','firstOffset','wet','decay','gate','gateDecay','repeats','pitchStep','pingPong','otherChannel')
DEFAULTS=(0,1,0,250,1,.5,.7,1,1,4,0,0,1)

def decode(extension):
    if not isinstance(extension,dict) or set(extension)!={'version','configuration'} or type(extension['version']) is not int or extension['version']!=1:
        raise ValueError('Unsupported ECHOCITY version; original preserved')
    wire=extension['configuration']
    if not isinstance(wire,list) or len(wire)<2 or type(wire[0]) is not int or wire[0]!=1 or type(wire[1]) is not int or not 0<=wire[1]<=8 or len(wire)!=2+13*wire[1]:
        raise ValueError('Invalid ECHOCITY configuration')
    units=[];ids=set()
    for at in range(2,len(wire),13):
        values=wire[at:at+13]
        if any(type(v) not in (int,float) or not math.isfinite(v) for v in values):raise ValueError('Invalid ECHOCITY value')
        for index in (0,1,2,9,10,11,12):
            if type(values[index]) is not int:raise ValueError('ECHOCITY discrete value must be an integer')
        identifier,enabled,unit,interval,first,wet,decay,gate,gate_decay,repeats,pitch,ping,ch=values
        if not 1<=identifier<=16777215 or identifier in ids or enabled not in (0,1) or unit not in (0,1) or not 0<interval<=(60000 if unit==0 else 64) or not 0<=first<=16 or not 0<=wet<=1 or not 0<=decay<=1 or not 0<=gate<=4 or not 0<=gate_decay<=1 or not 1<=repeats<=32 or not -48<=pitch<=48 or ping not in (0,1) or not 0<=ch<=15:
            raise ValueError('ECHOCITY value outside its range')
        ids.add(identifier);units.append(dict(zip(FIELDS,values)))
    return units

def encode(units):
    if not isinstance(units,list):raise ValueError('ECHOCITY units required')
    wire=[1,len(units)]
    for unit in units:
        if not isinstance(unit,dict) or set(unit)!=set(FIELDS):raise ValueError('Complete ECHOCITY unit required')
        wire.extend(unit[key] for key in FIELDS)
    result={'version':1,'configuration':wire};decode(result);return result
