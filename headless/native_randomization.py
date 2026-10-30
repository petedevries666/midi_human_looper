"""Native phrase randomization; fixed RAM, transactional admission, original MIDI intact."""
DECLARATIONS = r'''
NATIVE_RANDOM_SOURCE=30000000;NATIVE_RANDOM_CFG=NATIVE_RANDOM_SOURCE+128*8;
NATIVE_RANDOM_STATE=NATIVE_RANDOM_CFG+140*8;NATIVE_RANDOM_PREFIX=NATIVE_RANDOM_STATE+140*16;
NATIVE_RANDOM_PEDALS=NATIVE_RANDOM_PREFIX+140*2048;NATIVE_RANDOM_STATS=NATIVE_RANDOM_PEDALS+140*16;
NATIVE_RANDOM_PLANS=NATIVE_RANDOM_STATS+128*4;NATIVE_RANDOM_LAYER=NATIVE_RANDOM_PLANS+12*10;
NATIVE_RANDOM_EPOCH=NATIVE_RANDOM_LAYER+64;NATIVE_RANDOM_EPOCH_TMP=NATIVE_RANDOM_EPOCH+64;
NATIVE_RANDOM_EVENT=NATIVE_RANDOM_EPOCH_TMP+16;NATIVE_RANDOM_DIRECT_PLAN=NATIVE_RANDOM_EVENT+8;
NATIVE_RANDOM_ELIGIBLE=NATIVE_RANDOM_DIRECT_PLAN+16;NATIVE_RANDOM_PITCH_LAST=NATIVE_RANDOM_ELIGIBLE+256;NATIVE_RANDOM_PITCH_READY=NATIVE_RANDOM_PITCH_LAST+128;NATIVE_RANDOM_END=NATIVE_RANDOM_PITCH_READY+128;native_random_enabled=1;
native_random_seed=123457;native_random_cycle_seed=98761;native_random_current=-1;native_random_preplanned=0;native_random_transaction=0;
'''

BASIC = r'''
function native_random_begin() (native_random_work=max(1,native_random_seed);native_random_error=0;);
// Schrage reduction keeps every intermediate inside signed 31 bits on ARM.
function native_random_draw() local(hi,lo)
(hi=floor(native_random_work/127773);lo=native_random_work-hi*127773;native_random_work=16807*lo-2836*hi;native_random_work<=0?native_random_work+=2147483647;native_random_work/2147483647;);
function native_random_commit() (native_random_seed=native_random_work;);
function native_random_stats(p) local(i,b,lo,hi,mask)
(
 b=NATIVE_RANDOM_STATS+p*4;mem[b]==0?(
  lo=128;hi=-1;mask=0;i=0;loop(layer_count(p),
   (mem[layer_base(p,i)+1]&240)==144 && mem[layer_base(p,i)+3]>0?(
    lo=min(lo,mem[layer_base(p,i)+2]);hi=max(hi,mem[layer_base(p,i)+2]);mask|=1<<(mem[layer_base(p,i)+2]%12);
   );i+=1;);
  mem[b]=1;mem[b+1]=mask;mem[b+2]=lo;mem[b+3]=hi;
 );b;
);
function native_random_quantize(note,mask,direction) local(distance,lo,hi,found,result)
(
 note=max(0,min(127,note));result=note;distance=0;found=0;
 while(distance<12 && !found)(
  lo=note-distance;hi=note+distance;
  direction>0 && hi<=127 && (mask&(1<<(hi%12)))?(result=hi;found=1;):
  lo>=0 && (mask&(1<<(lo%12)))?(result=lo;found=1;):
  hi<=127 && (mask&(1<<(hi%12)))?(result=hi;found=1;);
  distance+=1;
 );result;
);
function native_random_pitch_allowed(p,tune,delta,mask) local(stats)
(stats=native_random_stats(p);mem[stats+3]>=0 && mask>0;);
function native_random_pitch_commit(p,plan)
(plan>=0 && mem[plan+3]>0?(mem[NATIVE_RANDOM_PITCH_LAST+p]=mem[plan+8];mem[NATIVE_RANDOM_PITCH_READY+p]=1;););
function native_random_pitch(p,tune,cfg) local(delta,n,choices,pick,result,last,ready,valid)
(
 result=0;mem[cfg+3]>0?(
  last=mem[NATIVE_RANDOM_PITCH_LAST+p];ready=mem[NATIVE_RANDOM_PITCH_READY+p];
  delta=mem[cfg+4];n=0;choices=0;loop(mem[cfg+5]-delta+1,valid=native_random_pitch_allowed(p,tune,delta,mem[cfg+6]);n+=valid;valid && (!ready || delta!=last)?choices+=1;delta+=1;);
  n<=0?(native_random_error=20;result=1000;):(
   choices<=0?(choices=n;ready=0;);pick=choices>1?floor(native_random_draw()*choices):0;delta=mem[cfg+4];
   loop(mem[cfg+5]-delta+1,native_random_pitch_allowed(p,tune,delta,mem[cfg+6]) && (!ready || delta!=last)?(pick==0?result=delta;pick-=1;);delta+=1;);
  );
 );result;
);
function native_random_view(p,i,rev)
(rev?native_direction_event(p,i,1):layer_base(p,mem[NATIVE_REVERSE_ORDER+p*2048+i]););
function native_random_start(p,cfg,rev,time,repeats) local(window,limit,i,b,last,n,pick,result)
(
 result=0;mem[cfg]>0?(
  limit=max(0,mem[LEN_BASE+p]-(repeats?ceil(max(128,samplesblock/8)/max(.000001,time)):1));
  window=min(limit,floor((mem[LEN_BASE+p]-1)*mem[cfg]));
  mem[cfg+1]>0?(window>0?result=floor(native_random_draw()*(window+1));):(
   i=0;n=0;last=-1;loop(layer_count(p),b=native_random_view(p,i,rev);
    mem[b]<=window && (mem[b+1]&240)==144 && mem[b+3]>0 && mem[b]!=last?(n+=1;last=mem[b];);i+=1;
   );
   n>0?(pick=n>1?floor(native_random_draw()*n):0;last=-1;i=0;
    loop(layer_count(p),b=native_random_view(p,i,rev);mem[b]<=window && (mem[b+1]&240)==144 && mem[b+3]>0 && mem[b]!=last?(pick==0?result=mem[b];pick-=1;last=mem[b];);i+=1;);
   );
  );
 );result;
);
function native_random_rebase_start(p,cfg,rev,time,repeats,desired) local(limit,window,i,b,distance,best,result)
(limit=max(0,mem[LEN_BASE+p]-(repeats?ceil(max(128,samplesblock/8)/max(.000001,time)):1));window=min(limit,floor((mem[LEN_BASE+p]-1)*mem[cfg]));result=min(desired,window);
 mem[cfg+1]<=0?(result=0;best=1000000000000000000000000000000;i=0;loop(layer_count(p),b=native_random_view(p,i,rev);mem[b]<=window && (mem[b+1]&240)==144 && mem[b+3]>0?(distance=abs(mem[b]-desired);distance<best?(best=distance;result=mem[b];););i+=1;););result;);
function native_random_cycle_start(p,cfg,rev,time) local(old,result)
(old=native_random_work;native_random_work=max(1,native_random_cycle_seed);result=native_random_start(p,cfg,rev,time,1);native_random_cycle_seed=native_random_work;native_random_work=old;result;);
function native_random_plan(p,mode,time,cfg,tune,rev,plan) local(j,delta,start)
(
 j=0;loop(8,mem[plan+j]=mem[cfg+j];j+=1;);mode==0 && mem[LEN_BASE+p]*time<max(128,samplesblock/8)?native_random_error=21;delta=native_random_pitch(p,tune,cfg);start=0;
 delta!=1000 && mem[cfg]>0?(!native_reverse_prepare(p)?native_random_error=21:start=native_random_start(p,cfg,rev,time,mode==0););
 mem[plan+7]=mode==0;mem[plan+8]=delta;mem[plan+9]=start;delta!=1000 && native_random_error==0;
);
function native_random_prefix_prepare(v,p,start,rev) local(i,b,st,ch,index,other,a,epoch)
(
 a=NATIVE_RANDOM_PREFIX+v*2048;memset(a,0,2048);memset(NATIVE_RANDOM_PEDALS+v*16,0,16);memset(NATIVE_RANDOM_EPOCH_TMP,0,16);
 start>0?(i=0;loop(layer_count(p),index=mem[NATIVE_REVERSE_ORDER+p*2048+(rev?layer_count(p)-1-i:i)];b=native_random_view(p,i,rev);
  mem[b]<start?(
   st=mem[b+1]&240;ch=mem[b+1]&15;
   st==144 && mem[b+3]>0?mem[a+index]=1:
   st==128 || (st==144 && mem[b+3]==0)?(
    other=mem[NATIVE_REVERSE_PAIR+p*2048+index]-1;other>=0?mem[a+other]=mem[NATIVE_RANDOM_PEDALS+v*16+ch]>=64?2+mem[NATIVE_RANDOM_EPOCH_TMP+ch]:0;
   ):st==176 && mem[b+2]==64?(
    mem[NATIVE_RANDOM_PEDALS+v*16+ch]=mem[b+3];mem[b+3]<64?mem[NATIVE_RANDOM_EPOCH_TMP+ch]+=1;
   );
  );i+=1;
 );
 i=0;loop(layer_count(p),epoch=mem[a+i];epoch>=2?(ch=mem[layer_base(p,i)+1]&15;mem[a+i]=(mem[NATIVE_RANDOM_PEDALS+v*16+ch]>=64 && epoch==2+mem[NATIVE_RANDOM_EPOCH_TMP+ch])?2:0;);i+=1;);
 );
);
function native_random_owner_begin(v,p,time) local(j,a,cfg,start,delta,code)
(
 cfg=NATIVE_RANDOM_CFG+v*8;a=NATIVE_RANDOM_STATE+v*16;start=0;delta=0;
 native_random_current>=0?(j=0;loop(8,mem[cfg+j]=mem[native_random_current+j];j+=1;);delta=mem[native_random_current+8];start=mem[native_random_current+9];):(
  memset(cfg,0,8);
 );
 memset(a,0,16);mem[a]=start;mem[a+3]=max(1,(mem[LEN_BASE+p]-start)*time);mem[a+4]=start;mem[a+6]=delta;mem[a+9]=time;
 mem[a+10]=native_direction_reversed(v,0);mem[a+11]=start;
 mem[cfg]>0 && mem[cfg+7]>0 && mem[cfg+2]==0 && mem[NATIVE_DIRECTION_VOICE+v]>=2?mem[a+11]=native_random_rebase_start(p,cfg,!mem[a+10],time,1,start);
 mem[NATIVE_VOICE_TUNE_BASE+v]+=delta;
 mem[cfg]>0?native_random_prefix_prepare(v,p,start,native_direction_reversed(v,0));
);
function native_random_voice_end(v)
(mem[NATIVE_RANDOM_CFG+v*8]>0?mem[NATIVE_RANDOM_STATE+v*16+3]:max(1,mem[LEN_BASE+mem[VOICE_LAYER_BASE+v]]*mem[VOICE_TIME_BASE+v]););
function native_random_event(v,p,i,rev) local(b,index,other,flag,start,j,a)
(
 b=native_random_view(p,i,rev);index=mem[NATIVE_REVERSE_ORDER+p*2048+(rev?layer_count(p)-1-i:i)];a=NATIVE_RANDOM_STATE+v*16;start=mem[a+4];
 j=0;loop(5,mem[NATIVE_RANDOM_EVENT+j]=mem[b+j];j+=1;);
 mem[NATIVE_RANDOM_EVENT]-=start;
 mem[NATIVE_RANDOM_EVENT]<0?(
  flag=mem[NATIVE_RANDOM_PREFIX+v*2048+index];
  (mem[b+1]&240)==144 && mem[b+3]>0?(flag>0?mem[NATIVE_RANDOM_EVENT]=0;):
  (mem[b+1]&240)==128 || ((mem[b+1]&240)==144 && mem[b+3]==0)?(
   other=mem[NATIVE_REVERSE_PAIR+p*2048+index]-1;other>=0 && mem[NATIVE_RANDOM_PREFIX+v*2048+other]==2?mem[NATIVE_RANDOM_EVENT]=0;
  );
 );NATIVE_RANDOM_EVENT;
);
function native_conductor_random_base(b) local(a)
(a=mem[b+79];a+2+mem[a]*4+3*mem[b+2];);
function native_random_variant_eligible(b) local(j,p,ok,cfg,tune,n,delta)
(ok=b>0 && mem[b]>0 && mem[b+1]==0;j=0;loop(min(12,mem[b+2]),p=mem[b+4+j*5];
 layer_count(p)<=0?ok=0;cfg=native_conductor_random_base(b)+j*8;
 mem[cfg+3]>0?(tune=mem[mem[b+79]+1+mem[mem[b+79]]*4+j];delta=mem[cfg+4];n=0;loop(mem[cfg+5]-delta+1,n+=native_random_pitch_allowed(p,tune,delta,mem[cfg+6]);delta+=1;);n==0?ok=0;);
 mem[cfg]>0 && !native_reverse_prepare(p)?ok=0;j+=1;
);ok;);
function native_random_layer_choose(si,b) local(meta,n,j,epoch,last,count,choices,pick,result,ordinal,valid)
(
 meta=mem[native_conductor_random_base(b)+mem[b+2]*8];native_random_layer_meta=meta;native_random_layer_pick=0;result=b;
 meta>0?(
  n=min(256,mem[meta+1]);epoch=mem[NATIVE_RANDOM_EPOCH+si];last=mem[meta+3]==epoch?mem[meta+2]:-1;count=0;choices=0;j=0;
  loop(n,valid=native_random_variant_eligible(mem[meta+4+j*2]);mem[NATIVE_RANDOM_ELIGIBLE+j]=valid;count+=valid;valid && mem[meta+5+j*2]!=last?choices+=1;j+=1;);
  count<=0?(result=0;native_random_error=22;):(
   choices=mem[meta]==2 && choices>0?choices:count;pick=choices>1?floor(native_random_draw()*choices):0;result=0;j=0;
   loop(n,ordinal=mem[meta+5+j*2];valid=mem[NATIVE_RANDOM_ELIGIBLE+j];
    valid && (mem[meta]!=2 || choices==count || ordinal!=last)?(pick==0?(result=mem[meta+4+j*2];native_random_layer_pick=ordinal;);pick-=1;);j+=1;
   );
  );
 );result;
);
'''

PREFIX = r'''
function native_random_prefix_emit(v,p,offs,loopSource) local(a,ch,value,old,key)
(
 a=NATIVE_RANDOM_STATE+v*16;mem[a+7]==0?(
  mem[a+7]=1;ch=0;loop(16,value=mem[NATIVE_RANDOM_PEDALS+v*16+ch];value>=64?(
   loopSource?instance_loop_dispatch(p,offs,176|ch,64,value,ch*128+64):(
    old=once_route_voice;once_route_voice=v;instance_input_key=ch*128+64;send_once_to_instruments(offs,176|ch,64,value,1);once_route_voice=old;
   );
  );ch+=1;);
 );
);
'''

VOICE_RENDER = r'''
function phrase_render_voice(vi,until,instant) local(a,p,cfg,time,budget,cycle,stop,code,start)
(
 cfg=NATIVE_RANDOM_CFG+vi*8;mem[cfg]<=0?native_random_legacy_voice(vi,until,instant):(
  a=NATIVE_RANDOM_STATE+vi*16;p=mem[VOICE_LAYER_BASE+vi];time=mem[VOICE_TIME_BASE+vi];budget=10;stop=0;
  while(budget>0 && !stop)(
   budget-=1;cycle=mem[a+1];
   instant || until>mem[a+2]?phrase_render_span(vi,min(until,mem[a+3]),instant,cycle);
   !instant && phrase_voice_repeats(vi) && until>=mem[a+3]?(
    mem[a+2]=mem[a+3];mem[a+1]+=1;mem[a+7]=0;
    mem[cfg+2]>0?(mem[a+4]=native_random_cycle_start(p,cfg,native_direction_reversed(vi,mem[a+1]),time);):(
     mem[a+4]=native_direction_reversed(vi,mem[a+1])==mem[a+10]?mem[a]:mem[a+11];
    );
    mem[a+3]=mem[a+2]+max(1,(mem[LEN_BASE+p]-mem[a+4])*time);
    native_random_prefix_prepare(vi,p,mem[a+4],native_direction_reversed(vi,mem[a+1]));
    until<=mem[a+2]?stop=1;
   ):stop=1;
  );
  instant?mem[VOICE_FIRST_BASE+vi]=1:mem[VOICE_CURSOR_BASE+vi]=until;
 );
);
'''

TRIGGER = r'''
function native_random_expected_time(p,mode) local(repeats,ratio)
(repeats=instance_independent_request?(p==instance_last_source?instance_repeat+1:0):(mode==4?0:p==last_trigger_layer?mem[REPEAT_BASE+p]+1:0);ratio=phrase_time_ratio(p);exp(max(-log(64),min(log(64),log(ratio)*repeats)))/native_phrase_rate(p););
function process_phrase_trigger(start_offset,play_only) local(p,mode,cfg,tune,time,old,localTransaction,ok,stopping)
(
 p=trigger_request;p>=0 && p<LAYERS?(
  mode=native_phrase_mode(p);stopping=mode==5 && native_phrase_active(p);
  old=native_random_current;localTransaction=!native_random_transaction;
  native_random_preplanned>0?native_random_current=NATIVE_RANDOM_PLANS+(native_random_preplanned-1)*10:(
   native_random_current=-1;cfg=NATIVE_RANDOM_SOURCE+p*8;
   !stopping && !(mode==0 && !instance_independent_request) && (mem[cfg]>0 || mem[cfg+3]>0)?(
    localTransaction?native_random_begin();time=native_random_expected_time(p,mode);tune=mem[NATIVE_PHRASE_TUNE_BASE+p];
    native_random_plan(p,mode,time,cfg,tune,mem[NATIVE_DIRECTION_SOURCE+p]==1 || (mem[NATIVE_DIRECTION_SOURCE+p]==2 && mem[NATIVE_DIRECTION_NEXT+(native_gate_switch+1)*128+p]>0),NATIVE_RANDOM_DIRECT_PLAN)?native_random_current=NATIVE_RANDOM_DIRECT_PLAN:native_random_current=-2;
   );
  );
  native_random_current==-2?(trigger_request=-1;instance_last_admitted=0;instance_error=native_random_error;instance_rejected+=1;):(
   native_random_trigger_core(start_offset,play_only);
   instance_last_admitted>0?(native_random_pitch_commit(p,native_random_current);free_play_error==p+1?free_play_error=0;localTransaction && native_random_current>=0?native_random_commit(););
  );native_random_current=old;
 );
);
'''

DIRECT_RENDER = r'''
function native_random_loop_render(p) local(v,a,cfg,time,left,cursor,position,span,i,b,at,st,d1,d2,budget,cycle,key)
(
 v=MAX_ONCE_VOICES+p;a=NATIVE_RANDOM_STATE+v*16;cfg=NATIVE_RANDOM_CFG+v*8;time=1/native_phrase_rate(p);
 left=samplesblock;cursor=0;budget=10;
 play_sample_pos<mem[FREE_LOOP_ANCHOR_BASE+p]?(cursor=min(samplesblock,mem[FREE_LOOP_ANCHOR_BASE+p]-play_sample_pos);left-=cursor;);
 while(left>0 && budget>0 && mem[TRIG_BASE+p]>.5)(budget-=1;position=play_sample_pos+cursor-mem[FREE_LOOP_ANCHOR_BASE+p];cycle=mem[a+1];
  span=min(left,max(0,mem[a+3]-position));
  span>0?(
   native_random_loop_prefix(v,p,cursor,1);
   i=0;loop(layer_count(p),b=native_random_event(v,p,i,native_direction_reversed(v,cycle));at=mem[b]*time+mem[a+2];
    mem[TRIG_BASE+p]>.5 && mem[b]>=0 && at>=position && at<position+span?(
     st=mem[b+1];d1=mem[b+2];d2=mem[b+3];key=6200000+p*2048+(st&15)*128+d1;
     (st&240)==144 && d2>0?mem[key]+=1:((st&240)==128 || ((st&240)==144 && d2==0))?mem[key]=max(0,mem[key]-1);
     (st&240)==176 && d1==64?mem[6462144+p*16+(st&15)]=d2>=64;
     (st&240)==144 && d2>0?d2=max(1,min(127,floor(d2*slider9*mem[VEL_BASE+p]+.5)));
     instance_loop_dispatch(p,cursor+at-position,st,d1,d2,(st&15)*128+d1);
    );i+=1;
   );left-=span;cursor+=span;
  );
  position+span>=mem[a+3]?(
   mem[a+2]=mem[a+3];mem[a+1]+=1;mem[a+7]=0;
   mem[cfg+2]>0?(mem[a+4]=native_random_cycle_start(p,cfg,native_direction_reversed(v,mem[a+1]),time);):mem[a+4]=native_direction_reversed(v,mem[a+1])==mem[a+10]?mem[a]:mem[a+11];
   mem[a+3]=mem[a+2]+max(1,(mem[LEN_BASE+p]-mem[a+4])*time);
   native_random_prefix_prepare(v,p,mem[a+4],native_direction_reversed(v,mem[a+1]));
  );
 );
);
'''


def extend(source):
    def change(old,new,count=1):
        nonlocal source
        if source.count(old)!=count:raise ValueError('Randomization contract changed: '+old[:110])
        source=source.replace(old,new)
    change('function instance_discard_all()',DECLARATIONS+'\nfunction instance_discard_all()')
    change('d1=max(0,min(127,d1+mem[NATIVE_VOICE_TUNE_BASE+once_route_voice]));',
           'd1=native_random_quantize(d1+mem[NATIVE_VOICE_TUNE_BASE+once_route_voice],mem[NATIVE_RANDOM_CFG+once_route_voice*8+3]>0?mem[NATIVE_RANDOM_CFG+once_route_voice*8+6]:4095,mem[NATIVE_RANDOM_STATE+once_route_voice*16+6]);')
    # Native ORIGINAL follows each instrument's MIDI OUT for pedal ownership,
    # just as it already does for note attacks. The frozen legacy source stays intact.
    change('ch=policy>0 && policy<=16?policy-1:st&15;destmask=policy==17?65535:1<<ch;',
           'ch=policy>0 && policy<=16?policy-1:native_phrase_contract>=2 && mem[engine_addr(INST_OUT_BASE,j)]>0?mem[engine_addr(INST_OUT_BASE,j)]-1:st&15;destmask=policy==17?65535:1<<ch;')

    change('function native_direction_reversed(v,cycle)',BASIC+'\nfunction native_direction_reversed(v,cycle)')
    # BASIC uses the direction helper only in owner initialization: move that one
    # definition ahead of the random helpers so EEL never resolves a forward call.
    start=source.index('function native_direction_reversed(v,cycle)')
    end=source.index('function phrase_time_addr(layer)',start)
    direction=source[start:end];source=source[:start]+source[end:]
    at=source.index('function native_random_begin()');source=source[:at]+direction+source[at:]
    change('busy=mem[NATIVE_DIRECTION_SOURCE+layer]>0;',
           'busy=mem[NATIVE_DIRECTION_SOURCE+layer]>0 || (layer_count(layer)>0 && (mem[NATIVE_RANDOM_SOURCE+layer*8]>0 || mem[NATIVE_RANDOM_SOURCE+layer*8+3]>0));')
    change('mem[NATIVE_DIRECTION_VOICE+v]>0?busy=1;',
           '(mem[NATIVE_DIRECTION_VOICE+v]>0 || mem[NATIVE_RANDOM_CFG+v*8]>0 || mem[NATIVE_RANDOM_CFG+v*8+3]>0)?busy=1;')
    change('mem[NATIVE_REVERSE_READY+layer]=0;', 'mem[NATIVE_RANDOM_STATS+layer*4]=0;mem[NATIVE_REVERSE_READY+layer]=0;',2)
    change('function process_phrase_trigger(start_offset,play_only)','function native_random_trigger_core(start_offset,play_only)')
    change('function phrase_admit_independent(layer,offs)',TRIGGER+'\nfunction phrase_admit_independent(layer,offs)')
    change('  mem[VOICE_TIME_BASE+voice_slot]=instance_time;', '  mem[VOICE_TIME_BASE+voice_slot]=instance_time;native_random_owner_begin(voice_slot,requested_layer,instance_time);')
    change('mem[NATIVE_VOICE_TUNE_BASE+v]=mem[mem[b+79]+1+mem[mem[b+79]]*4+j];',
           'mem[NATIVE_VOICE_TUNE_BASE+v]=mem[mem[b+79]+1+mem[mem[b+79]]*4+j]+mem[NATIVE_RANDOM_STATE+v*16+6];')
    # Prefix emitter for independent voices is declared before the span renderer;
    # the direct-source version is declared after its ledger dispatcher.
    voice_prefix=PREFIX.replace('native_random_prefix_emit','native_random_voice_prefix').replace('loopSource?instance_loop_dispatch(p,offs,176|ch,64,value,ch*128+64):(', '(')
    change('function phrase_render_span(vi,until,instant,cycle)',voice_prefix+'\nfunction phrase_render_span(vi,until,instant,cycle)')
    change('once_time=mem[VOICE_TIME_BASE+vi];phrase_end=max(1,mem[LEN_BASE+once_layer]*once_time);',
           'once_time=mem[VOICE_TIME_BASE+vi];phrase_end=mem[NATIVE_RANDOM_CFG+vi*8]>0?mem[NATIVE_RANDOM_STATE+vi*16+3]-mem[NATIVE_RANDOM_STATE+vi*16+2]:max(1,mem[LEN_BASE+once_layer]*once_time);mem[NATIVE_RANDOM_CFG+vi*8]>0 && (instant || until>mem[NATIVE_RANDOM_STATE+vi*16+2])?native_random_voice_prefix(vi,once_layer,max(0,mem[NATIVE_RANDOM_STATE+vi*16+2]-mem[VOICE_POS_BASE+vi]),0);')
    change('base=mem[NATIVE_DIRECTION_VOICE+vi]>0?', 'base=mem[NATIVE_RANDOM_CFG+vi*8]>0?native_random_event(vi,once_layer,i,native_direction_reversed(vi,cycle)):mem[NATIVE_DIRECTION_VOICE+vi]>0?')
    change('evt_t=relative_t+cycle*phrase_end;', 'evt_t=relative_t+(mem[NATIVE_RANDOM_CFG+vi*8]>0?mem[NATIVE_RANDOM_STATE+vi*16+2]:cycle*phrase_end);')
    change('mem[instance_header(vi)+11]>.5 && (instant?', 'relative_t>=0 && mem[instance_header(vi)+11]>.5 && (instant?')
    change('function phrase_render_voice(vi,until,instant)','function native_random_legacy_voice(vi,until,instant)')
    change('// Preserve legacy LOOP timing/velocity',VOICE_RENDER+'\n// Preserve legacy LOOP timing/velocity')
    loop_prefix=PREFIX.replace('native_random_prefix_emit','native_random_loop_prefix')
    change('function free_loop_stop_at(layer,offs)',loop_prefix+'\n'+DIRECT_RENDER+'\nfunction free_loop_stop_at(layer,offs)')
    change('mem[NATIVE_VOICE_TUNE_BASE+v]=mem[NATIVE_PHRASE_TUNE_BASE+layer];',
           'mem[NATIVE_VOICE_TUNE_BASE+v]=mem[NATIVE_PHRASE_TUNE_BASE+layer]+mem[NATIVE_RANDOM_STATE+v*16+6];')
    # All generated direct LOOP paths pass through this guarded wrapper.
    change('function phrase_loop_source_trigger(layer,offs)','function native_random_loop_core(layer,offs)')
    change('function native_hold_can_play(layer)',r'''function phrase_loop_source_trigger(layer,offs) local(cfg,old,ok,v)
    (cfg=NATIVE_RANDOM_SOURCE+layer*8;old=native_random_current;v=MAX_ONCE_VOICES+layer;
     mem[TRIG_BASE+layer]>.5 || (mem[cfg]<=0 && mem[cfg+3]<=0)?native_random_loop_core(layer,offs):(
      native_random_begin();ok=native_random_plan(layer,0,1/native_phrase_rate(layer),cfg,mem[NATIVE_PHRASE_TUNE_BASE+layer],mem[NATIVE_DIRECTION_SOURCE+layer]==1,NATIVE_RANDOM_DIRECT_PLAN);
      ok?(native_random_current=NATIVE_RANDOM_DIRECT_PLAN;mem[NATIVE_DIRECTION_VOICE+v]=mem[NATIVE_DIRECTION_SOURCE+layer];native_random_owner_begin(v,layer,1/native_phrase_rate(layer));native_random_loop_core(layer,offs);mem[TRIG_BASE+layer]>.5?(native_random_pitch_commit(layer,native_random_current);free_play_error==layer+1?free_play_error=0;native_random_commit(););):(
       instance_error=native_random_error;instance_rejected+=1;free_play_error=layer+1;
      );native_random_current=old;
     );
    );
    function native_hold_can_play(layer)''')
    change('layer_audible(fl) && mem[MODE_BASE+fl]<.5 && mem[TRIG_BASE+fl]>.5 ? (',
           'layer_audible(fl) && mem[MODE_BASE+fl]<.5 && mem[TRIG_BASE+fl]>.5 ? (mem[NATIVE_RANDOM_CFG+(MAX_ONCE_VOICES+fl)*8]>0?native_random_loop_render(fl):(')
    change('    );fl+=1;\n  );play_sample_pos+=samplesblock;', '    ));fl+=1;\n  );play_sample_pos+=samplesblock;')
    change('mem[VOICE_POS_BASE+vi]>=max(1,mem[LEN_BASE+mem[VOICE_LAYER_BASE+vi]]*mem[VOICE_TIME_BASE+vi])',
           'mem[VOICE_POS_BASE+vi]>=native_random_voice_end(vi)')
    change('period=max(1,mem[LEN_BASE+mem[VOICE_LAYER_BASE+v]]*mem[VOICE_TIME_BASE+v]);pos=',
           'period=native_random_voice_end(v);pos=')
    change('phrase_voice_repeats(v)?(mem[g+4]=(floor(max(0,pos)/period)+1)*period;wait=1;)',
           'phrase_voice_repeats(v)?(mem[NATIVE_RANDOM_CFG+v*8]>0?(phrase_render_voice(v,pos,0);mem[g+4]=native_random_voice_end(v);):mem[g+4]=(floor(max(0,pos)/period)+1)*period;wait=1;)')
    # Conductor selection and phrase planning share one random transaction.
    change('chargeMask)\n(\n h=conductor_header(si);',
           'chargeMask,randomMeta,randomLayer,randomBase,randomCfg,randomTune,randomRev)\n(\n native_random_begin();native_random_transaction=1;randomMeta=0;randomLayer=0;h=conductor_header(si);')
    change('b<=0 || !mem[b] ? mem[h+4]=',
           '!phase?(b=native_random_layer_choose(si,b);randomMeta=native_random_layer_meta;randomLayer=native_random_layer_pick;);b<=0 || !mem[b] ? mem[h+4]=')
    change('!(mode==5 && native_phrase_active(p))?n+=1;',
           '!(mode==5 && native_phrase_active(p))?(randomCfg=native_conductor_random_base(b)+j*8;randomTune=mem[mem[b+79]+1+mem[mem[b+79]]*4+j];randomRev=native_conductor_direction(b,j)==1 || (native_conductor_direction(b,j)==2 && mem[NATIVE_DIRECTION_NEXT+(si+1)*128+p]>0);!native_random_plan(p,mode,t,randomCfg,randomTune,randomRev,NATIVE_RANDOM_PLANS+j*10)?valid=0;n+=1;);')
    change('id=phrase_admit_independent(p,offs);', 'native_random_preplanned=j+1;id=phrase_admit_independent(p,offs);native_random_preplanned=0;')
    # Only this exact result write closes conductor_apply, not gesture helpers.
    change(' mem[sw_rt(si)+17]=mem[h+4];\n);',r''' native_random_error>0 && (mem[h+4]==3 || mem[h+4]==4)?mem[h+4]=native_random_error;
 mem[h+4]<=1?(
  native_random_commit();!phase?(mem[NATIVE_RANDOM_LAYER+si]=randomLayer;
   randomMeta>0?(mem[randomMeta+2]=randomLayer;mem[randomMeta+3]=mem[NATIVE_RANDOM_EPOCH+si];);
  );
 );native_random_transaction=0;native_random_preplanned=0;
 mem[sw_rt(si)+17]=mem[h+4];
);''')
    change('memset(NATIVE_DIRECTION_NEXT+(si+1)*128,0,128);',
           'mem[NATIVE_RANDOM_LAYER+si]=0;mem[NATIVE_RANDOM_EPOCH+si]+=1;memset(NATIVE_DIRECTION_NEXT+(si+1)*128,0,128);')
    change('memset(NATIVE_DIRECTION_NEXT,0,65*128);',
           'native_random_error=0;memset(NATIVE_RANDOM_PITCH_READY,0,128);memset(NATIVE_RANDOM_CFG,0,140*8);memset(NATIVE_RANDOM_STATE,0,140*16);memset(NATIVE_RANDOM_LAYER,0,64);v=0;loop(64,mem[NATIVE_RANDOM_EPOCH+v]+=1;v+=1;);memset(NATIVE_DIRECTION_NEXT,0,65*128);')
    change('native_phrase_contract?(gi=0;loop(SW_COUNT,mem[CONDUCTOR_GESTURE_BASE+gi*8]=0;',
           'native_phrase_contract?(native_random_error=0;memset(NATIVE_RANDOM_PITCH_READY,0,128);memset(NATIVE_DIRECTION_NEXT,0,65*128);gi=0;loop(SW_COUNT,mem[NATIVE_RANDOM_LAYER+gi]=0;mem[NATIVE_RANDOM_EPOCH+gi]+=1;mem[CONDUCTOR_GESTURE_BASE+gi*8]=0;')
    return source
