"""Native playback speed; source timestamps and recorded pitch stay unchanged."""
def extend(source):
    def change(old,new):
        nonlocal source
        if source.count(old)!=1:raise ValueError('Native RATE contract changed: '+old[:90])
        source=source.replace(old,new)
    change('function instance_discard_all()',
           'NATIVE_PHRASE_RATE_BASE=CONDUCTOR_BASE-6500;\nfunction instance_discard_all()')
    change('function phrase_time_factor(layer)', '''function native_phrase_rate(layer)
local(r)
(r=mem[NATIVE_PHRASE_RATE_BASE+layer];r>=.1 && r<=16?r:1;);
function native_phrase_period(layer)
(max(1,floor(mem[LEN_BASE+layer]/native_phrase_rate(layer)+.5)););
function native_conductor_rate(b,j)
local(a,r)
(a=mem[b+79];r=mem[a+2+mem[a]*4+mem[b+2]+j];r>=.1 && r<=16?r:1;);
function native_capture_position(offs)
(overdub_pos+offs*(native_free_time?native_phrase_rate(overdub_layer):1););
function phrase_time_factor(layer)''')
    change('local(h,step,b,n,j,v,free,valid,p,mode,ratio,repeats,last,t,oldmode,oldhold,olddecay,oldtime,id,', 'local(h,step,b,n,j,v,free,valid,p,mode,ratio,repeats,last,t,oldmode,oldhold,olddecay,oldtime,native_old_rate,id,')
    change('  exp(exponent);', '  exp(exponent)/native_phrase_rate(layer);')
    change('t=exp(max(-log(64),min(log(64),log(ratio)*repeats)));',
           't=exp(max(-log(64),min(log(64),log(ratio)*repeats)))/native_conductor_rate(b,j);')
    # Admission snapshots the effective time multiplier. The source's setting
    # is restored before any other layer is admitted, including the same phrase.
    change('oldtime=mem[phrase_time_addr(p)];',
           'oldtime=mem[phrase_time_addr(p)];native_old_rate=mem[NATIVE_PHRASE_RATE_BASE+p];mem[NATIVE_PHRASE_RATE_BASE+p]=native_conductor_rate(b,j);')
    change('mem[phrase_time_addr(p)]=oldtime;',
           'mem[phrase_time_addr(p)]=oldtime;mem[NATIVE_PHRASE_RATE_BASE+p]=native_old_rate;')
    # Free LOOP sources use their own sample-clock renderer, not voice time.
    change('local(fl,period,position,left,cursor,span,count,j,b,at,st,d1,d2,countkey)', 'local(fl,period,position,left,cursor,span,count,j,b,at,st,d1,d2,countkey,playback_rate)')
    change('period=max(1,mem[LEN_BASE+fl]);', 'playback_rate=native_phrase_rate(fl);period=native_phrase_period(fl);')
    change('loop(count,b=layer_base(fl,j);at=mem[b];',
           'loop(count,b=layer_base(fl,j);at=playback_rate==1?mem[b]:(mem[b]<mem[LEN_BASE+fl]?min(period-1,floor(mem[b]/playback_rate+.5)):period);')
    change('!instance_poly_routes()?(instance_error=3;instance_rejected+=1;free_play_error=layer+1;):loop_len_samples>0?(',
           '!instance_poly_routes()?(instance_error=3;instance_rejected+=1;free_play_error=layer+1;):loop_len_samples>0 && (native_phrase_period(layer)>=max(128,samplesblock/8) || (free_play_error=layer+1;instance_error=3;instance_rejected+=1;0;))?(')
    # Overdub positions remain in SOURCE samples; capture-window bounds stay
    # in callback samples. New notes then align with the audible rated loop.
    change('free_od_len=max(1,mem[LEN_BASE+overdub_layer]);',
           'free_od_len=native_phrase_period(overdub_layer);')
    change('overdub_pos=-free_od_boundary;',
           'overdub_pos=-free_od_boundary*native_phrase_rate(overdub_layer);')
    change('chain_capture_start=max(0,-overdub_pos);chain_capture_end=min(samplesblock,mem[LEN_BASE+overdub_layer]-overdub_pos);',
           'chain_capture_start=max(0,-overdub_pos/native_phrase_rate(overdub_layer));chain_capture_end=min(samplesblock,(mem[LEN_BASE+overdub_layer]-overdub_pos)/native_phrase_rate(overdub_layer));')
    change('overdub_pos=native_free_time?-offset:0;',
           'overdub_pos=native_free_time?-offset*native_phrase_rate(overdub_layer):0;')
    change('chain_capture_end=min(samplesblock,mem[LEN_BASE+overdub_layer]+offset);',
           'chain_capture_end=min(samplesblock,mem[LEN_BASE+overdub_layer]/native_phrase_rate(overdub_layer)+offset);')
    for old,new in (
        ('overdub_pos+offset<mem[LEN_BASE+overdub_layer]', 'native_capture_position(offset)<mem[LEN_BASE+overdub_layer]'),
        ('chain_capture_origin=overdub_pos+offset;', 'chain_capture_origin=native_capture_position(offset);'),
        ('store_event(overdub_layer,overdub_pos+offset-', 'store_event(overdub_layer,native_capture_position(offset)-'),
        ('overdub_pos+=samplesblock;', 'overdub_pos+=samplesblock*(native_free_time?native_phrase_rate(overdub_layer):1);')):
        change(old,new)
    return source
