"""Versioned terminal ECHOCITY carrier; no callback, MIDI or browser dependency."""
import math

FIELDS=('instrumentId','enabled','timeUnit','interval','firstOffset','wet','decay','gate','gateDecay','repeats','pitchStep','pingPong','otherChannel','dry')
DEFAULTS=(0,1,0,250,1,.5,.7,1,1,4,0,0,1,1)
ROUTE_FIELDS=('routing','channelMask','noRepeat','patternLength','pattern')

def decode(extension):
    if not isinstance(extension,dict) or set(extension)!={'version','configuration'} or type(extension['version']) is not int or extension['version'] not in (1,2,3,4,5):
        raise ValueError('Unsupported ECHOCITY version; original preserved')
    wire=extension['configuration']
    width={1:13,2:14,3:15,4:35,5:36}[extension['version']]
    if not isinstance(wire,list) or len(wire)<2 or type(wire[0]) is not int or wire[0]!=extension['version'] or type(wire[1]) is not int or not 0<=wire[1]<=8 or len(wire)!=2+width*wire[1]:
        raise ValueError('Invalid ECHOCITY configuration')
    units=[];ids=set()
    for at in range(2,len(wire),width):
        values=wire[at:at+width]
        if any(type(v) not in (int,float) or not math.isfinite(v) for v in values):raise ValueError('Invalid ECHOCITY value')
        for index in (0,1,2,9,10,11,12):
            if type(values[index]) is not int:raise ValueError('ECHOCITY discrete value must be an integer')
        if width==13:values=values+[1-values[5]]
        traversal=values[14] if width>=15 else 0
        if type(traversal) is not int or not 0<=traversal<=3:raise ValueError('ECHOCITY traversal outside its range')
        route={}
        if width>=35:
            routing,mask,no_repeat,length=values[15:19];pattern=values[19:35]
            if any(type(v) is not int for v in values[15:]) or not 0<=routing<=3 or not 0<=mask<=65535 or no_repeat not in (0,1) or not 0<=length<=16 or any(not 0<=v<=15 for v in pattern):raise ValueError('Invalid ECHOCITY routing')
            if routing in (1,2) and not mask or routing==3 and not length:raise ValueError('Choose ECHOCITY destinations')
            route=dict(zip(ROUTE_FIELDS,(routing,mask,no_repeat,length,pattern)))
        if width>=36:
            destination=values[35]
            if type(destination) is not int or destination not in (0,1,2):raise ValueError('Invalid ECHOCITY destination transforms')
            route['destinationTransforms']=destination
        values=values[:14]
        identifier,enabled,unit,interval,first,wet,decay,gate,gate_decay,repeats,pitch,ping,ch,dry=values
        if not 1<=identifier<=16777215 or identifier in ids or enabled not in (0,1) or unit not in (0,1) or not 0<interval<=(60000 if unit==0 else 64) or not 0<=first<=16 or not 0<=wet<=1 or not 0<=decay<=1 or not 0<=gate<=4 or not 0<=gate_decay<=1 or not 1<=repeats<=32 or not -48<=pitch<=48 or ping not in (0,1) or not 0<=ch<=15:
            raise ValueError('ECHOCITY value outside its range')
        if not 0<=dry<=1:raise ValueError('ECHOCITY DRY outside its range')
        ids.add(identifier);units.append({**dict(zip(FIELDS,values)),'traversal':traversal,**route})
    return units

def encode(units):
    if not isinstance(units,list):raise ValueError('ECHOCITY units required')
    version=5 if any(unit.get('destinationTransforms',0) for unit in units if isinstance(unit,dict)) else 4 if any(set(ROUTE_FIELDS)&set(unit) for unit in units if isinstance(unit,dict)) else 3 if any(unit.get('traversal',0) for unit in units if isinstance(unit,dict)) else 2
    wire=[version,len(units)]
    for unit in units:
        if not isinstance(unit,dict) or set(FIELDS)-set(unit) or set(unit)-set(FIELDS)-{'traversal','destinationTransforms'}-set(ROUTE_FIELDS):raise ValueError('Complete ECHOCITY unit required')
        destination=unit.get('destinationTransforms',0)
        if type(destination) is not int or destination not in (0,1,2):raise ValueError('Invalid ECHOCITY destination transforms')
        wire.extend(unit[key] for key in FIELDS)
        if version>=3:wire.append(unit.get('traversal',0))
        if version>=4:
            wire.extend(unit.get(key,default) for key,default in zip(ROUTE_FIELDS[:4],(0,0,1,0)))
            pattern=unit.get('pattern',[0]*16)
            if not isinstance(pattern,list) or len(pattern)!=16:raise ValueError('ECHOCITY pattern needs 16 entries')
            wire.extend(pattern)
        if version>=5:wire.append(destination)
    result={'version':version,'configuration':wire};decode(result);return result
