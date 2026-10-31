"""Native gesture playback modes; preserve legacy MODE/controller normalization."""
HELPERS = r'''
function native_phrase_mode(p)
(mem[MODE_BASE+p]>=3?mem[MODE_BASE+p]:mem[NATIVE_PHRASE_PLAY_MODE_BASE+p]>=3?mem[NATIVE_PHRASE_PLAY_MODE_BASE+p]:mem[MODE_BASE+p];);
function native_phrase_active(p)
(phrase_playing(p) || (mem[TRIG_BASE+p]>.5 && mem[instance_header(MAX_ONCE_VOICES+p)+11]>.5););
function native_phrase_stop(p,offs)
(phrase_toggle_stop(p,offs);mem[TRIG_BASE+p]>.5 && mem[instance_header(MAX_ONCE_VOICES+p)+11]>.5?free_loop_stop_at(p,offs););
function native_gate_release_source(p,offs) local(v,h)
(v=0;loop(MAX_ONCE_VOICES,h=instance_header(v);
 mem[VOICE_ACTIVE_BASE+v]>.5 && mem[VOICE_LAYER_BASE+v]==p && mem[h+8]==3 && mem[h+12]==0?(
  phrase_render_voice(v,mem[VOICE_POS_BASE+v]+offs,0);instance_stop_voice(v,offs);
 );v+=1;););
function native_gate_release_switch(si,offs) local(v,h,id,stroke)
(v=0;id=mem[sw_cfg(si)+21];stroke=mem[sw_rt(si)+12]+1;
 loop(MAX_ONCE_VOICES,h=instance_header(v);
  mem[VOICE_ACTIVE_BASE+v]>.5 && mem[h+8]==3 && mem[h+12]==id && mem[NATIVE_GATE_STROKE_BASE+v]==stroke?(
   phrase_render_voice(v,mem[VOICE_POS_BASE+v]+offs,0);instance_stop_voice(v,offs);
  );v+=1;
 ););
function native_phrase_reclaimable(b,phase,mask,longMask,releaseMask,chargeMask) local(v,j,p,mode,found,result)
(v=0;result=0;loop(MAX_ONCE_VOICES,found=0;
 mem[VOICE_ACTIVE_BASE+v]>.5?(j=0;loop(min(MAX_ONCE_VOICES,mem[b+2]),p=mem[b+4+j*5];mode=mem[b+5+j*5]>=0?mem[b+5+j*5]:native_phrase_mode(p);
  mem[VOICE_LAYER_BASE+v]==p && (mode==4 || mode==5) && layer_audible(p) &&
  ((!phase && !((mask|longMask|releaseMask|chargeMask)&(1<<j))) || (phase==1 && (mask&(1<<j))) || (phase==2 && (longMask&(1<<j))) || (phase==3 && (releaseMask&(1<<j))) || (phase==4 && (chargeMask&(1<<j))))?found=1;j+=1;
 ););result+=found;v+=1;);result;);
'''

WRAPPER = r'''
function process_phrase_trigger(start_offset,play_only) local(p,kind,saved,id,v,h,gateHeld)
(
 p=trigger_request;p>=0 && p<LAYERS?(
  kind=native_phrase_mode(p);
  kind<3?native_phrase_trigger_core(start_offset,play_only):(
   trigger_request=-1;instance_last_admitted=0;instance_error=0;
   kind==5 && native_phrase_active(p)?native_phrase_stop(p,start_offset):(
    gateHeld=0;kind==3 && native_gate_switch<0?(v=0;loop(MAX_ONCE_VOICES,h=instance_header(v);mem[VOICE_ACTIVE_BASE+v]>.5 && mem[VOICE_LAYER_BASE+v]==p && mem[h+8]==3 && mem[h+12]==0?gateHeld=1;v+=1;););
    !gateHeld && !(kind==3 && native_gate_switch>=0 && mem[sw_rt(native_gate_switch)]<=0)?(
     !instance_poly_routes() || layer_count(p)<=0 || mem[LEN_BASE+p]<=0 || instance_serial>=9007199254740990?(
      instance_error=instance_serial>=9007199254740990?5:3;instance_rejected+=1;
     ):(
      kind==4?native_phrase_stop(p,start_offset);
      saved=mem[MODE_BASE+p];mem[MODE_BASE+p]=1;trigger_request=p;
      native_phrase_trigger_core(start_offset,play_only);mem[MODE_BASE+p]=saved;id=instance_last_admitted;
      id>0?(v=0;loop(MAX_ONCE_VOICES,h=instance_header(v);mem[h]==id?(
       mem[h+7]=1;mem[h+8]=kind;mem[NATIVE_GATE_STROKE_BASE+v]=native_gate_switch>=0?mem[sw_rt(native_gate_switch)+12]+1:0;
      );v+=1;););
     );
    );
   );
  );
 );
);
'''

def extend(source):
    def change(old, new, count=1):
        nonlocal source
        if source.count(old) != count:
            raise ValueError('Native phrase modes contract changed: '+old[:100])
        source = source.replace(old, new)
    change('function instance_discard_all()', '''NATIVE_PHRASE_PLAY_MODE_BASE=CONDUCTOR_BASE-8400;
NATIVE_GATE_STROKE_BASE=CONDUCTOR_BASE-8256;native_gate_switch=-1;
function instance_discard_all()''')
    change('function native_hold_release(layer,offs)', HELPERS+'\nfunction native_hold_release(layer,offs)')
    change('  !native_phrase_contract && native_hold_enabled && mem[MODE_BASE+layer]==2',
           '  native_gate_release_source(layer,offs);\n  !native_phrase_contract && native_hold_enabled && mem[MODE_BASE+layer]==2')
    change('function process_phrase_trigger(start_offset,play_only)', 'function native_phrase_trigger_core(start_offset,play_only)')
    change('function phrase_admit_independent(layer,offs)', WRAPPER+'\nfunction phrase_admit_independent(layer,offs)')
    # Legacy controller curves keep their original 0..2 normalization. An
    # explicitly selected gesture mode temporarily takes precedence over them.
    change('    value=max(param_min(kind),min(param_max(kind),value));',
           '    kind==20 && mem[NATIVE_PHRASE_PLAY_MODE_BASE+gi]>=3?value=1;\n    value=max(param_min(kind),min(param_max(kind),value));')
    change('mem[MODE_BASE+gi]=mem[b];mem[TRIG_BASE+gi]=',
           'mem[MODE_BASE+gi]=mem[NATIVE_PHRASE_PLAY_MODE_BASE+gi]>=3?1:mem[b];mem[TRIG_BASE+gi]=')

    change('mem[instance_header(vi)+7]>0?mem[instance_header(vi)+8]!=1:', 'mem[instance_header(vi)+7]>0?(mem[instance_header(vi)+8]==0 || mem[instance_header(vi)+8]==2):')
    # New modes share ONCE timing but keep their actual mode in the voice header.
    change('function phrase_voice_mode(vi) (mem[instance_header(vi)+7]>0?mem[instance_header(vi)+8]:mem[MODE_BASE+mem[VOICE_LAYER_BASE+vi]];);',
           'function phrase_voice_mode(vi) (mem[instance_header(vi)+8]>=3?1:mem[instance_header(vi)+7]>0?mem[instance_header(vi)+8]:mem[MODE_BASE+mem[VOICE_LAYER_BASE+vi]];);')
    change('mem[MODE_BASE+once_layer];\n  count=', 'mem[MODE_BASE+once_layer];mode>=3?mode=1;\n  count=')
    change('(mem[CONDUCTOR_GESTURE_BASE+si*8+3]>0?mem[CONDUCTOR_GESTURE_BASE+si*8+6]=1;',
           '(native_gate_release_switch(si,offs);mem[CONDUCTOR_GESTURE_BASE+si*8+3]>0?mem[CONDUCTOR_GESTURE_BASE+si*8+6]=1;')
    change('mode=mem[b+5+j*5]>=0?mem[b+5+j*5]:mem[MODE_BASE+p];',
           'mode=mem[b+5+j*5]>=0?mem[b+5+j*5]:native_phrase_mode(p);')
    change('(mode!=1 && mem[LEN_BASE+p]*t<max(128,samplesblock/8))?valid=0;n+=1;',
           '((mode==0 || mode==2) && mem[LEN_BASE+p]*t<max(128,samplesblock/8)) || (mode==3 && phase>=3)?valid=0;!(mode==5 && native_phrase_active(p))?n+=1;')
    change('mov+1>64-(snap_host_write-snap_host_read+native_control_count)',
           'mem[b+2]==1?free+=native_phrase_reclaimable(b,phase,mask,longMask,releaseMask,chargeMask);mov+1>64-(snap_host_write-snap_host_read+native_control_count)')
    change('oldtime,native_old_rate,id,owner', 'oldtime,native_old_rate,native_old_play_mode,id,owner')
    change('      mem[b+5+j*5]>=0?mem[MODE_BASE+p]=mem[b+5+j*5];',
           '      native_old_play_mode=mem[NATIVE_PHRASE_PLAY_MODE_BASE+p];mem[b+5+j*5]>=0?(mem[NATIVE_PHRASE_PLAY_MODE_BASE+p]=0;mem[MODE_BASE+p]=mem[b+5+j*5];);')
    change('      id=phrase_admit_independent(p,offs);',
           '      native_gate_switch=si;id=phrase_admit_independent(p,offs);native_gate_switch=-1;mem[NATIVE_PHRASE_PLAY_MODE_BASE+p]=native_old_play_mode;')
    return source
