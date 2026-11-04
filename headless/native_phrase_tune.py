"""Playback-only phrase transposition; frozen recordings and input keys stay intact."""
def extend(source):
    def change(old, new):
        nonlocal source
        if source.count(old) != 1:
            raise ValueError('Native phrase TUNE contract changed: '+old[:80])
        source = source.replace(old, new)
    change('function instance_discard_all()', '''NATIVE_PHRASE_TUNE_BASE=CONDUCTOR_BASE-7800;
NATIVE_VOICE_TUNE_BASE=CONDUCTOR_BASE-7600;
function instance_discard_all()''')
    change('h=instance_header(voice_slot);mem[h+15]=',
           'mem[NATIVE_VOICE_TUNE_BASE+voice_slot]=mem[NATIVE_PHRASE_TUNE_BASE+requested_layer];h=instance_header(voice_slot);mem[h+15]=')
    change('mem[h+6]=1;mem[h+7]=0;',
           'mem[NATIVE_VOICE_TUNE_BASE+v]=mem[NATIVE_PHRASE_TUNE_BASE+layer];mem[h+6]=1;mem[h+7]=0;')
    # The compiler appends one effective tune per admitted phrase after actions.
    # Set it on the newly admitted owner, never on the shared source.
    change('mem[owner+12]=mem[h];',
           'mem[NATIVE_VOICE_TUNE_BASE+v]=mem[mem[b+79]+1+mem[mem[b+79]]*4+j];mem[owner+12]=mem[h];')
    # Release lookup uses the ORIGINAL recorded input key, before transposition.
    # Only attacks are shifted; their actual output is captured by the existing
    # ownership ledger, so Off, sustain, STOP and PANIC release the same pitch.
    change('instance_route_record=-1;\n  once_route_voice>=0',
           'instance_route_record=-1;\n  once_route_voice>=0 && typ==144 && d2>0 ? d1=max(0,min(127,d1+mem[NATIVE_VOICE_TUNE_BASE+once_route_voice]));\n  once_route_voice>=0')
    return source
