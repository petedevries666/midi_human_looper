"""Native BASS policies, selected per instrument; legacy values 0..3 unchanged."""
HELPERS=r'''
function native_bass_mode(gi) local(a,mode)
(a=NATIVE_BASS_POLICY_BASE+gi*3;mode=floor(mem[engine_addr(INST_NOTE_MODE_BASE,gi)]+0.5);
 mode==1 && mem[a+1]==mem[I_IDS_BASE+gi] && mem[a+2]==tf_id(gi,3) && mem[a]>0?3+mem[a]:mode;);

function native_bass_select(gi,v) local(a,id)
(a=NATIVE_BASS_OWNER_BASE+gi*2;id=mem[instance_header(v)];
 id>mem[a+1]?(mem[a]=v+1;mem[a+1]=id;););
function native_bass_note(gi) local(a,v,valid,n,result,live,count)
(a=NATIVE_BASS_OWNER_BASE+gi*2;v=mem[a]-1;
 valid=v>=0 && mem[instance_header(v)]==mem[a+1];n=0;result=-1;
 loop(128,
  live=max(0,mem[engine_addr(MONO_HELD_COUNT_BASE,gi*128+n)]-mem[engine_addr(SW_MONO_PHRASE_BASE,gi*128+n)]);
  count=valid?mem[NATIVE_MONO_SOURCE_BASE+(v*INST_CAP+gi)*128+n]:0;
  result<0 && (live>0 || count>0)?result=n;n+=1;
 );result;);
function native_bass_source(gi,note) local(a,v)
(a=NATIVE_BASS_OWNER_BASE+gi*2;v=mem[a]-1;
 v>=0 && mem[instance_header(v)]==mem[a+1] && mem[NATIVE_MONO_SOURCE_BASE+(v*INST_CAP+gi)*128+note]>0?v:-1;);
function native_bass_accept(gi,v,typ,velocity)
(v<0 || typ!=144 || velocity<=0 || !transformer_on(gi,3) || native_bass_mode(gi)!=5 || mem[instance_header(v)+8]==2;);
'''

def extend(source):
    def change(old,new):
        nonlocal source
        if source.count(old)!=1:raise ValueError('Native BASS policy contract changed: '+old[:90])
        source=source.replace(old,new)
    change('function instance_discard_all()', 'NATIVE_BASS_OWNER_BASE=CONDUCTOR_BASE-6300;\nNATIVE_BASS_POLICY_BASE=CONDUCTOR_BASE-6250;\nfunction instance_discard_all()')
    change('mode=floor(mem[engine_addr(INST_NOTE_MODE_BASE,gi)]+0.5);', 'mode=native_bass_mode(gi);')
    change('function mono_desired_note(gi, mode)', HELPERS+'\nfunction mono_desired_note(gi, mode)')
    change('best=-1;\n  mode==1 ? (', 'best=-1;\n  mode>=4 ? best=native_bass_note(gi) : mode==1 ? (')
    change('  desired=mono_desired_note(gi,mode);', '  mode>=4 && is_on && source_voice>=0?native_bass_select(gi,source_voice);\n  desired=mono_desired_note(gi,mode);')
    change('  desired!=active ? (', '''  mode>=4 && desired>=0?(new_source=native_bass_source(gi,desired);new_owner=new_source>=0?1:-1;);
  desired!=active || (mode>=4 && desired>=0 && (new_source!=old_source || (is_on && source_voice==new_source && note==desired))) ? (''')
    # The audible output belongs only to the selected phrase or live source.
    # Older logical notes stay tracked for cleanup but cannot retain its gate.
    change('mem[engine_addr(SW_LIVE_OUT_BASE,key)]=mem[engine_addr(MONO_HELD_COUNT_BASE,gi*128+desired)]>mem[engine_addr(SW_MONO_PHRASE_BASE,gi*128+desired)];',
           'mem[engine_addr(SW_LIVE_OUT_BASE,key)]=mode>=4?new_owner<0:mem[engine_addr(MONO_HELD_COUNT_BASE,gi*128+desired)]>mem[engine_addr(SW_MONO_PHRASE_BASE,gi*128+desired)];')
    change('mem[engine_addr(SW_PHRASE_OUT_BASE,key)]=mem[engine_addr(SW_MONO_PHRASE_BASE,gi*128+desired)]>0;',
           'mem[engine_addr(SW_PHRASE_OUT_BASE,key)]=mode>=4?new_owner>0:mem[engine_addr(SW_MONO_PHRASE_BASE,gi*128+desired)]>0;')
    change('mem[I_EXISTS_BASE+ii] && mem[engine_addr(INST_ENABLED_BASE,ii)]>0.5 && (once_route_voice<0 || instance_inst_id(once_route_voice,ii)==mem[I_IDS_BASE+ii]) ? (',
           'mem[I_EXISTS_BASE+ii] && mem[engine_addr(INST_ENABLED_BASE,ii)]>0.5 && (once_route_voice<0 || instance_inst_id(once_route_voice,ii)==mem[I_IDS_BASE+ii]) && native_bass_accept(ii,once_route_voice,typ,d2) ? (')
    # Bypass, deletion, patch reset and PANIC share this production reset hook.
    change('function i_clear_runtime(gi)\nlocal(j,idx,v)\n(',
           'function i_clear_runtime(gi)\nlocal(j,idx,v)\n(mem[NATIVE_BASS_OWNER_BASE+gi*2]=0;mem[NATIVE_BASS_OWNER_BASE+gi*2+1]=0;')
    return source
