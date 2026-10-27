"""Native ingress gate, after exclusive learn / command dispatch.

Input buses identify physical ingress slots. Every musical output returns to bus
zero so ingress identity never collides with the ECHOCITY output journal.
This extension is deliberately separate from the frozen REAPER source.
"""

EEL = r'''
NATIVE_THRU_MODE_BASE=29400000;
NATIVE_THRU_HELD_BASE=29400256;
NATIVE_THRU_TOTAL_BASE=29433024;
NATIVE_THRU_STALE_BASE=29435072;
NATIVE_THRU_SUSTAIN_BASE=29467840;
NATIVE_THRU_CLOSE_BASE=29468096;
NATIVE_THRU_HEAD_BASE=29468352;
ext_midi_bus=1;native_thru_available=1;native_thru_enabled=0;
native_thru_reset_pending=0;native_thru_close_pending=0;
native_thru_slot=0;native_thru_mode=1;native_thru_stale_until=0;
nt_init=0;loop(256,mem[NATIVE_THRU_MODE_BASE+nt_init]=1;nt_init+=1;);
memset(NATIVE_THRU_HELD_BASE,0,32768);
memset(NATIVE_THRU_TOTAL_BASE,0,2048);
memset(NATIVE_THRU_STALE_BASE,0,32768);
memset(NATIVE_THRU_SUSTAIN_BASE,0,256);
memset(NATIVE_THRU_CLOSE_BASE,0,256);

// Merge one lookahead event per physical bus by sample offset. Draining each
// bus in turn would reorder a pedal release relative to another keyboard.
function native_thru_begin()
local(slot,at,offs,st,data)
(
 slot=0;loop(native_thru_enabled?16:1,
  at=NATIVE_THRU_HEAD_BASE+slot*4;midi_bus=slot;
  mem[at]=midirecv(offs,st,data);
  mem[at+1]=offs;mem[at+2]=st;mem[at+3]=data;slot+=1;
 );midi_bus=0;
);
function native_thru_next()
local(slot,at,best,best_offset,offs,st,data)
(
 best=-1;best_offset=samplesblock+1;slot=0;
 loop(native_thru_enabled?16:1,
  at=NATIVE_THRU_HEAD_BASE+slot*4;
  mem[at]>0 && mem[at+1]<best_offset?(
   best=slot;best_offset=mem[at+1];
  );slot+=1;
 );
 best>=0?(
  at=NATIVE_THRU_HEAD_BASE+best*4;
  offset=mem[at+1];msg1=mem[at+2];msg23=mem[at+3];
  midi_bus=best;mem[at]=midirecv(offs,st,data);
  mem[at+1]=offs;mem[at+2]=st;mem[at+3]=data;
  1;
 ):0;
);

function native_thru_reset()
(
 memcpy(NATIVE_THRU_STALE_BASE,NATIVE_THRU_HELD_BASE,32768);
 memset(NATIVE_THRU_HELD_BASE,0,32768);
 memset(NATIVE_THRU_TOTAL_BASE,0,2048);
 memset(NATIVE_THRU_SUSTAIN_BASE,0,256);
 native_thru_stale_until=sw_clock+10*srate;
);
function native_thru_route(offs,st,num,value,slot)
local(kind,ch,key,index,release,forward,j,pedal)
(
 !native_thru_enabled ? (
  send_to_instruments(offs,st,num,value,1);i_release_mask=0;
 ) : (
 kind=st&240;ch=st&15;key=ch*128+num;
 index=slot*2048+key;forward=1;
 release=kind==128 || (kind==144 && value==0);
 kind==144 && value>0 ? (
  // Equal notes from two devices share the live voice until both release.
  forward=mem[NATIVE_THRU_TOTAL_BASE+key]<=0;
  mem[NATIVE_THRU_HELD_BASE+index]<=0 ? (
   mem[NATIVE_THRU_HELD_BASE+index]=1;
   mem[NATIVE_THRU_TOTAL_BASE+key]+=1;
  );
 ) : release ? (
  forward=0;
  sw_clock+offs<native_thru_stale_until && mem[NATIVE_THRU_STALE_BASE+index]>0 ? (
   mem[NATIVE_THRU_STALE_BASE+index]-=1;
  ) : mem[NATIVE_THRU_HELD_BASE+index]>0 ? (
   mem[NATIVE_THRU_HELD_BASE+index]=0;
   mem[NATIVE_THRU_TOTAL_BASE+key]=max(0,mem[NATIVE_THRU_TOTAL_BASE+key]-1);
   forward=mem[NATIVE_THRU_TOTAL_BASE+key]<=0;
  );
 ) : kind==176 && num==64 ? (
  mem[NATIVE_THRU_SUSTAIN_BASE+slot*16+ch]=value;
  pedal=0;j=0;loop(16,pedal=max(pedal,mem[NATIVE_THRU_SUSTAIN_BASE+j*16+ch]);j+=1;);
  value=pedal;
 );
 forward ? (
  i_release_mask=i_capture_release(st,num,value);
  send_to_instruments(offs,st,num,value,1);
  i_release_mask=0;
 );
 );
);
function native_thru_close(slot,ch,offs)
local(note,index,key,j,pedal)
(
 note=0;loop(128,
  key=ch*128+note;index=slot*2048+key;
  mem[NATIVE_THRU_HELD_BASE+index]>0 ? (
   mem[NATIVE_THRU_HELD_BASE+index]=0;
   mem[NATIVE_THRU_STALE_BASE+index]=1;
   mem[NATIVE_THRU_TOTAL_BASE+key]=max(0,mem[NATIVE_THRU_TOTAL_BASE+key]-1);
   mem[NATIVE_THRU_TOTAL_BASE+key]<=0 ? (
    i_release_mask=i_capture_release(128|ch,note,0);
    send_to_instruments(offs,128|ch,note,0,1);i_release_mask=0;
   );
  );note+=1;
 );
 native_thru_stale_until=sw_clock+10*srate;
 mem[NATIVE_THRU_SUSTAIN_BASE+slot*16+ch]>0 ? (
  mem[NATIVE_THRU_SUSTAIN_BASE+slot*16+ch]=0;
  pedal=0;j=0;loop(16,pedal=max(pedal,mem[NATIVE_THRU_SUSTAIN_BASE+j*16+ch]);j+=1;);
  send_to_instruments(offs,176|ch,64,pedal,1);
 );
);
'''


def extend(source):
    def change(old, new):
        nonlocal source
        if source.count(old) != 1:
            raise ValueError('Native MIDI THRU source contract changed: '+old[:80])
        source = source.replace(old, new)

    # Initialize once in @init, never once per DSP block. Move the existing
    # release helper before the gate so every EEL function is defined before use.
    release = '''function i_capture_release(st,note,value)
local(gi,idx,mask)
(mask=0;(st&240)==128 || ((st&240)==144 && value==0)?(
 gi=0;loop(INST_CAP,idx=I_QUARANTINE_BASE+(gi*16+(st&15))*128+note;
 mem[idx]>0?(mem[idx]-=1;mask|=1<<gi;);gi+=1;););mask;);
'''
    change(release, '')
    change('function sw_input(st,num,value,offs)',
           release+'\n'+EEL+'\nfunction sw_input(st,num,value,offs)')
    change('function reset_note_runtime()\nlocal(pv_i)\n(',
           'function reset_note_runtime()\nlocal(pv_i)\n(\n native_thru_reset_pending=1;')
    # midirecv selects its input bus; merge their lookahead events by timestamp.
    change('while (\n  midirecv(offset,msg1,msg23) ?',
           'native_thru_reset_pending?(native_thru_reset();native_thru_reset_pending=0;);\n'
           'native_thru_close_pending?(nt_close=0;loop(256,\n'
           ' mem[NATIVE_THRU_CLOSE_BASE+nt_close]>0?('
           'native_thru_close(floor(nt_close/16),nt_close%16,0);'
           'mem[NATIVE_THRU_CLOSE_BASE+nt_close]=0;);nt_close+=1;);'
           'native_thru_close_pending=0;);\n'
           'native_thru_begin();\nwhile (\n  native_thru_next() ?')
    change('    status=msg1&240;\n    d1=msg23&127;',
           '    native_thru_slot=max(0,min(15,floor(midi_bus)));midi_bus=0;\n'
           '    native_thru_mode=native_thru_enabled?mem[NATIVE_THRU_MODE_BASE+native_thru_slot*16+(msg1&15)]:1;\n'
           '    status=msg1&240;\n    d1=msg23&127;')
    change('is_note_on=(status==144 && d2>0);i_release_mask=i_capture_release(msg1,d1,d2);',
           'is_note_on=(status==144 && d2>0);i_release_mask=native_thru_enabled?0:i_capture_release(msg1,d1,d2);')
    # Exclusive Learn / stale releases (matched == -2) never leak, even in ALL.
    change('matched!=-1 ? (thru>0 ? send_to_instruments(offs,st,num,value,1);1;) : 0;',
           'matched!=-1 ? (matched>=0 && (native_thru_enabled?native_thru_mode==2:thru>0) ? '
           'native_thru_route(offs,st,num,value,native_thru_slot);1;) : 0;')
    change('    !is_trigger_command ? (\n    (state==STATE_READY',
           '    !is_trigger_command && native_thru_mode>0 ? (\n    (state==STATE_READY')
    change('!is_trigger_command ? send_to_instruments(offset,msg1,d1,d2,1);',
           '(native_thru_mode==2 || (native_thru_mode==1 && !is_trigger_command)) ? '
           'native_thru_route(offset,msg1,d1,d2,native_thru_slot);')
    change('i_release_mask=0;\nsw_poll',
           'midi_bus=0;i_release_mask=0;native_thru_mode=1;native_thru_slot=0;\nsw_poll')
    return source
