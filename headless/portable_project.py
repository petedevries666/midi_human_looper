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
MARKERS = (164892,165316,165829,166494,166828,168366)


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
    if any(memory[index]!=version for version,index in enumerate(MARKERS,2)):
        raise ValueError('Invalid schema-7 extension markers')
    if int(globals_[8])!=globals_[8] or not 0<=globals_[8]<LAYERS:
        raise ValueError('Invalid phrase identity')
    from registry import REGISTRY
    supported={code for code in REGISTRY.engine_types if code>0}
    # Resolve existing schema-7 instance codes exactly like transform_type().
    # 7..11 are instance slots, not new effect types. Do not alias them across
    # instruments or silently execute future unsupported module records.
    for instrument in range(8):
        count_index=164851+instrument if instrument<3 else 168474+instrument-3
        type_index=164854+instrument*6 if instrument<3 else 169964+(instrument-3)*6
        count=memory[count_index]
        if int(count)!=count or not 0<=count<=6:raise ValueError('Invalid Transformer chain length')
        used=set()
        for slot in range(int(count)):
            code=abs(memory[type_index+slot])
            if int(code)!=code or not 1<=code<=11 or code in used:raise ValueError('Invalid/aliased Transformer instance code')
            used.add(code)
            if code>=7:
                index=instrument*5+int(code)-7
                address=166513+index*21 if index<15 else 171124+(index-15)*21
                kind=memory[address]
                if kind in (3,5):raise ValueError('Stateful Transformer stacking is unsupported; original retained')
            else:kind=code
            if kind not in supported:raise ValueError('Unsupported Transformer capability; original retained')
    for p in range(LAYERS):
        n = memory[COUNT+p]
        if int(n) != n or not 0 <= n <= 2048 or memory[LENGTH+p] < 0:
            raise ValueError('Invalid phrase capacity or duration')
        notes=[]
        for j in range(int(n)):
            t, st, d1, d2, offset = memory[p*STRIDE+j*5:p*STRIDE+j*5+5]
            if t < 0 or offset < 0 or any(int(x) != x for x in (st,d1,d2)) or not 128 <= st <= 239 or not 0 <= d1 <= 127 or not 0 <= d2 <= 127:
                raise ValueError('Invalid source MIDI event')
            if int(st)&240 in (128,144):notes.append([t,int(st),int(d1),int(d2)])
        from phrase_midi import validate_notes
        validate_notes(sorted(notes,key=lambda event:event[0]))


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
    # MIDI source events are emitted on the destination sample grid. This also
    # prevents harmless floating error from failing the native fixed-grid guard.
    patch['globals'][0]=round(patch['globals'][0])
    for phrase in range(LAYERS):
        patch['memory'][LENGTH+phrase]=round(patch['memory'][LENGTH+phrase])
        for event in range(int(patch['memory'][COUNT+phrase])):
            index=phrase*STRIDE+event*5
            patch['memory'][index]=round(patch['memory'][index])
            patch['memory'][index+4]=round(patch['memory'][index+4])
    if adapter == 'reaper':
        # Preserve the portable original, reject execution of native-only data.
        ce = patch.get('controllerEngine',{})
        gs = patch.get('globalSnapshots',{})
        from controller_config import decode
        if ce and set(ce) != {'version','configuration'}:
            raise ValueError('Unsupported REAPER controller configuration')
        if ce and (decode(ce)['sources'] or decode(ce)['mappings']):
            raise ValueError('REAPER cannot execute native Controller Engine assignments; portable original retained')
        if gs:
            wire=gs.get('configuration');version=gs.get('version')
            size={1:4,2:196,3:200,4:200}.get(version)
            if (set(gs) != {'version','configuration'} or not isinstance(wire,list) or
                len(wire)!=size or wire[0]!=version or wire[1]<1 or wire[2]!=0 or wire[3]!=0 or any(wire[4:])):
                raise ValueError('REAPER cannot execute native Snapshots/actions/A-B; portable original retained')
        patch.pop('controllerEngine',None)
        patch.pop('globalSnapshots',None)
    elif adapter != 'native':
        raise ValueError('Unknown execution adapter')
    return patch
