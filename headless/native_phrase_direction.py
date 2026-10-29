"""Native non-destructive direction, with bounded cached FIFO note pairing."""
HELPERS = r'''
function native_reverse_prepare(p) local(i,b,st,key,head,tail,prev,ok,cache)
(
 mem[NATIVE_REVERSE_READY+p]==0?(
  memset(NATIVE_REVERSE_HEAD,0,2048);memset(NATIVE_REVERSE_TAIL,0,2048);
  memset(NATIVE_REVERSE_NEXT,0,2048);memset(NATIVE_REVERSE_PEDAL,0,16);
  cache=NATIVE_REVERSE_PAIR+p*2048;memset(cache,0,2048);i=0;ok=mem[LEN_BASE+p]>0;
  loop(layer_count(p),b=layer_base(p,i);st=mem[b+1]&240;key=(mem[b+1]&15)*128+mem[b+2];
   st==144 && mem[b+3]>0?(
    tail=mem[NATIVE_REVERSE_TAIL+key];tail>0?mem[NATIVE_REVERSE_NEXT+tail-1]=i+1:mem[NATIVE_REVERSE_HEAD+key]=i+1;
    mem[NATIVE_REVERSE_TAIL+key]=i+1;
   ):st==128 || (st==144 && mem[b+3]==0)?(
    head=mem[NATIVE_REVERSE_HEAD+key];head>0?(
     mem[cache+i]=head;mem[cache+head-1]=i+1;mem[NATIVE_REVERSE_HEAD+key]=mem[NATIVE_REVERSE_NEXT+head-1];
     mem[NATIVE_REVERSE_HEAD+key]==0?mem[NATIVE_REVERSE_TAIL+key]=0;
    ):ok=0;
   ):st==176 && mem[b+2]==64?(
    key=mem[b+1]&15;prev=mem[NATIVE_REVERSE_PEDAL+key];mem[cache+i]=-prev-1;mem[NATIVE_REVERSE_PEDAL+key]=mem[b+3];
   );i+=1;
  );
  i=0;loop(2048,mem[NATIVE_REVERSE_HEAD+i]>0?ok=0;i+=1;);
  i=0;loop(16,mem[NATIVE_REVERSE_PEDAL+i]>=64?ok=0;i+=1;);
  mem[NATIVE_REVERSE_READY+p]=ok?1:-1;
 );mem[NATIVE_REVERSE_READY+p]>0;
);
function native_direction_event(p,i,rev) local(b,other,st,j)
(
 rev?(
  i=layer_count(p)-1-i;b=layer_base(p,i);other=mem[NATIVE_REVERSE_PAIR+p*2048+i];st=mem[b+1]&240;
  mem[NATIVE_REVERSE_EVENT]=max(0,mem[LEN_BASE+p]-1-mem[b]);j=1;loop(4,mem[NATIVE_REVERSE_EVENT+j]=mem[b+j];j+=1;);
  st==144 && mem[b+3]>0?(
   mem[NATIVE_REVERSE_EVENT+1]=128|(mem[b+1]&15);mem[NATIVE_REVERSE_EVENT+3]=mem[layer_base(p,other-1)+3];
  ):st==128 || (st==144 && mem[b+3]==0)?(
   mem[NATIVE_REVERSE_EVENT+1]=144|(mem[b+1]&15);mem[NATIVE_REVERSE_EVENT+3]=mem[layer_base(p,other-1)+3];
  ):st==176 && mem[b+2]==64?mem[NATIVE_REVERSE_EVENT+3]=-other-1;
  NATIVE_REVERSE_EVENT;
 ):layer_base(p,i);
);
function native_direction_reversed(v,cycle) local(d)
(d=mem[NATIVE_DIRECTION_VOICE+v];d>=2?(d-2+cycle)%2:d==1;);
'''

WRAPPER = r'''
function process_phrase_trigger(start_offset,play_only) local(p,d,mode,ctx,parity,before,oldcode)
(
 p=trigger_request;p>=0 && p<LAYERS?(
  d=mem[NATIVE_DIRECTION_SOURCE+p];mode=native_phrase_mode(p);ctx=(native_gate_switch+1)*LAYERS+p;
  parity=mem[NATIVE_DIRECTION_NEXT+ctx];before=mem[TRIG_BASE+p];
  (mode==2 && d==2) || (d>0 && !((mode==5 && native_phrase_active(p)) || (mode==0 && before>0 && !instance_independent_request)) && !native_reverse_prepare(p))?(
   trigger_request=-1;instance_last_admitted=0;instance_error=3;instance_rejected+=1;
  ):(
   oldcode=native_direction_current;native_direction_current=d==2?2+parity:d;
   instance_last_admitted=0;native_direction_trigger_core(start_offset,play_only);
   instance_last_admitted>0 || (!before && mem[TRIG_BASE+p]>0)?mem[NATIVE_DIRECTION_NEXT+ctx]=d==2?1-parity:0;
   mode==5 && !native_phrase_active(p)?mem[NATIVE_DIRECTION_NEXT+ctx]=0;
   mode==0 && before && mem[TRIG_BASE+p]==0?mem[NATIVE_DIRECTION_NEXT+ctx]=0;
   native_direction_current=oldcode;
  );
 );
);
'''

def extend(source):
    def change(old,new,count=1):
        nonlocal source
        if source.count(old)!=count:raise ValueError('Native direction contract changed: '+old[:90])
        source=source.replace(old,new)
    change('function instance_discard_all()', '''NATIVE_DIRECTION_SOURCE=CONDUCTOR_BASE-30000;
NATIVE_DIRECTION_VOICE=NATIVE_DIRECTION_SOURCE+128;
NATIVE_DIRECTION_NEXT=NATIVE_DIRECTION_VOICE+140;
NATIVE_REVERSE_READY=NATIVE_DIRECTION_NEXT+65*128;
NATIVE_REVERSE_PAIR=28000000;NATIVE_REVERSE_HEAD=NATIVE_REVERSE_PAIR+128*2048;
NATIVE_REVERSE_TAIL=NATIVE_REVERSE_HEAD+2048;NATIVE_REVERSE_NEXT=NATIVE_REVERSE_TAIL+2048;
NATIVE_REVERSE_PEDAL=NATIVE_REVERSE_NEXT+2048;NATIVE_REVERSE_EVENT=NATIVE_REVERSE_PEDAL+16;
NATIVE_REVERSE_END=NATIVE_REVERSE_EVENT+8;native_direction_enabled=1;
function instance_discard_all()''')
    change('function phrase_time_addr(layer)', HELPERS+'\nfunction phrase_time_addr(layer)')
    change('  set_layer_count(layer,0);','  mem[NATIVE_REVERSE_READY+layer]=0;set_layer_count(layer,0);')
    change('  count=layer_count(layer);\n  count < MAX_EVENTS_PER_LAYER',
           '  mem[NATIVE_REVERSE_READY+layer]=0;count=layer_count(layer);\n  count < MAX_EVENTS_PER_LAYER')
    change('function instance_discard_all() local(v,h)\n(',
           'function instance_discard_all() local(v,h)\n(\n memset(NATIVE_DIRECTION_NEXT,0,65*128);')
    change('(mem[CONDUCTOR_GESTURE_BASE+si*8+3]=0;',
           '(memset(NATIVE_DIRECTION_NEXT+(si+1)*128,0,128);mem[CONDUCTOR_GESTURE_BASE+si*8+3]=0;')
    change('function process_phrase_trigger(start_offset,play_only)', 'function native_direction_trigger_core(start_offset,play_only)')
    change('function phrase_admit_independent(layer,offs)',WRAPPER+'\nfunction phrase_admit_independent(layer,offs)')
    change('function phrase_loop_source_trigger(layer,offs)', 'function native_direction_loop_core(layer,offs)')
    change('function native_hold_can_play(layer)', r'''function phrase_loop_source_trigger(layer,offs)
    (mem[TRIG_BASE+layer]>.5 || mem[NATIVE_DIRECTION_SOURCE+layer]==0 || native_reverse_prepare(layer)?native_direction_loop_core(layer,offs):(instance_error=3;instance_rejected+=1;free_play_error=layer+1;););
    function native_hold_can_play(layer)''')
    change('function select_phrase_record(layer)', 'function native_direction_record_core(layer)')
    change('function phrase_playing(layer)', r'''function select_phrase_record(layer)
    (mem[NATIVE_DIRECTION_SOURCE+layer]>0 && layer_count(layer)>0?(free_play_error=layer+1;):(native_direction_record_core(layer);););
    function phrase_playing(layer)''')

    change('mem[NATIVE_VOICE_TUNE_BASE+voice_slot]=', 'mem[NATIVE_DIRECTION_VOICE+voice_slot]=native_direction_current;mem[NATIVE_VOICE_TUNE_BASE+voice_slot]=')
    change('mem[NATIVE_VOICE_TUNE_BASE+v]=mem[NATIVE_PHRASE_TUNE_BASE+layer];',
           'mem[NATIVE_DIRECTION_VOICE+v]=mem[NATIVE_DIRECTION_SOURCE+layer]==2?2:mem[NATIVE_DIRECTION_SOURCE+layer];mem[NATIVE_VOICE_TUNE_BASE+v]=mem[NATIVE_PHRASE_TUNE_BASE+layer];')
    change('base=layer_base(once_layer,i);relative_t=',
           'base=native_direction_event(once_layer,i,native_direction_reversed(vi,cycle));relative_t=')
    change('loop(count,b=layer_base(fl,j);at=playback_rate==1?',
           'loop(count,b=native_direction_event(fl,j,native_direction_reversed(MAX_ONCE_VOICES+fl,floor((play_sample_pos-mem[FREE_LOOP_ANCHOR_BASE+fl]+cursor)/period)));at=playback_rate==1?')
    # A direct LOOP may not have created its ledger owner before its first event.
    change('position<0?position+=period;left=samplesblock;cursor=0;',
           'position<0?position+=period;left=samplesblock;cursor=0;mem[NATIVE_DIRECTION_SOURCE+fl]>0 && play_sample_pos<mem[FREE_LOOP_ANCHOR_BASE+fl]?(cursor=min(samplesblock,mem[FREE_LOOP_ANCHOR_BASE+fl]-play_sample_pos);left-=cursor;position=0;);')
    change('playback_rate=native_phrase_rate(fl);period=native_phrase_period(fl);',
           'mem[NATIVE_DIRECTION_VOICE+MAX_ONCE_VOICES+fl]=mem[NATIVE_DIRECTION_SOURCE+fl];playback_rate=native_phrase_rate(fl);period=native_phrase_period(fl);')
    # Encode PING_PONG as 2 (forward first), not REVERSE's 1.
    change('mem[NATIVE_DIRECTION_VOICE+MAX_ONCE_VOICES+fl]=mem[NATIVE_DIRECTION_SOURCE+fl];',
           'mem[NATIVE_DIRECTION_VOICE+MAX_ONCE_VOICES+fl]=mem[NATIVE_DIRECTION_SOURCE+fl];')
    change('function native_conductor_rate(b,j)', '''function native_conductor_direction(b,j)
(mem[mem[b+79]+2+mem[mem[b+79]]*4+2*mem[b+2]+j];);
function native_conductor_rate(b,j)''')
    change('((mode==0 || mode==2) && mem[LEN_BASE+p]*t<max(128,samplesblock/8)) || (mode==3 && phase>=3)?valid=0;',
           '((mode==0 || mode==2) && mem[LEN_BASE+p]*t<max(128,samplesblock/8)) || (mode==3 && phase>=3) || (mode==2 && native_conductor_direction(b,j)==2) || (native_conductor_direction(b,j)>0 && !native_reverse_prepare(p))?valid=0;')
    change('native_old_play_mode,id,owner','native_old_play_mode,native_old_direction,id,owner')
    change('      native_old_play_mode=mem[NATIVE_PHRASE_PLAY_MODE_BASE+p];',
           '      native_old_direction=mem[NATIVE_DIRECTION_SOURCE+p];mem[NATIVE_DIRECTION_SOURCE+p]=mem[mem[b+79]+2+mem[mem[b+79]]*4+2*mem[b+2]+j];native_old_play_mode=mem[NATIVE_PHRASE_PLAY_MODE_BASE+p];')
    change('native_gate_switch=-1;mem[NATIVE_PHRASE_PLAY_MODE_BASE+p]=native_old_play_mode;',
           'native_gate_switch=-1;mem[NATIVE_DIRECTION_SOURCE+p]=native_old_direction;mem[NATIVE_PHRASE_PLAY_MODE_BASE+p]=native_old_play_mode;')
    return source
