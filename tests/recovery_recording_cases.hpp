static void recovery_recording_tests(const char* source) {
  Host h(source);
  h.run("ext_noinit=1;gmem[0]=0;panic_pending=0;slider9=1;mem[INST_ENABLED_BASE+1]=0;mem[INST_ENABLED_BASE+2]=0;clear_layer(0);clear_layer(1);store_event(0,0,144,60,100,0);store_event(0,64,128,60,0,0);mem[MODE_BASE]=0;mem[LEN_BASE]=512;loop_len_samples=512;mem[TRIG_BASE]=1;state=STATE_PLAYING;");
  ChainMode c(h.f,true,2);check(c.command(2,1),"arm a new take during another phrase's LOOP");
  h.eq("state",3,"arming never stops unrelated playback");
  h.midi(144,64,91);h.events();c.observe();check(c.recording,"independent recording starts on its first note");
  int bass=0;for(unsigned i=0;i<1700;++i){h.block();for(auto e:h.events())if(e[0]==144 && e[1]==60 && e[2])++bass;}
  check(bass>400,"LOOP continues throughout a recording longer than two bars");
  h.midi(128,64,31);h.events();check(c.command(3,1),"independent FINISH succeeds");
  h.eq("state",3,"FINISH preserves unrelated LOOP");h.eq("layer_count(1)",2,"long take retains its note pair");
  check(h.eval("mem[LEN_BASE+1]")>192000,"long phrase has actual duration beyond old capacity");
  // Different phrase periods share the sample clock without truncation or restart.
  h.run("clear_layer(1);store_event(1,0,144,67,90,0);store_event(1,64,128,67,0,0);mem[MODE_BASE+1]=0;mem[LEN_BASE+1]=768;");
  check(c.command(1,1),"start a different-length LOOP without restarting the first");
  std::vector<unsigned> first,second;
  for(unsigned frame=0;frame<4096;frame+=128){h.block();ysfx_midi_event_t e{};while(ysfx_receive_midi(h.f,&e))if(e.size==3 && (e.data[0]&240)==144 && e.data[2]){
    if(e.data[1]==60)first.push_back(frame+e.offset);if(e.data[1]==67)second.push_back(frame+e.offset);
  }}
  check(first.size()>=7&&second.size()>=5,"both independently sized loops remain audible");
  for(unsigned i=1;i<first.size();++i)check(first[i]-first[i-1]==512,"first phrase period preserved");
  for(unsigned i=1;i<second.size();++i)check(second[i]-second[i-1]==768,"second phrase period preserved");
  c.command(0,0);h.run("send_all_notes_off();reset_note_runtime();clear_layer(2);");h.events();
  check(c.command(2,2),"new overflow take admitted");
  for(unsigned i=0;i<2049;++i){uint8_t bytes[]={144,62,90};ysfx_midi_event_t e{};e.size=3;e.data=bytes;check(ysfx_send_midi(h.f,&e),"dense capture input admission");}
  h.block();h.events();h.eq("record_overflow",1,"capacity exhaustion is reported explicitly");
  check(c.tick(128,128,48000,true,120),"overflow requests safe output cleanup");
  check(c.error&&!c.recording,"overflow leaves authoritative ERROR, never an unsafe completed take");
  h.eq("layer_count(2)",0,"failed first take cannot persist silently truncated MIDI");
  h.eq("layer_count(0)",2,"overflow preserves the unrelated source phrase");
  h.run("send_all_notes_off();reset_note_runtime();clear_layer(3);");h.events();
  check(c.command(2,3),"recorder recovers after capacity failure");
  h.midi(145,69,94);h.events();h.midi(177,64,127);h.events();
  check(c.command(3,3),"finish closes held note and recorded sustain");
  h.eq("layer_count(3)",4,"source gets bounded missing Note Off and sustain-off");
  h.eq("mem[layer_base(3,3)+1]",177,"sustain cleanup keeps exact channel");
  h.eq("mem[layer_base(3,3)+2]",64,"sustain cleanup is CC64");
  h.eq("mem[layer_base(3,3)+3]",0,"sustain cleanup releases pedal");
  c.command(0,0);h.run("send_all_notes_off();reset_note_runtime();clear_layer(6);store_event(6,0,144,48,81,0);store_event(6,64,128,48,23,0);mem[MODE_BASE+6]=0;mem[LEN_BASE+6]=512;mem[TRIG_BASE+6]=1;mem[FREE_LOOP_ANCHOR_BASE+6]=0;state=STATE_PLAYING;play_sample_pos=510;");h.events();
  check(c.command(2,6),"LOOP overdub is armed at an arbitrary phase");
  uint8_t on[]={144,67,92},off[]={128,67,31};ysfx_midi_event_t input{};input.size=3;input.offset=17;input.data=on;check(ysfx_send_midi(h.f,&input),"first in-block overdub Note On");input.offset=97;input.data=off;check(ysfx_send_midi(h.f,&input),"first in-block overdub Note Off");
  h.block();h.eq("layer_count(6)",4,"wrap admission captures both events in its first block");
  h.eq("mem[layer_base(6,2)]",15,"onset is relative to in-block wrap, not the next callback");h.eq("mem[layer_base(6,3)]",95,"off retains its source duration");
  int monitored=0;for(auto e:h.events())if(e[0]==144 && e[1]==67 && e[2])++monitored;
  check(monitored==1,"new overdub notes are monitored once, not echoed by the loop in the same pass");
  check(c.command(3,6),"LOOP overdub FINISH");h.eq("mem[LEN_BASE+6]",512,"LOOP overdub retains its phrase duration");
}
