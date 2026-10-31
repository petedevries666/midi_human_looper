"""Targeted echo ingress, merged with physical input without entering Learn/REC.

Host handoff is one audio block. The original native ARP advances exactly once.
No frozen REAPER source or second VM is used.
"""
STATE=r'''
NATIVE_DEST_QUEUE=29060000;NATIVE_DEST_LEASE=29065000;
NATIVE_DEST_MONO=29068000;NATIVE_DEST_ARP=29069024;NATIVE_DEST_MONO_ORIGIN=29070048;
NATIVE_DEST_ARP_SOURCE=29086432;
native_destination_available=1;native_destination_count=0;native_destination_read=0;
native_destination_context=0;native_destination_mono_depth=0;native_destination_physical_ready=0;native_destination_epoch=0;
function native_destination_origin(gi,ch,note,is_on,origin) local(idx,total,result)
(
 result=native_destination_context?2:origin;
 native_destination_mono_depth>0?(
  idx=NATIVE_DEST_MONO_ORIGIN+(gi*16+ch)*128+note;
  is_on?(
   total=mem[engine_addr(MONO_HELD_COUNT_BASE,gi*128+note)];
   result=total>0 && mem[NATIVE_DEST_MONO+gi*128+note]>=total?2:origin;
   mem[idx]=result;
  ):result=mem[idx];
 );result;
);
function native_destination_arp_origin(gi,note,origin) local(total,result)
(
 total=mem[engine_addr(ARP_HELD_COUNT_BASE,gi*128+note)];result=origin;
 total>0 && mem[NATIVE_DEST_ARP+gi*128+note]>=total?result=2;
 mem[engine_addr(INST_NOTE_MODE_BASE,gi)]>0?(
  total=mem[engine_addr(MONO_HELD_COUNT_BASE,gi*128+note)];
  total>0 && mem[NATIVE_DEST_MONO+gi*128+note]>=total?result=2;
 );result;
);
'''
RECEIVE=r'''
function native_destination_receive(q) local(b,slot,generation,id,ch,note,vel,on,offs,row,gi,j,found,tn,mode,sv,sp,sc)
(
 b=NATIVE_DEST_QUEUE+q*9;slot=mem[b];generation=mem[b+1];id=mem[b+2];
 ch=mem[b+3];note=mem[b+4];vel=mem[b+5];on=mem[b+6];offs=mem[b+7];
 slot>=0 && slot<256 && generation>0 && id>0 && ch>=0 && ch<16 && note>=0 && note<128 && offs>=0 && offs<samplesblock?(
  row=NATIVE_DEST_LEASE+slot*8;
  sv=native_transform_voice;sp=sw_playback_origin;sc=native_destination_context;
  native_transform_voice=-1;sw_playback_origin=0;native_destination_context=1;midi_bus=0;
  on?(
   found=0;gi=-1;j=0;loop(INST_CAP,
    mem[I_EXISTS_BASE+j] && mem[engine_addr(INST_ENABLED_BASE,j)]>.5 && mem[engine_addr(INST_OUT_BASE,j)]==ch+1?(
     found+=1;mem[I_IDS_BASE+j]==id?gi=j;
    );j+=1;
   );
   found==1 && gi>=0 && !mem[row+7]?(
    tn=tf_pitch(gi,note);mode=transformer_on(gi,3)?floor(mem[engine_addr(INST_NOTE_MODE_BASE,gi)]+.5):0;
    mem[row]=generation;mem[row+1]=id;mem[row+2]=gi;mem[row+3]=ch;mem[row+4]=tn;mem[row+5]=mode;mem[row+6]=note;mem[row+7]=1;
    param_track_input(gi,ch,note,1,0);
    tn>=0 && tn<=127?(
     vel=tf_velocity(gi,vel,1);
     mode>0?(
      mem[NATIVE_DEST_MONO+gi*128+tn]+=1;route_mono_note(gi,offs,144|ch,tn,vel,1,0);
     ):route_emit_note(gi,offs,144|ch,tn,vel,1,0,0);
    );
   );
  ):(
   mem[row+7] && mem[row]==generation && mem[row+1]==id?(
    gi=mem[row+2];tn=mem[row+4];mode=mem[row+5];ch=mem[row+3];note=mem[row+6];
    mem[I_EXISTS_BASE+gi] && mem[I_IDS_BASE+gi]==id?(
     param_track_input(gi,ch,note,0,0);
     tn>=0 && tn<=127?(
      mode>0?(
       mem[NATIVE_DEST_MONO+gi*128+tn]=max(0,mem[NATIVE_DEST_MONO+gi*128+tn]-1);
       route_mono_note(gi,offs,128|ch,tn,0,0,0);
      ):route_emit_note(gi,offs,128|ch,tn,0,0,0,0);
     );
    );mem[row+7]=0;
   );
  );native_destination_context=sc;sw_playback_origin=sp;native_transform_voice=sv;
 );
);
'''
NEXT=r'''
function native_thru_next() local(done,result,b,echo_offset,budget)
(
 done=0;result=0;budget=513;
 while(!done && budget>0)(
  !native_destination_physical_ready?(
   native_destination_physical_ready=native_destination_physical_next();
   native_destination_physical_offset=offset;native_destination_physical_st=msg1;
   native_destination_physical_data=msg23;native_destination_physical_bus=midi_bus;
  );
  b=NATIVE_DEST_QUEUE+native_destination_read*9;echo_offset=mem[b+7];
  native_destination_read<native_destination_count && (!native_destination_physical_ready || echo_offset<native_destination_physical_offset)?(
   native_destination_receive(native_destination_read);native_destination_read+=1;
  ):(
   native_destination_physical_ready?(
    offset=native_destination_physical_offset;msg1=native_destination_physical_st;
    msg23=native_destination_physical_data;midi_bus=native_destination_physical_bus;
    native_destination_physical_ready=0;result=1;
   );done=1;
  );budget-=1;
 );result;
);
'''

def extend(source):
 def change(old,new):
  nonlocal source
  if source.count(old)!=1:raise ValueError('Native destination contract changed: '+old[:90])
  source=source.replace(old,new)
 change('function native_echo_event(',STATE+'\nfunction native_echo_event(')
 change('mem[NATIVE_ECHO_ARP_ORIGIN+gi]=origin;', 'origin=native_destination_arp_origin(gi,note,origin);mem[NATIVE_ECHO_ARP_ORIGIN+gi]=origin;')
 change('local(ch,key,origin,idx,echo_voice,echo_id)', 'local(ch,key,origin,idx,echo_voice,echo_id,echo_origin)')
 change('idx=(gi*16+ch)*128+note;\n  !(mem[engine_addr(INST_ARP_ENABLED_BASE,gi)]>.5',
        'idx=(gi*16+ch)*128+note;\n  echo_origin=native_destination_origin(gi,ch,note,is_on,origin);\n  !(mem[engine_addr(INST_ARP_ENABLED_BASE,gi)]>.5')
 change('native_echo_event(is_on?1:2,mem[I_IDS_BASE+gi],echo_id,ch,note,is_on?vel:0,origin,offs);',
        'native_echo_event(is_on?1:2,mem[I_IDS_BASE+gi],echo_origin==2?0:echo_id,ch,note,is_on?vel:0,echo_origin,offs);')
 change('  mem[engine_addr(INST_ARP_ENABLED_BASE,gi)]>0.5 && transformer_on(gi,5) ? (\n    origin ? (',
        '  mem[engine_addr(INST_ARP_ENABLED_BASE,gi)]>0.5 && transformer_on(gi,5) ? (\n    echo_origin==2?(is_on?(mem[NATIVE_DEST_ARP_SOURCE+gi*128+note]+=1;mem[NATIVE_DEST_ARP+gi*128+note]+=1;):(mem[NATIVE_DEST_ARP_SOURCE+gi*128+note]=max(0,mem[NATIVE_DEST_ARP_SOURCE+gi*128+note]-1);mem[engine_addr(INST_ARP_HOLD_BASE,gi)]<.5?mem[NATIVE_DEST_ARP+gi*128+note]=max(0,mem[NATIVE_DEST_ARP+gi*128+note]-1);););\n    origin ? (')
 change('  source_voice=native_transform_voice;\n', '  native_destination_mono_depth+=1;source_voice=native_transform_voice;\n')
 change('  native_transform_voice=source_voice;\n);', '  native_transform_voice=source_voice;native_destination_mono_depth-=1;\n);')
 change('function send_to_instruments(offs, st, d1, d2, extra_gain)',RECEIVE+'\nfunction send_to_instruments(offs, st, d1, d2, extra_gain)')
 change('function native_thru_next()', 'function native_destination_physical_next()')
 change('function native_thru_reset()', NEXT+'\nfunction native_thru_reset()')
 change('function native_thru_begin()\nlocal(slot,at,offs,st,data)\n(',
        'function native_thru_begin()\nlocal(slot,at,offs,st,data)\n(native_destination_physical_ready=0;native_destination_read=0;')
 change('function reset_note_runtime()\nlocal(pv_i)\n(',
        'function reset_note_runtime()\nlocal(pv_i)\n(native_destination_epoch+=1;native_destination_read=0;native_destination_count=0;memset(NATIVE_DEST_LEASE,0,2048);memset(NATIVE_DEST_MONO,0,1024);memset(NATIVE_DEST_ARP,0,1024);memset(NATIVE_DEST_ARP_SOURCE,0,1024);memset(NATIVE_DEST_MONO_ORIGIN,0,16384);')
 change('function i_clear_runtime(gi)\nlocal(j,idx,v)\n(',
        'function i_clear_runtime(gi)\nlocal(j,idx,v)\n(memset(NATIVE_DEST_MONO+gi*128,0,128);memset(NATIVE_DEST_ARP+gi*128,0,128);memset(NATIVE_DEST_ARP_SOURCE+gi*128,0,128);memset(NATIVE_DEST_MONO_ORIGIN+gi*2048,0,2048);j=0;loop(256,mem[NATIVE_DEST_LEASE+j*8+2]==gi?mem[NATIVE_DEST_LEASE+j*8+7]=0;j+=1;);')
 import re
 match=re.search(r'function arp_clear_latch\(gi\)\nlocal\([^\n]+\)\n\(',source)
 if not match:raise ValueError('Native destination latch contract changed')
 change(match.group(),match.group()+'memcpy(NATIVE_DEST_ARP+gi*128,NATIVE_DEST_ARP_SOURCE+gi*128,128);')
 match=re.search(r'function arp_release_instrument\(gi\)\nlocal\([^\n]+\)\n\(',source)
 if not match:raise ValueError('Native destination ARP release contract changed')
 change(match.group(),match.group()+'memset(NATIVE_DEST_ARP+gi*128,0,128);memset(NATIVE_DEST_ARP_SOURCE+gi*128,0,128);')
 return source
