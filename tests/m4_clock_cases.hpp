// Deterministic production ChainMode + full shared EEL, not a clock model.
static void m4_clock_tests(const char *source) {
  Host h(source);
  h.run("ext_noinit=1;gmem[0]=0;panic_pending=0;slider9=1;clear_layer(4);");
  ChainMode c(h.f,true,2);
  c.tick(123456,128,48000,true,120,1000000);
  check(c.command(2,4),"M4 REC admitted");
  h.midi(146,65,97);h.events();c.observe();
  check(c.recording,"M4 actual first note starts recording");
  check(!c.tick(123584,128,48000,false,120,1000128),
        "FREE TIME transport STOP is not an audio interruption");
  check(c.recording&&!c.error,"FREE TIME recording survives transport STOP");
  h.midi(130,65,31);h.events();c.observe();
  check(!c.tick(0,128,48000,false,120,1000256),
        "FREE TIME stopped transport seek is independent of capture clock");
  check(c.recording&&!c.error,"FREE TIME seek cannot finish or corrupt a take");
  h.block();h.events();
  check(!c.tick(98765,128,48000,true,120,1000384),
        "FREE TIME transport START keeps the sample timeline");
  c.command(3,4);
  h.eq("layer_count(4)",2,"transport changes retain complete source pair");
  h.eq("mem[layer_base(4,0)]",0,"first attack remains zero");
  h.eq("mem[layer_base(4,1)]",128,"relative duration unchanged by transport");
  h.eq("mem[LEN_BASE+4]",384,"take length comes only from processed samples");
  // Real audio gaps must remain errors even with stopped JACK transport.
  h.run("clear_layer(5);panic_pending=0;");
  c.tick(0,128,48000,false,120,1000512);c.command(2,5);
  h.midi(145,61,90);h.events();c.observe();
  check(c.tick(0,128,48000,false,120,1000896),"stopped-transport audio gap requests safety");
  check(c.error&&!c.recording&&!c.armed,"stopped-transport missed audio block rejects take");
  h.eq("layer_count(5)",0,"missed-block take rolled back atomically");
  h.eq("layer_count(4)",2,"failed capture preserves unrelated valid phrase");
  check(c.errorReason==ChainMode::CaptureError::AudioClockGap,"stable clock-gap reason");
  // Capacity and validation failures use real shared source append/finish paths.
  for(int failure=1;failure<=4;++failure){
    h.run("send_all_notes_off();reset_note_runtime();clear_layer(6);"
          "store_event(6,0,144,48,81,0);store_event(6,64,128,48,23,0);mem[LEN_BASE+6]=1024;mem[MODE_BASE+6]=1;panic_pending=0;");
    check(c.command(2,6),"arm existing phrase for rollback regression");
    check(!c.error && c.errorReason==ChainMode::CaptureError::None,"new REC clears latched error reason");
    h.midi(145,67,92);h.events();c.observe();
    check(c.recording,"actual overdub begins before injected fault");
    if(failure==1)h.run("m4_i=0;loop(2048,store_event(6,1,176,1,1,0);m4_i+=1;);");
    if(failure==2)h.run("m4_i=0;loop(2045,store_event(6,1,176,1,1,0);m4_i+=1;);");
    if(failure==3)h.run("mem[layer_base(6,2)]=-1;");
    if(failure==4)*c.phraseCounts[6]=std::nan("");
    c.command(3,6);
    check(c.error && int(c.errorReason)==std::min(failure,3),"precise overflow/release/validation reason");
    check(!c.recording && !c.armed && !c.freeCaptureSession,"failed session is ended");
    h.eq("layer_count(6)",2,"failed append rolls back count");
    h.eq("mem[LEN_BASE+6]",1024,"failed append restores original duration");
    h.eq("mem[layer_base(6,0)+2]",48,"failed append preserves old attack");
    h.eq("mem[layer_base(6,1)]",64,"failed append preserves old release timing");
    h.eq("mem[layer_base(6,1)+3]",23,"failed append preserves old release velocity");
    check(c.errorPhrase==6,"capture error identifies exact phrase");
    printf("M4 rejected case=%d reason=%s oldSourceEvents=2 oldLength=1024\n",failure,ChainMode::errorName(c.errorReason));
  }
  check(c.captureRejected==5 && c.captureOverflows==1,"diagnostic counters distinguish capture from output overflow");
  // Audio-cycle gaps are diagnosed regardless of rolling state, and wrap is safe.
  for(unsigned rate:{44100u,48000u,96000u})for(unsigned frames:{128u,256u,512u,8192u}){
    Host q(source,false);ysfx_set_sample_rate(q.f,rate);ysfx_set_block_size(q.f,frames);ysfx_init(q.f);
    q.run("slider9=1;panic_pending=0;clear_layer(2);");
    ChainMode d(q.f,true,2);d.command(2,2);
    d.tick(777,frames,rate,false,120,0);
    uint8_t bytes[]={146,66,90};ysfx_midi_event_t e{};e.size=3;e.offset=17;e.data=bytes;
    check(ysfx_send_midi(q.f,&e),"sample-accurate clock matrix input");
    ysfx_process_float(q.f,nullptr,nullptr,0,0,frames);q.events();d.observe();
    check(!d.tick(777,frames,rate,false,120,frames),"audio clock zero is a valid first cycle");
    bytes[0]=130;bytes[2]=31;e.offset=41;check(ysfx_send_midi(q.f,&e),"sample-accurate matrix release");
    ysfx_process_float(q.f,nullptr,nullptr,0,0,frames);q.events();d.observe();d.command(3,2);
    q.eq("mem[layer_base(2,0)]",0,"matrix first attack zero");
    q.eq("mem[layer_base(2,1)]",frames+24,"matrix note duration survives stopped transport");
    q.eq("mem[LEN_BASE+2]",2*frames-17,"matrix actual capture duration");
    d.haveAudioClock=false;d.tick(0,frames,rate,false,120,uint64_t(UINT32_MAX)-frames+1);
    check(!d.tick(0,frames,rate,false,120,0),"normal 32-bit JACK clock wrap is not an interruption");
  }
  // Missed block during overdub restores a previous valid source as well.
  h.run("send_all_notes_off();reset_note_runtime();panic_pending=0;");
  c.command(2,6);c.tick(0,128,48000,false,120,2000000);
  h.midi(145,70,90);h.events();c.observe();
  check(c.tick(0,128,48000,false,120,2000384),"overdub clock gap requests safety cleanup");
  check(c.errorReason==ChainMode::CaptureError::AudioClockGap,"overdub gap reason");
  h.eq("layer_count(6)",2,"gap rollback retains previous complete source");
  // Explicit STOP finalizes a valid take; CANCEL discards only the append.
  h.run("send_all_notes_off();reset_note_runtime();panic_pending=0;");
  c.command(2,6);h.midi(145,69,90);h.events();c.observe();c.command(5,6);
  h.eq("layer_count(6)",2,"explicit CANCEL preserves old source");
  c.command(2,6);h.midi(145,69,90);h.events();c.observe();c.command(0,0);
  check(!c.error && !c.recording && !c.armed,"explicit STOP safely finalizes without a clock error");
  h.eq("layer_count(6)",4,"STOP retains capture with synthetic paired release");
  // The production callback checks continuity before consuming FINISH/STOP.
  // A pending FINISH must not convert a failed append into a committed take.
  h.run("send_all_notes_off();reset_note_runtime();panic_pending=0;");
  c.command(2,6);c.tick(0,128,48000,false,120,3000000);
  h.midi(145,71,90);h.events();c.observe();
  check(c.tick(0,128,48000,false,120,3000384),"pre-command clock check rejects missed append");
  c.command(3,6);
  check(c.errorReason==ChainMode::CaptureError::AudioClockGap,"FINISH cannot clear failed-take diagnosis");
  h.eq("layer_count(6)",4,"FINISH after gap cannot commit a partial append");
  printf("PASS: %d M4 clock-domain checks\n",checks);
}
