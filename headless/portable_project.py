"""Immutable studio/live carrier. File work belongs to control workers, never JACK.

Version 1 deliberately carries the existing schema-7 patch rather than inventing
another module model. Only phrase source timing is canonicalized to seconds.
Unknown configurations are rejected without changing their source file.
"""
import copy
import hashlib
import json
import math
import uuid

FORMAT = 'MBMF_PORTABLE_PROJECT'
SIZE = 171649
LAYERS, STRIDE, COUNT = 16, 10240, 163840
LENGTH, TRIGGER, POSITION, REPEAT = 163952, 163920, 163936, 163984
MAX_BYTES = 16000000


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def rate(value):
    if type(value) not in (int, float) or not math.isfinite(value) or not 8000 <= value <= 384000:
        raise ValueError('Invalid adapter sample rate')
    return value


def validate_patch(patch):
    # Import lazily: server imports this module for bridge endpoints.
    from server import validate_patch_extensions
    validate_patch_extensions(patch)
    if patch['schema'] != 7 or patch.get('work_mem_size') != SIZE:
        raise ValueError('Portable v1 requires migrated schema-7 patch; load older patches in the engine first')
    memory, globals_ = patch.get('memory'), patch.get('globals')
    if not isinstance(memory, list) or len(memory) != SIZE or not isinstance(globals_, list) or len(globals_) != 9:
        raise ValueError('Invalid patch dimensions')
    if any(type(x) not in (int, float) or not math.isfinite(x) for x in memory + globals_):
        raise ValueError('Invalid numeric patch data')
    if globals_[0] < 0:
        raise ValueError('Invalid loop length')
    for p in range(LAYERS):
        n = memory[COUNT+p]
        if int(n) != n or not 0 <= n <= 2048 or memory[LENGTH+p] < 0:
            raise ValueError('Invalid phrase capacity or duration')
        previous = -1
        for j in range(int(n)):
            t, st, d1, d2, offset = memory[p*STRIDE+j*5:p*STRIDE+j*5+5]
            if t < previous or offset < 0 or any(int(x) != x for x in (st,d1,d2)) or not 128 <= st <= 239 or not 0 <= d1 <= 127 or not 0 <= d2 <= 127:
                raise ValueError('Invalid source MIDI event')
            previous = t


def timing(patch, scale):
    result = copy.deepcopy(patch)
    memory = result['memory']
    result['globals'][0] *= scale
    for p in range(LAYERS):
        memory[LENGTH+p] *= scale
        for j in range(int(memory[COUNT+p])):
            i = p*STRIDE+j*5
            memory[i] *= scale
            memory[i+4] *= scale
        # These are playheads/trigger counters, never performance configuration.
        for base in (TRIGGER, POSITION, REPEAT):
            memory[base+p] = 0
    return result


def capture(patch, sample_rate, project_id=None, parent=None, name='Untitled'):
    validate_patch(patch)
    payload = {'name': str(name)[:128], 'timeUnit': 'seconds',
               'patch': timing(patch, 1/rate(sample_rate))}
    project_id = project_id or str(uuid.uuid4())
    envelope = dict(format=FORMAT, version=1, projectId=project_id,
                    parentRevisionId=parent, payload=payload)
    envelope['revisionId'] = digest(envelope)
    envelope['contentHash'] = digest(envelope)
    validate(envelope)
    return envelope


def validate(project):
    if not isinstance(project, dict) or set(project) != {'format','version','projectId','revisionId','parentRevisionId','payload','contentHash'}:
        raise ValueError('Unknown portable fields; refusing destructive migration')
    if project['format'] != FORMAT or type(project['version']) is not int or project['version'] != 1:
        raise ValueError('Unsupported portable project version')
    try:
        uuid.UUID(project['projectId'])
    except (ValueError, TypeError, AttributeError):
        raise ValueError('Invalid stable project identity') from None
    parent = project['parentRevisionId']
    if parent is not None and (not isinstance(parent,str) or len(parent)!=64 or any(c not in '0123456789abcdef' for c in parent)):
        raise ValueError('Invalid parent revision')
    unsigned = {k:v for k,v in project.items() if k != 'contentHash'}
    if digest(unsigned) != project['contentHash'] or digest({k:v for k,v in unsigned.items() if k != 'revisionId'}) != project['revisionId']:
        raise ValueError('Portable content hash/revision mismatch')
    payload = project['payload']
    if not isinstance(payload,dict) or set(payload) != {'name','timeUnit','patch'} or payload['timeUnit'] != 'seconds' or not isinstance(payload['name'],str) or len(payload['name'])>128:
        raise ValueError('Unsupported portable payload')
    validate_patch(payload['patch'])
    if len(canonical(project)) > MAX_BYTES:
        raise ValueError('Project exceeds bounded control capacity')
    return project


def materialize(project, sample_rate, adapter='native'):
    validate(project)
    patch = timing(project['payload']['patch'], rate(sample_rate))
    if adapter == 'reaper':
        # Preserve the portable original, reject execution of native-only data.
        ce = patch.get('controllerEngine',{})
        gs = patch.get('globalSnapshots',{})
        from controller_config import decode
        if (ce and (decode(ce)['sources'] or decode(ce)['mappings'])) or (len(gs.get('configuration',[])) >= 4 and gs['configuration'][3]):
            raise ValueError('REAPER execution of native controllers/snapshots is not supported; portable original retained')
        # Unknown shapes must not be guessed to mean an empty configuration.
        if ce and set(ce)-{'version','configuration'}:
            raise ValueError('Unsupported REAPER controller configuration')
        patch.pop('controllerEngine',None)
        patch.pop('globalSnapshots',None)
    elif adapter != 'native':
        raise ValueError('Unknown execution adapter')
    return patch
