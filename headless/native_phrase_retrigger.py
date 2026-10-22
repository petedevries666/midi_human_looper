"""Native phrase attack policy; keep the frozen REAPER source unchanged."""
def extend(source):
    def change(old,new):
        nonlocal source
        if source.count(old)!=1:
            raise ValueError('Native phrase retrigger contract changed: '+old[:80])
        source=source.replace(old,new)
    # Logical owners still share their final release, but every admitted phrase
    # attack must reach the synth. Never fabricate an Off before a repeated On.
    change('native_phrase_contract>=2 && instrument_output_owners(ch,note,-1)>1 ? 1 : ', '')
    change('kind==15 ? 1 :', 'kind==15 ? 2 :')
    # Preserve the old <=100% calculation exactly; bound growth before pow so
    # arbitrarily long trigger sessions cannot overflow floating point.
    anchor='function phrase_velocity_decay_gain(rate,repeats,pitch,pivot,bias)'
    change(anchor, '''function native_phrase_repeat_gain(rate,repeats)
(rate<=1?pow(rate,repeats):pow(rate,min(max(0,repeats),(100*log(10))/log(rate))););
'''+anchor)
    for repeats in ('instance_repeat','mem[REPEAT_BASE+requested_layer]'):
        change('instance_gain=pow(mem[DECAY_BASE+requested_layer],'+repeats+');',
               'instance_gain=native_phrase_repeat_gain(mem[DECAY_BASE+requested_layer],'+repeats+');')
    return source
