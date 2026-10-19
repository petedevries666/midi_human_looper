"""Native-only source journal. Disabled until a host explicitly subscribes.

This observes logical POLY/MONO edges before final output coalescing. It does
not replace note routing, change velocity, or claim an arbitrary continuation.
The ARP input chord is deliberately excluded: it is not an emitted arp note.
"""
EEL = r'''
NATIVE_ECHO_SOURCE_BASE=29000000;NATIVE_ECHO_SOURCE_CAP=1024;
native_echo_sources=0;native_echo_read=0;native_echo_write=0;native_echo_overflow=0;native_echo_finish=0;native_echo_reset_offset=0;
function native_echo_event(kind,instrument,instance,ch,note,velocity,origin,offs)
local(b)
(
 native_echo_sources && (kind!=4 || instrument>0) && ((kind!=3 && kind!=7) || instance>0)?(
  native_echo_write-native_echo_read<NATIVE_ECHO_SOURCE_CAP?(
   b=NATIVE_ECHO_SOURCE_BASE+(native_echo_write%NATIVE_ECHO_SOURCE_CAP)*6;
   mem[b]=kind;mem[b+1]=instrument;mem[b+2]=instance;
   mem[b+3]=(ch&15)+((note&127)*16)+((velocity&127)*2048);
   mem[b+4]=origin;mem[b+5]=instance_output_open?max(0,min(samplesblock-1,floor(offs))):0;
   native_echo_write+=1;
  ):native_echo_overflow+=1;
 );
);
'''


def extend(source):
    def change(old, new):
        nonlocal source
        if source.count(old) != 1:
            raise ValueError('Native echo source contract changed: '+old[:80])
        source = source.replace(old, new)

    change('function i_clear_runtime(gi)', EEL+'\nfunction i_clear_runtime(gi)')
    # Reset/deletion can occur outside DSP: the journal survives until the next
    # block drain, unlike midisend_buf outside the DSP context.
    change('function i_clear_runtime(gi)\nlocal(j,idx,v)\n(',
           'function i_clear_runtime(gi)\nlocal(j,idx,v)\n(native_echo_event(4,mem[I_IDS_BASE+gi],0,0,0,0,0,native_echo_reset_offset);')
    change('function reset_note_runtime()\nlocal(pv_i)\n(',
           'function reset_note_runtime()\nlocal(pv_i)\n(\n native_echo_event(5,0,0,0,0,0,0,native_echo_reset_offset);')
    change('reset_note_runtime();ch=0;loop(16,',
           'native_echo_reset_offset=offs;reset_note_runtime();native_echo_reset_offset=0;ch=0;loop(16,')
    change('local(ch,key,origin,idx)\n(\n  ch=outst&15;origin=',
           'local(ch,key,origin,idx,echo_voice,echo_id)\n(\n  ch=outst&15;origin=')
    change('idx=(gi*16+ch)*128+note;\n  !(mem[engine_addr(INST_ARP_ENABLED_BASE,gi)]>.5',
           '''idx=(gi*16+ch)*128+note;
  !(mem[engine_addr(INST_ARP_ENABLED_BASE,gi)]>.5 && transformer_on(gi,5))?(
   echo_voice=owned?once_route_voice:native_transform_voice;
   echo_id=origin && echo_voice>=0?mem[instance_header(echo_voice)]:0;
   native_echo_event(is_on?1:2,mem[I_IDS_BASE+gi],echo_id,ch,note,is_on?vel:0,origin,offs);
  );
  !(mem[engine_addr(INST_ARP_ENABLED_BASE,gi)]>.5''')
    # Owned POLY releases use their saved output record, bypassing route_emit_note.
    change('mem[NOTE_REF_BASE+idx]=max(0,mem[NOTE_REF_BASE+idx]-1);\n     instrument_output_owners',
           '''mem[NOTE_REF_BASE+idx]=max(0,mem[NOTE_REF_BASE+idx]-1);
     j<INST_CAP?native_echo_event(2,id,mem[h],ch,note,0,1,offs);
     instrument_output_owners''')
    change('reveal_end(v,offs);mem[h+1]+=1;',
           'native_echo_event(native_echo_finish?7:3,0,mem[h],0,0,0,1,offs);reveal_end(v,offs);mem[h+1]+=1;')
    # Natural phrase completion closes held gates but must not kill echo tails.
    change('?instance_stop_voice(vi,samplesblock-1);',
           '?(native_echo_finish=1;instance_stop_voice(vi,samplesblock-1);native_echo_finish=0;);')
    change('!phrase_voice_repeats(conductor_qv)?instance_stop_voice(conductor_qv,conductor_qoffs);',
           '!phrase_voice_repeats(conductor_qv)?(native_echo_finish=1;instance_stop_voice(conductor_qv,conductor_qoffs);native_echo_finish=0;);')
    change('state==STATE_PLAYING ? state=STATE_STOPPED;\n);\n// Optional native',
           'state==STATE_PLAYING ? state=STATE_STOPPED;\n native_echo_event(6,0,0,0,0,0,1,native_stop_offset);\n);\n// Optional native')
    return source
