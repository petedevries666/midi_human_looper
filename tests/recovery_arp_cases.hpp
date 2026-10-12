static void recovery_arp_tests(const char* source) {
  for(unsigned rate:{44100u,48000u,96000u}) for(unsigned block:{64u,128u,512u,1024u})
    for(int mode:{0,1,2}) {
      Host h(source,false);ysfx_set_sample_rate(h.f,rate);ysfx_set_block_size(h.f,block);ysfx_init(h.f);
      ysfx_time_info_t time{};time.tempo=120;ysfx_set_time_info(h.f,&time);
      h.run("ext_noinit=1;gmem[0]=0;slider9=1;panic_pending=0;mem[INST_ENABLED_BASE+1]=0;mem[INST_ENABLED_BASE+2]=0;mem[INST_OUT_BASE]=3;mem[INST_LEVEL_BASE]=127;mem[INST_TRANSFORM_COUNT_BASE]=1;mem[INST_TRANSFORM_TYPE_BASE]=5;param_apply(0,3,1);param_apply(0,4,"+std::to_string(mode)+");param_apply(0,5,16);param_apply(0,6,.5);");
      for(int pitch:{60,64,67}){uint8_t bytes[]={144,uint8_t(pitch),100};ysfx_midi_event_t e{};e.size=3;e.data=bytes;check(ysfx_send_midi(h.f,&e),"ARP poly input admission");}
      std::vector<int> notes;std::map<int,uint64_t> sounding;unsigned pairs=0;
      const double step=rate/32.;
      for(unsigned frame=0;frame<unsigned(step*9);frame+=block){
        ysfx_process_float(h.f,nullptr,nullptr,0,0,block);ysfx_midi_event_t e{};
        while(ysfx_receive_midi(h.f,&e))if(e.size==3){
          const int kind=e.data[0]&240,note=e.data[1];const uint64_t at=frame+e.offset;
          check(e.offset<block,"ARP timestamp is inside callback");
          if(kind==144 && e.data[2]){check((e.data[0]&15)==2,"ARP obeys fixed output routing");notes.push_back(note);sounding[note]=at;}
          if(kind==128 && sounding.count(note)){
            check(std::abs(double(at-sounding[note])-step*.5)<=1,"ARP gates retain exact sample durations across block boundaries");sounding.erase(note);++pairs;
          }
        }
      }
      check(notes.size()>=8 && pairs>=8,"ARP produces real repeated paired MIDI");
      for(unsigned i=0;i<8;++i){
        if(mode==1)check(notes[i]==std::vector<int>({60,64,67})[i%3],"UP actual MIDI order");
        if(mode==2)check(notes[i]==std::vector<int>({67,64,60})[i%3],"DOWN actual MIDI order");
        if(mode==0)check(notes[i]==60||notes[i]==64||notes[i]==67,"RANDOM selects held pitches only");
      }
      h.run("mem[INST_TRANSFORM_TYPE_BASE]=-5;");ysfx_process_float(h.f,nullptr,nullptr,0,0,block);h.events();
      ysfx_process_float(h.f,nullptr,nullptr,0,0,block);
      for(auto e:h.events())check(!((e[0]&240)==144&&e[2]),"ARP bypass stops regeneration");
      h.run("send_all_notes_off();reset_note_runtime();");
      h.eq("mem[ARP_ACTIVE_NOTE_BASE]",-1,"ARP PANIC clears owned sounding note");
    }
}
