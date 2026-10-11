#include "../headless/chain_mode.hpp"
static void chain_mode_tests(const char *source) {
  Host h(source);
  h.run("ext_noinit=1;gmem[0]=0;panic_pending=0;slider9=1;");
  ChainMode chain(h.f, true);
  chain.command(2, 0);
  check(!chain.tick(0, 128, 48000, false, 120),
        "armed record survives JACK Starting/Stopped before first roll");
  check(chain.armed, "record pending until transport rolls");
  chain.tick(0, 128, 48000, true, 120);
  check(chain.recording && !chain.armed, "take begins at common grid origin");
  h.eq("mem[MODE_BASE]", 1, "recording preserves default ONCE mode");
  h.midi(144, 60, 100);
  chain.tick(128, 128, 48000, true, 120);
  h.midi(128, 60, 0);
  h.eq("layer_count(0)", 2,
       "existing recording dispatcher captures paired MIDI");
  chain.command(3, 0);
  check(!chain.recording, "manual finish disarms only selected recording");
  h.eq("mem[TRIG_BASE]", 1, "recorded loop armed for playback");
  h.eq("mem[LEN_BASE]", 192000, "take retains shared two-bar length");
  chain.previous = 0;
  chain.command(2, 0);
  chain.tick(0, 128, 48000, true, 120);
  check(!chain.command(2, 1),
        "recording target cannot be stolen by another phrase");
  h.midi(144, 65, 100);
  chain.command(3, 0);
  h.eq("layer_count(0)", 4,
       "overdub retains earlier take and adds paired notes");
  chain.previous = 0;
  h.run("clear_layer(1);");
  chain.command(2, 1);
  chain.tick(256, 128, 48000, true, 120);
  check(chain.armed && !chain.recording, "second phrase waits for common wrap");
  chain.tick(384, 128, 48000, false, 120);
  check(!chain.run && !chain.armed,
        "transport STOP cancels record and playback");
  chain.previous = 0;
  chain.command(2, 1);
  chain.tick(192000, 128, 48000, true, 120);
  h.midi(145, 61, 100);
  chain.command(3, 1);
  h.eq("layer_count(1)", 2, "finish supplies missing recorded Note Off");
  h.eq("mem[layer_base(1,1)]", 191999, "synthetic release remains inside loop");
  h.eq("mem[layer_base(1,1)+1]", 129,
       "synthetic release preserves MIDI channel");
  check(chain.tick(192128, 128, 48000, true, 130),
        "tempo change requires owned-note release");
  check(chain.error && !chain.run,
        "tempo change never silently stretches recorded events");
  check(!chain.tick(192256, 128, 48000, true, 130),
        "latched clock error does not spam PANIC each block");
  chain.previous = 0;
  chain.command(1, 1);
  chain.tick(100000, 128, 48000, true, 120);
  check(chain.tick(0, 128, 48000, true, 120) && !chain.run,
        "transport seek cancels playback safely");
  chain.previous = 0;
  chain.command(1, 1);
  chain.tick(100000, 128, 48000, true, 120, 1000000);
  check(chain.tick(100384, 128, 48000, true, 120, 1000384) && chain.run,
        "missed callback resumes playback with release, unlike transport seek");
  // Interruption must retain an error after cancel() clears recording.
  chain.previous = 0;
  chain.command(2, 1);
  chain.tick(192000, 128, 48000, true, 120, 2000000);
  check(chain.tick(192384, 128, 48000, true, 120, 2000384) && !chain.run && chain.error,
        "missed recording callback stops and reports capture failure");
  chain.previous = 0;
  chain.command(1, 1);
  chain.tick(100000, 128, 48000, true, 120, 1000000);
  check(chain.tick(0, 128, 48000, true, 120, 1000512) && !chain.run,
        "transport seek is detected independently of JACK sample clock");
  // Full phrase with an unmatched attack must be rejected, never played without
  // its release.
  h.run("clear_layer(2);store_event(2,0,144,62,100,0);chain_test_i=1;loop(MAX_"
        "EVENTS_PER_LAYER-1,store_event(2,chain_test_i,176,1,1,0);chain_test_i+"
        "=1;);");
  chain.previous = 0;
  chain.command(2, 2);
  chain.tick(0, 128, 48000, true, 120);
  chain.command(3, 2);
  h.eq("mem[TRIG_BASE+2]", 0, "capacity exhaustion disables unsafe loop");
}

// Timing v2: musical duration is independent of the processing buffer.
static void chain_exact_timing_tests(const char *source) {
  Host h(source);
  h.run("ext_noinit=1;gmem[0]=0;panic_pending=0;slider9=1;");
  for (unsigned rate : {44100u,48000u,96000u})
    for (unsigned block : {128u,256u,512u,8192u})
      for (double bpm : {73.,120.,137.}) {
        ChainMode c(h.f,true,2);
        c.tick(0,block,rate,true,bpm);
        const uint64_t length=uint64_t(std::llround(rate*480./bpm));
        check(c.length==length,"v2 exact musical length independent of buffer");
        c.tick(length+17,block,rate,true,bpm);
        h.eq("chain_phase",17,"v2 exact phase independent of block alignment");
      }
  ChainMode c(h.f,true,2);
  c.tick(0,128,44100,true,120);
  h.run("clear_layer(3);");c.command(2,3);
  const uint64_t start=176384; // grid origin occurs 16 samples into this block
  c.previous=0;c.tick(start,128,44100,true,120);
  check(c.recording&&!c.armed,"v2 arms on an in-block musical boundary");
  auto send=[&](int st,int note,int vel,unsigned offset) {
    uint8_t b[]={uint8_t(st),uint8_t(note),uint8_t(vel)};
    ysfx_midi_event_t e{};e.offset=offset;e.size=3;e.data=b;
    check(ysfx_send_midi(h.f,&e),"enqueue boundary MIDI");
  };
  send(144,60,100,15); // excluded before boundary
  send(144,61,90,16);send(128,60,0,17);send(128,61,40,40);
  h.block();h.events();
  h.eq("layer_count(3)",2,"capture excludes pre-window attacks and orphan releases");
  h.eq("mem[layer_base(3,0)]",0,"in-block boundary attack stored at T=0");
  h.eq("mem[layer_base(3,1)]",24,"in-block release retains duration");
  c.previous=0;c.tick(352768,128,44100,true,120); // end=352800, offset32
  send(144,62,80,31);send(144,63,80,32);h.block();h.events();
  c.tick(352896,128,44100,true,120);
  check(!c.recording,"take finishes after exact capture window");
  h.eq("layer_count(3)",4,"late attacks excluded and crossing note receives release");
  h.eq("mem[layer_base(3,2)]",176399,"last sample attack retained");
  h.eq("mem[layer_base(3,3)]",176399,"boundary synthetic release stays in window");
}

static void chain_exact_playback_tests(const char *source) {
  for (unsigned rate : {44100u,48000u,96000u})
    for (unsigned block : {128u,512u,8192u}) {
      Host h(source,false);ysfx_set_sample_rate(h.f,rate);
      ysfx_set_block_size(h.f,block);ysfx_init(h.f);
      h.run("slider9=1;slider5=0;mem[INST_TRANSFORM_COUNT_BASE]=0;"
            "clear_layer(0);mem[MODE_BASE]=0;mem[VEL_BASE]=1;"
            "store_event(0,0,144,60,100,0);store_event(0,32,128,60,0,0);");
      ChainMode c(h.f,true,2);c.command(1,0);c.tick(0,block,rate,true,137);
      const uint64_t length=c.length,start=(length-1)/block*block;
      bool on=false,off=false;c.previous=0;
      for (uint64_t frame=start;frame<start+2*block;frame+=block) {
        c.tick(frame,block,rate,true,137);
        ysfx_process_float(h.f,nullptr,nullptr,0,0,block);
        ysfx_midi_event_t e{};
        while(ysfx_receive_midi(h.f,&e)) if(e.size==3 && e.data[1]==60) {
          if((e.data[0]&240)==144 && e.data[2]>0) {
            check(frame+e.offset==length,"v2 playback attack on exact grid across block edge");on=true;
          } else if((e.data[0]&240)==128 || ((e.data[0]&240)==144 && !e.data[2])) {
            check(frame+e.offset==length+32,"v2 paired release retains sample duration");off=true;
          }
        }
      }
      check(on&&off,"actual EEL playback crosses nonaligned grid with paired notes");
    }
}

// Reproduce hardware failure: delayed first attack, arbitrary arming phase,
// selected ONCE or LOOP. Assert authoritative source storage, not export repair.
static void chain_capture_origin_tests(const char *source) {
  for (unsigned version : {1u,2u}) for(int mode : {0,1})
    for(unsigned phase : {128u,8192u,100000u}) {
      Host h(source);
      h.run("ext_noinit=1;gmem[0]=0;panic_pending=0;slider9=1;clear_layer(4);");
      *NSEEL_VM_getramptr(h.f->vm.get(),unsigned(*ysfx_find_var(h.f,"MODE_BASE"))+4,nullptr)=mode;
      ChainMode c(h.f,true,version);
      c.tick(phase,128,48000,true,120);c.command(2,4);
      c.previous=0;c.tick(192000,128,48000,true,120);
      c.tick(192128,128,48000,true,120);
      h.midi(146,65,97);
      c.tick(192256,128,48000,true,120);h.midi(130,65,31);
      c.command(3,4);
      h.eq("mem[MODE_BASE+4]",mode,"REC preserves selected playback mode");
      h.eq("mem[layer_base(4,0)]",0,"delayed first recorded attack has authoritative T=0");
      h.eq("mem[layer_base(4,1)]",128,"common shift preserves note duration");
      h.eq("mem[layer_base(4,0)+1]",146,"capture preserves channel");
      h.eq("mem[layer_base(4,0)+3]",97,"capture preserves velocity");
      if(const char* path=std::getenv("CAPTURE_SOURCE_FIXTURE")) {
        std::ofstream out(path,std::ios::app);
        out << "{\"lengthSeconds\":4,\"bpm\":120,\"events\":[";
        for(int i=0;i<2;++i) {
          // layer_base includes layout stride; query through EEL, outside RT.
          h.run(i==0?"capture_test_addr=layer_base(4,0);":"capture_test_addr=layer_base(4,1);");
          unsigned addr=unsigned(*ysfx_find_var(h.f,"capture_test_addr"));
          if(i)out << ',';
          out << '[' << *NSEEL_VM_getramptr(h.f->vm.get(),addr,nullptr)/48000.;
          for(unsigned k=1;k<4;++k)out << ',' << int(*NSEEL_VM_getramptr(h.f->vm.get(),addr+k,nullptr));
          out << ']';
        }
        out << "]}\n";
      }
    }
}
