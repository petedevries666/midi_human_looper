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
# Existing control channel byte ceiling, not a musical STEPS/LAYERS limit (Q3).
MAX_BYTES = 16000000
OPTIONS = {
    'playMode': ('LOOP', 'ONCE', 'HOLD'),
    'trigger': ('PRESS', 'HOLD'),
    'instancePolicy': ('JOIN_EXISTING', 'RESTART', 'NEW_INSTANCE'),
    'join': ('TRIGGER', 'JOIN_NOW', 'JOIN_AT_LOOP_START'),
    'referenceTime': ('CYCLE', 'ELAPSED'),
    'entry': ('TRIGGER', 'REVEAL'),
    'release': ('LATCH', 'GATE'),
    'movementPlayMode': ('ONE_SHOT', 'GATED'),
    'retrigger': ('SOFT_RESTART', 'DIRECT'),
}
PHRASE_OPTIONS = {'playMode', 'trigger', 'instancePolicy', 'join', 'referenceTime', 'entry', 'release', 'phrase_time_decay', 'phrase_velocity_decay', 'phrase_base_velocity'}
MOVEMENT_OPTIONS = {'trigger', 'join', 'referenceTime', 'movementPlayMode', 'retrigger', 'destination'}


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


def validate(data):
    if not isinstance(data, dict):
        raise ValueError('CONDUCTOR document required')
    fields(data, ('version', 'sources', 'switches', 'movements', 'ccRate') if data.get('version') == DOCUMENT_VERSION else ('version', 'sources', 'switches'))
    if type(data['version']) is not int or data['version'] not in (VERSION, DOCUMENT_VERSION):
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
        fields(source, ('id', 'type', 'slot'))
        unique(source['id'])
        # Only the existing PHRASE pool has a production storage binding today.
        # MOVEMENT refs are valid but unresolved until its source library exists.
        if source['type'] != 'PHRASE':
            raise ValueError('CONDUCTOR unsupported source pool binding')
        integer(source['slot'], 1, 16)
        if source['slot'] in slots:
            raise ValueError('CONDUCTOR aliased PHRASE slot')
        slots.add(source['slot']); sources[source['id']] = source
    if data['version'] == DOCUMENT_VERSION:
        if type(data['ccRate']) is not int or data['ccRate'] not in (10, 25, 50, 100):
            raise ValueError('MOVEMENT invalid global CC rate')
        if not isinstance(data['movements'], list):
            raise ValueError('MOVEMENT library required')
        for movement in data['movements']:
            fields(movement, ('id', 'name', 'target', 'points', 'duration', 'interpolation', 'retrigger', 'glideSeconds'))
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
                if not isinstance(point, list) or len(point) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in point) or point[0] <= previous:
                    raise ValueError('MOVEMENT ordered normalized curve points required')
                previous = point[0]
            if points[0][0] != 0 or points[-1][0] != 1:
                raise ValueError('MOVEMENT endpoints must be 0 and 1')
            sources[movement['id']] = dict(type='MOVEMENT')
    switches = set()
    for switch in data['switches']:
        fields(switch, ('switchId', 'traversal', 'transition', 'gesture', 'steps'))
        integer(switch['switchId'], 1, 16777215)
        if switch['switchId'] in switches:
            raise ValueError('CONDUCTOR duplicate Smart Switch owner')
        switches.add(switch['switchId'])
        if switch['traversal'] not in ('SEQUENTIAL', 'BACKWARD', 'PING_PONG', 'RANDOM', 'SHUFFLE_BAG') or switch['transition'] not in ('IMMEDIATE', 'END_OF_PHRASE') or switch['gesture'] not in ('INSTANT', 'EXCLUSIVE'):
            raise ValueError('CONDUCTOR invalid switch options')
        if not isinstance(switch['steps'], list) or not switch['steps']:
            raise ValueError('CONDUCTOR at least one STEP required')
        for step in switch['steps']:
            fields(step, ('id', 'transition', 'layers'))
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
                    if index == 0 or block['action'] not in ('STOP', 'PAUSE', 'RESUME', 'RESET_CURSOR', 'RESET_SHUFFLE_BAG', 'STOP_RESET') or block['trigger'] not in ('PRESS', 'HOLD'):
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
    return dict(version=VERSION, sources=[dict(id=str(uuid.uuid4()), type='PHRASE', slot=i) for i in range(1, 17)], switches=[])


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
