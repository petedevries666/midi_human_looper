// Real shared EEL capture, including the first attack inside an audio block.
// Test both REAPER-style capture and the default native free-time adapter.
static void free_capture_tests(const char* source) {
  for (int mode : {0,1,2}) for (unsigned origin : {0u,17u,96u})
    for (unsigned wait : {0u,1600u}) for(bool native : {false,true}) {
      Host h(source);
      h.run("ext_noinit=1;gmem[0]=0;panic_pending=0;slider9=1;clear_layer(4);"
            "mem[MODE_BASE+4]="+std::to_string(mode)+";panic_pending=0;");
      ChainMode chain(h.f,native,2);
      if(native)check(chain.command(2,4),"native free REC admitted");
      else h.run("arm_layer(4);");
      uint64_t frame=12345;
      auto block=[&]() {
        if(native)chain.tick(frame,128,48000,true,frame<100000?120:173);
        h.block();h.events();frame+=128;
        if(native)chain.observe();
      };
      for(unsigned b=0;b<wait;++b){block();}
      h.eq("state",h.val("STATE_READY"),"free capture waits indefinitely for a note");
      auto send=[&](int st,int note,int vel,unsigned offset) {
        uint8_t bytes[]={uint8_t(st),uint8_t(note),uint8_t(vel)};
        ysfx_midi_event_t e{};e.offset=offset;e.size=3;e.data=bytes;
        check(ysfx_send_midi(h.f,&e),"enqueue free capture MIDI");
      };
      send(178,7,80,0); // pre-attack controls affect live input, not source data
      send(146,65,97,origin);send(147,69,83,origin);
      send(146,72,91,origin+7);block();
      send(130,65,31,0);send(131,69,21,32);send(130,72,17,64);
      block();
      if(native)check(chain.command(3,4),"native free FINISH admitted");
      else h.run("finish_phrase_record();");
      h.eq("layer_count(4)",6,"free capture retains all chord attacks and releases");
      const unsigned times[]={0,0,7,128-origin,160-origin,192-origin};
      for(unsigned i=0;i<6;++i)
        h.eq("mem[layer_base(4,"+std::to_string(i)+")]",times[i],
             "one origin preserves first-block spacing and subsequent durations");
      h.eq("mem[LEN_BASE+4]",256-origin,"free phrase length is actual elapsed recording time");
      h.eq("mem[MODE_BASE+4]",mode,"free recording preserves playback mode");
      if(const char* path=std::getenv("FREE_CAPTURE_FIXTURE")) {
        std::ofstream out(path,std::ios::app);
        out << "{\"lengthSeconds\":" << (256-origin)/48000.
            << ",\"bpm\":120,\"events\":[";
        for(unsigned i=0;i<6;++i) {
          h.run("free_test_addr=layer_base(4,"+std::to_string(i)+");");
          const unsigned addr=unsigned(h.val("free_test_addr"));
          if(i)out << ',';
          out << '[' << *NSEEL_VM_getramptr(h.f->vm.get(),addr,nullptr)/48000.;
          for(unsigned k=1;k<4;++k)
            out << ',' << int(*NSEEL_VM_getramptr(h.f->vm.get(),addr+k,nullptr));
          out << ']';
        }
        out << "]}\n";
      }
    }
  // No external transport is needed to arm or record. Finishing a held attack
  // closes source ownership at the actual take end, not a calculated bar end.
  Host h(source);
  h.run("ext_noinit=1;gmem[0]=0;panic_pending=0;slider9=1;clear_layer(5);");
  ChainMode chain(h.f,true,2);
  check(chain.command(2,5),"free arm without an external transport");
  for(unsigned i=0;i<1600;++i){chain.tick(i*128,128,48000,false,120);h.block();h.events();}
  check(chain.armed && !chain.recording,"stopped transport cannot start the free recorder");
  h.midi(145,61,99);chain.observe();
  check(chain.recording && !chain.armed,"first note starts capture with no rolling transport");
  h.block();h.events();
  check(chain.command(3,5),"FINISH accepts a held note without external transport");
  h.eq("layer_count(5)",2,"native free FINISH supplies the missing paired release");
  h.eq("mem[LEN_BASE+5]",256,"native free FINISH retains actual take duration");
  h.eq("mem[layer_base(5,1)]",255,"held release stays inside actual phrase end");
  h.eq("mem[layer_base(5,1)+1]",129,"held release retains exact channel");
  h.eq("mem[layer_base(5,1)+2]",61,"held release retains exact pitch");
  h.run("clear_layer(6);panic_pending=0;");
  check(chain.command(2,6),"arm independent empty phrase");
  chain.tick(0,128,48000,true,120,1000000);
  chain.tick(384,128,48000,true,120,1000384);
  check(chain.armed && !chain.error,"missed callback while waiting cannot invent a recording");
  h.midi(144,62,0);chain.observe();
  check(chain.armed && !chain.recording,"velocity-zero Note On cannot start a take");
  h.midi(144,62,100);chain.observe();
  check(chain.tick(768,128,48000,true,120,1000768),"missed capture callback still requests owned-note cleanup");
  check(chain.error && !chain.recording && !chain.armed,"missed capture remains an explicit error");
}
