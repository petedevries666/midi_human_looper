"""Versioned, configuration-only CONDUCTOR carrier. Never called by the MIDI callback.

Schema 7 source MIDI remains authoritative; identities bind to slots explicitly.
Unknown fields/versions are rejected, not discarded. No runtime cursor is stored.
"""
import copy
import json
import math
import uuid

VERSION = 1
DOCUMENT_VERSION = 2
GROUP_VERSION = 3
# Existing control channel byte ceiling, not a musical STEPS/LAYERS limit (Q3).
MAX_BYTES = 16000000
OPTIONS = {
    'playMode': ('LOOP', 'ONCE', 'HOLD'),
    'trigger': ('PRESS', 'HOLD', 'LONG_HOLD', 'RELEASE', 'SUPERCHARGE_RELEASE'),
    'instancePolicy': ('JOIN_EXISTING', 'RESTART', 'NEW_INSTANCE'),
    'join': ('TRIGGER', 'JOIN_NOW', 'JOIN_AT_LOOP_START'),
    'referenceTime': ('CYCLE', 'ELAPSED'),
    'entry': ('TRIGGER', 'REVEAL'),
    'release': ('LATCH', 'GATE'),
    'movementPlayMode': ('ONE_SHOT', 'GATED'),
    'movementCycle': ('ONCE', 'LOOP', 'PING_PONG'),
    'retrigger': ('SOFT_RESTART', 'DIRECT'),
}
PHRASE_OPTIONS = {'playMode', 'trigger', 'instancePolicy', 'join', 'referenceTime', 'entry', 'release', 'phrase_time_decay', 'phrase_velocity_decay', 'phrase_base_velocity', 'phrase_tune', 'phrase_rate', 'revealCC', 'revealFadeSeconds'}
MOVEMENT_OPTIONS = {'trigger', 'join', 'referenceTime', 'movementPlayMode', 'retrigger', 'destination', 'releaseSeconds', 'restValue', 'movementDuration', 'movementCycle'}


def fields(value, required):
    if not isinstance(value, dict) or set(value) != set(required):
        raise ValueError('CONDUCTOR unknown or missing fields')


def identity(value):
    if not isinstance(value, str):
        raise ValueError('CONDUCTOR stable UUID required')
    try:
        if str(uuid.UUID(value)) != value:
            raise ValueError()
    except (ValueError, AttributeError):
        raise ValueError('CONDUCTOR canonical stable UUID required') from None
    return value


def integer(value, lo, hi):
    if type(value) is not int or not lo <= value <= hi:
        raise ValueError('CONDUCTOR invalid integer')


def playback_rate(value):
    if type(value) not in (int,float) or not math.isfinite(value) or not .1<=value<=16:
        raise ValueError('RATE must be between 0.1 and 16')


def destination(value):
    if not isinstance(value, dict):
        raise ValueError('CONDUCTOR destination required')
    if value.get('type') == 'CC':
        fields(value, ('type', 'channel', 'number'))
        integer(value['channel'], 1, 16); integer(value['number'], 0, 127)
    elif value.get('type') == 'PARAMETER':
        fields(value, ('type', 'instrumentId', 'moduleId', 'kind'))
        integer(value['instrumentId'], 1, 16777215)
        integer(value['moduleId'], 0, 16777215)
        from registry import REGISTRY
        if type(value['kind']) is not int or not any(p['engineKind']==value['kind'] for p in REGISTRY.parameters.values()):
            raise ValueError('CONDUCTOR unknown parameter descriptor')
    else:
        raise ValueError('CONDUCTOR unknown destination')


def charge_range(parameter):
    if parameter=='movementDuration':return .001,86400.
    if parameter=='movementAmplitude':return 0.,1.
    from registry import REGISTRY
    if parameter not in ('phrase_time_decay','phrase_velocity_decay','phrase_base_velocity'):raise ValueError('Unsupported charge parameter')
    d=REGISTRY.parameters[parameter];return d['min'],d['max']

def validate_charge(step,defaults):
    charge=step['supercharge'];fields(charge,('bindings',)+tuple(k for k in ('thresholdMs','fullMs') if k in charge))
    threshold=charge.get('thresholdMs',defaults['thresholdMs']);full=charge.get('fullMs',defaults['fullMs'])
    integer(threshold,0,30000);integer(full,1,120000)
    if full<threshold:raise ValueError('Full charge must follow its threshold')
    if not isinstance(charge['bindings'],list):raise ValueError('Charge bindings required')
    blocks={l['block']['id']:l['block'] for l in step['layers'] if l.get('block') and l['block'].get('type') in ('PHRASE','MOVEMENT')};seen=set()
    for b in charge['bindings']:
        if 'target' in b:
            fields(b,('target','parameter','from','to','factor'));destination(b['target'])
            if b['target']['type']!='PARAMETER' or b['target']['kind']==16 or b['parameter']!='parameter':raise ValueError('Unsupported charge target')
            from registry import REGISTRY
            descriptor=next((d for d in REGISTRY.parameters.values() if d.get('engineKind')==b['target']['kind']),None)
            if descriptor is None:raise ValueError('Unknown charge target')
            key=('target',tuple(sorted(b['target'].items())))
            if key in seen:raise ValueError('Duplicate charge destination')
            seen.add(key)
            for field in ('from','to','factor'):
                v=b[field];lo,hi=(0,16) if field=='factor' else (descriptor['min'],descriptor['max'])
                if type(v) not in (int,float) or not math.isfinite(v) or not lo<=v<=hi:raise ValueError('Charge value outside parameter range')
            continue
        fields(b,('blockId','parameter','from','to','factor'));identity(b['blockId'])
        block=blocks.get(b['blockId']);key=(b['blockId'],b['parameter'])
        if not block or key in seen:raise ValueError('Missing or duplicate charge destination')
        seen.add(key);lo,hi=charge_range(b['parameter'])
        if (block['type']=='MOVEMENT') != b['parameter'].startswith('movement'):raise ValueError('Charge parameter does not belong to this block')
        for field in ('from','to','factor'):
            v=b[field];a,z=(0,16) if field=='factor' else (lo,hi)
            if type(v) not in (int,float) or not math.isfinite(v) or not a<=v<=z:raise ValueError('Charge value outside parameter range')


def validate(data):
    if not isinstance(data, dict):
        raise ValueError('CONDUCTOR document required')
    fields(data, (('version', 'sources', 'switches', 'movements', 'ccRate') if data.get('version') in (DOCUMENT_VERSION, GROUP_VERSION) else ('version', 'sources', 'switches')) + (('supercharge',) if 'supercharge' in data else ()))
    defaults=data.get('supercharge',dict(thresholdMs=600,fullMs=2000));fields(defaults,('thresholdMs','fullMs'));integer(defaults['thresholdMs'],0,30000);integer(defaults['fullMs'],1,120000)
    if defaults['fullMs']<defaults['thresholdMs']:raise ValueError('Full patch charge must follow its threshold')
    if type(data['version']) is not int or data['version'] not in (VERSION, DOCUMENT_VERSION, GROUP_VERSION):
        raise ValueError('CONDUCTOR unsupported version')
    used = set()
    def unique(value):
        identity(value)
        if value in used:
            raise ValueError('CONDUCTOR duplicate stable identity')
        used.add(value)
    if not isinstance(data['sources'], list) or not isinstance(data['switches'], list):
        raise ValueError('CONDUCTOR arrays required')
    slots = set()
    sources = {}
    for source in data['sources']:
        fields(source, (('id', 'type', 'slot', 'muteGroup') if data['version']==GROUP_VERSION else ('id', 'type', 'slot')) + tuple(k for k in ('tune','rate') if k in source))
        if 'tune' in source: integer(source['tune'], -24, 24)
        if 'rate' in source: playback_rate(source['rate'])
        if data['version']==GROUP_VERSION: integer(source['muteGroup'], 0, 16777215)
        unique(source['id'])
        # Only the existing PHRASE pool has a production storage binding today.
        # MOVEMENT refs are valid but unresolved until its source library exists.
        if source['type'] != 'PHRASE':
            raise ValueError('CONDUCTOR unsupported source pool binding')
        integer(source['slot'], 1, 128)
        if source['slot'] in slots:
            raise ValueError('CONDUCTOR aliased PHRASE slot')
        slots.add(source['slot']); sources[source['id']] = source
    if data['version'] in (DOCUMENT_VERSION, GROUP_VERSION):
        if type(data['ccRate']) is not int or data['ccRate'] not in (10, 25, 50, 100):
            raise ValueError('MOVEMENT invalid global CC rate')
        if not isinstance(data['movements'], list):
            raise ValueError('MOVEMENT library required')
        for movement in data['movements']:
            extended=any(k in movement for k in ('playMode','releaseSeconds','restValue'))
            fields(movement, ('id', 'name', 'target', 'points', 'duration', 'interpolation', 'retrigger', 'glideSeconds') + (('playMode','releaseSeconds','restValue') if extended else ()) + (('cycleMode',) if 'cycleMode' in movement else ()))
            if movement.get('cycleMode','ONCE') not in OPTIONS['movementCycle']:raise ValueError('MOVEMENT invalid cycle mode')
            if extended:
                if movement['playMode'] not in OPTIONS['movementPlayMode']:raise ValueError('MOVEMENT invalid play mode')
                for k,hi in [('releaseSeconds',60),('restValue',1)]:
                    v=movement[k]
                    if type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=hi:raise ValueError('MOVEMENT invalid release')
            unique(movement['id'])
            name = movement['name']
            if not isinstance(name, str) or not name or any(not 32 <= ord(c) <= 126 or c in '\\"' for c in name):
                raise ValueError('MOVEMENT printable unescaped ASCII name required')
            destination(movement['target'])
            for key in ('duration', 'glideSeconds'):
                v = movement[key]
                if type(v) not in (int, float) or not math.isfinite(v) or v <= 0:
                    raise ValueError('MOVEMENT positive finite duration required')
            if movement['glideSeconds'] > 60:
                raise ValueError('MOVEMENT GLIDE exceeds Controller Engine range')
            if movement['interpolation'] not in ('LINEAR', 'HOLD') or movement['retrigger'] not in OPTIONS['retrigger']:
                raise ValueError('MOVEMENT unsupported interpolation/retrigger')
            points = movement['points']
            if not isinstance(points, list) or len(points) < 2:
                raise ValueError('MOVEMENT at least two curve points required')
            previous = -1
            for point in points:
                if not isinstance(point, list) or len(point) not in (2, 3) or any(type(v) not in (int, float) or not math.isfinite(v) for v in point) or any(not 0 <= v <= 1 for v in point[:2]) or (len(point) == 3 and abs(point[2]) > .98) or point[0] <= previous:
                    raise ValueError('MOVEMENT ordered normalized curve points required')
                previous = point[0]
            if points[0][0] != 0 or points[-1][0] != 1:
                raise ValueError('MOVEMENT endpoints must be 0 and 1')
            sources[movement['id']] = dict(type='MOVEMENT')
    switches = set()
    for switch in data['switches']:
        fields(switch, ('switchId', 'traversal', 'transition', 'gesture', 'steps') + (('advance',) if 'advance' in switch else ()))
        if switch.get('advance','PRESS') not in ('PRESS','RELEASE'):raise ValueError('CONDUCTOR invalid advance gesture')
        integer(switch['switchId'], 1, 16777215)
        if switch['switchId'] in switches:
            raise ValueError('CONDUCTOR duplicate Smart Switch owner')
        switches.add(switch['switchId'])
        if switch['traversal'] not in ('SEQUENTIAL', 'BACKWARD', 'PING_PONG', 'RANDOM', 'SHUFFLE_BAG') or switch['transition'] not in ('IMMEDIATE', 'END_OF_PHRASE') or switch['gesture'] not in ('INSTANT', 'EXCLUSIVE'):
            raise ValueError('CONDUCTOR invalid switch options')
        if not isinstance(switch['steps'], list) or not switch['steps']:
            raise ValueError('CONDUCTOR at least one STEP required')
        for step in switch['steps']:
            fields(step, ('id', 'transition', 'layers') + tuple(k for k in ('supercharge','repeat') if k in step))
            if 'repeat' in step: integer(step['repeat'],1,999)
            if 'supercharge' in step:validate_charge(step,defaults)
            unique(step['id'])
            if step['transition'] not in ('INHERIT', 'IMMEDIATE', 'END_OF_PHRASE') or not isinstance(step['layers'], list) or not step['layers']:
                raise ValueError('CONDUCTOR invalid STEP')
            for index, layer in enumerate(step['layers']):
                fields(layer, ('id', 'block')); unique(layer['id'])
                block = layer['block']
                if block is None:
                    continue
                if isinstance(block,dict) and block.get('type') == 'ACTION':
                    fields(block, ('id', 'type', 'action', 'target', 'trigger'))
                    unique(block['id'])
                    if index == 0 or block['action'] not in ('STOP', 'PAUSE', 'RESUME', 'RESET_CURSOR', 'RESET_SHUFFLE_BAG', 'STOP_RESET', 'PANIC') or block['trigger'] not in ('PRESS', 'HOLD', 'LONG_HOLD', 'RELEASE', 'SUPERCHARGE_RELEASE'):
                        raise ValueError('CONDUCTOR invalid action or LAYER')
                    target = block['target']
                    if not isinstance(target,dict): raise ValueError('CONDUCTOR action target required')
                    if target.get('type') == 'PHRASE':
                        fields(target, ('type', 'sourceId')); identity(target['sourceId'])
                    elif target.get('type') == 'MUTE_GROUP':
                        fields(target, ('type', 'id')); integer(target['id'], 1, 16777215)
                    elif target.get('type') == 'ALL_PHRASES':
                        fields(target, ('type',))
                    elif target.get('type') == 'SWITCH':
                        fields(target, ('type', 'switchId')); integer(target['switchId'], 1, 16777215)
                    else: raise ValueError('CONDUCTOR invalid action target')
                    if (block['action'] in ('RESET_CURSOR','RESET_SHUFFLE_BAG') and target['type'] != 'SWITCH') or (block['action'] in ('STOP','PAUSE','RESUME') and target['type'] == 'SWITCH'):
                        raise ValueError('CONDUCTOR incompatible action target')
                    if block['action']=='PANIC' and target['type']!='ALL_PHRASES':raise ValueError('PANIC requires ALL_PHRASES')
                    continue
                fields(block, ('id', 'type', 'sourceId', 'overrides'))
                unique(block['id'])
                if block['type'] not in ('PHRASE', 'MOVEMENT') or (index == 0 and block['type'] != 'PHRASE'):
                    raise ValueError('CONDUCTOR LAYER 01 must be PHRASE MASTER or EMPTY')
                identity(block['sourceId'])
                if block['sourceId'] in sources and sources[block['sourceId']]['type'] != block['type']:
                    raise ValueError('CONDUCTOR source type mismatch')
                permitted = PHRASE_OPTIONS if block['type'] == 'PHRASE' else MOVEMENT_OPTIONS
                if not isinstance(block['overrides'], dict) or set(block['overrides']) - permitted:
                    raise ValueError('CONDUCTOR unsupported local override (MUTE GROUP is source-only)')
                for name, local in block['overrides'].items():
                    if not isinstance(local, dict) or local.get('mode') not in ('INHERIT', 'OVERRIDE'):
                        raise ValueError('CONDUCTOR override mode required')
                    fields(local, ('mode',) if local['mode'] == 'INHERIT' else ('mode', 'value'))
                    if local['mode'] == 'OVERRIDE':
                        if name == 'destination':
                            destination(local['value'])
                        elif name in ('revealCC','revealFadeSeconds'):
                            v=local['value']
                            if name=='revealCC':
                                integer(v,0,119)
                                if v==64:raise ValueError('Sustain is reserved')
                            elif type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=60:raise ValueError('Invalid REVEAL fade')
                        elif name in ('releaseSeconds','restValue','movementDuration'):
                            v=local['value']
                            if type(v) not in (int,float) or not math.isfinite(v) or not (0<v<=86400 if name=='movementDuration' else 0<=v<=(60 if name=='releaseSeconds' else 1)):raise ValueError('MOVEMENT invalid release override')
                        elif name == 'phrase_rate':
                            playback_rate(local['value'])
                        elif name == 'phrase_tune':
                            integer(local['value'], -24, 24)
                        elif name.startswith('phrase_'):
                            from registry import REGISTRY
                            descriptor=REGISTRY.parameters[name];v=local['value']
                            if type(v) not in (int,float) or not math.isfinite(v) or not descriptor['min']<=v<=descriptor['max']:
                                raise ValueError('CONDUCTOR invalid parameter override')
                        elif local['value'] not in OPTIONS[name]:
                            raise ValueError('CONDUCTOR invalid local option')
    encoded = json.dumps(data, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')
    if len(encoded) * 4 > MAX_BYTES:
        raise ValueError('CONDUCTOR exceeds existing control transport capacity')
    return data


def encode(data):
    validate(data)
    return {'version': VERSION, 'configuration': list(json.dumps(data, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii'))}


def decode(extension):
    fields(extension, ('version', 'configuration'))
    wire = extension['configuration']
    if type(extension['version']) is not int or extension['version'] != VERSION or not isinstance(wire, list) or len(wire) * 4 > MAX_BYTES or any(type(c) is not int or not 32 <= c <= 126 for c in wire):
        raise ValueError('CONDUCTOR invalid carrier')
    try:
        def pairs(items):
            result = {}
            for key, value in items:
                if key in result: raise ValueError('CONDUCTOR duplicate JSON field')
                result[key] = value
            return result
        data = json.loads(bytes(wire), object_pairs_hook=pairs)
    except (ValueError, TypeError, UnicodeError):
        raise ValueError('CONDUCTOR malformed document') from None
    return validate(data)


def migrate(patch):
    """Explicit adoption: never translate legacy sequence indices into STEPS.

    Legacy slots are fixed existing sources; UUIDs are allocated once at adoption
    and then stored. No implicit re-binding occurs on subsequent LOAD.
    """
    if 'conductor' in patch:
        return copy.deepcopy(decode(patch['conductor']))
    return dict(version=VERSION, sources=[dict(id=str(uuid.uuid4()), type='PHRASE', slot=i) for i in range(1, 129 if patch.get('schema')==8 else 17)], switches=[])


def resolve(data, existing_switches=None):
    validate(data)
    sources = {s['id']: s for s in data['sources']}
    sources.update({s['id']: s for s in data.get('movements', [])})
    missing = []
    for switch in data['switches']:
        if existing_switches is not None and switch['switchId'] not in existing_switches:
            missing.append(dict(switchId=switch['switchId'], reason='missing_switch'))
        for step in switch['steps']:
            for layer in step['layers']:
                block = layer['block']
                if block and block['type'] == 'ACTION' and block['target'].get('type') == 'PHRASE' and block['target']['sourceId'] not in sources:
                    missing.append(dict(blockId=block['id'], sourceId=block['target']['sourceId'], reason='missing_source'))
                if block and block['type'] != 'ACTION' and block['sourceId'] not in sources:
                    missing.append(dict(blockId=block['id'], sourceId=block['sourceId'], reason='missing_source'))
    return missing


def with_mute_groups(data):
    """Explicit versioned adoption; legacy documents are never mutated in place."""
    validate(data)
    result=copy.deepcopy(data)
    result.update(version=GROUP_VERSION)
    result.setdefault('movements',[]); result.setdefault('ccRate',25)
    for source in result['sources']: source.setdefault('muteGroup',0)
    return validate(result)


def mute_group_warnings(data):
    validate(data)
    sources={s['id']:s for s in data['sources']}
    result=[]
    for switch in data['switches']:
        for step in switch['steps']:
            groups={}
            for layer in step['layers']:
                block=layer['block']
                source=sources.get(block.get('sourceId')) if block and block['type']=='PHRASE' else None
                if source and source.get('muteGroup',0): groups.setdefault(source['muteGroup'],set()).add(source['slot'])
            for group,slots in sorted(groups.items()):
                if len(slots)>1: result.append(dict(switchId=switch['switchId'],stepId=step['id'],muteGroup=group,winnerPhraseId=min(slots),phraseIds=sorted(slots)))
    return result
