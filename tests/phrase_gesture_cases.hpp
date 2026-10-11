// Exercise the shared JSFX used by both REAPER and the native host, including
// physical MIDI timestamps rather than a separate mathematical simulation.
static void phrase_gesture_tests(const char *path) {
  Host h(path);
  h.run("panic_pending=0;state=STATE_STOPPED;mem[INST_ENABLED_BASE]=1;"
        "mem[INST_ENABLED_BASE+1]=0;mem[INST_ENABLED_BASE+2]=0;"
        "mem[INST_TRANSFORM_COUNT_BASE]=0;mem[COUNT_BASE]=0;"
        "store_event(0,0,144,60,100,0);store_event(0,5,144,64,90,0);"
        "store_event(0,50,128,64,0,0);store_event(0,400,128,60,0,0);"
        "mem[LEN_BASE]=512;mem[MODE_BASE]=1;mem[PH_POLICY_BASE]=1;"
        "mem[PHRASE_NOTE_BASE]=70;mem[learn_phrase_channel(0)]=1;");
  auto queue = [&](int status, unsigned offset) {
    uint8_t bytes[] = {uint8_t(status),70,100};
    ysfx_midi_event_t event{};event.data=bytes;event.size=3;event.offset=offset;
    check(ysfx_send_midi(h.f,&event),"queue timestamped phrase gesture");
  };
  queue(144,20);queue(144,30);h.block();
  ysfx_midi_event_t e{};unsigned attacks=0,releases=0;
  while(ysfx_receive_midi(h.f,&e)) {
    if(e.size==3 && (e.data[0]&240)==144 && e.data[2]) {
      ++attacks;check(e.offset==(e.data[1]==60?20:25),"immediate source attacks retain intra-block time");
    }
    if(e.size==3 && (e.data[0]&240)==128) {
      ++releases;check(e.offset==30,"second PRESS releases owned notes at its timestamp");
    }
    check(e.size!=3 || e.data[1]!=70,"trigger gesture never leaks to output");
  }
  check(attacks==2 && releases==2,"second PRESS stops without restarting phrase or chord");
  h.eq("phrase_playing(0)",0,"toggle STOP removes running voice");
  h.eq("mem[REPEAT_BASE]",0,"toggle STOP does not count a retrigger");
  h.midi(144,70,100);h.events();h.eq("phrase_playing(0)",1,"next PRESS starts after STOP");
  h.midi(128,70,0);h.events();h.eq("phrase_playing(0)",1,"ONCE NO RETRIGGER ignores RELEASE");
  h.block();h.events();h.block();h.events();h.eq("phrase_playing(0)",0,"new mode ends naturally");
  h.eq("mem[NOTE_REF_BASE+60]",0,"natural completion releases source ownership");
  h.midi(144,70,100);h.events();h.eq("phrase_playing(0)",1,"PRESS after natural end starts anew");
  h.midi(144,70,100);h.events();
  // A live note at the same pitch must survive a phrase-only STOP.
  h.midi(144,60,80);h.events();h.midi(144,70,100);h.events();
  h.midi(144,70,100);auto messages=h.events();bool killedLive=false;
  for(auto &m:messages)if((m[0]&240)==128 && m[1]==60)killedLive=true;
  check(!killedLive,"phrase STOP preserves a live owner of the same channel/pitch");
  h.midi(128,60,0);h.events();
  h.run("save_patch(1);mem[PH_POLICY_BASE]=0;ph_bank_load(1);");
  h.eq("mem[PH_POLICY_BASE]",1,"patch bank retains playback policy");
  h.run("external_patch_save_request(1);mem[PH_POLICY_BASE]=0;external_patch_apply();");
  h.eq("mem[PH_POLICY_BASE]",1,"external patch roundtrip retains playback policy");
  h.run("gmem[2]=7;gmem[3]=PH_LEGACY_PAYLOAD;gmem[0]=2;external_patch_apply();");
  h.eq("mem[PH_POLICY_BASE]",0,"schema-7 migration preserves legacy ONCE semantics");
  h.run("mem[PH_POLICY_BASE]=1;mem[INST_TRANSFORM_COUNT_BASE]=1;"
        "mem[INST_TRANSFORM_TYPE_BASE]=5;mem[INST_ARP_ENABLED_BASE]=1;");
  h.midi(144,70,100);h.events();h.eq("mem[PH_ERROR_BASE]",1,"unsafe stateful routing is explicitly rejected");
  h.eq("phrase_playing(0)",0,"rejected start never owns a hidden voice");
  h.run("mem[INST_TRANSFORM_COUNT_BASE]=0;mem[PH_POLICY_BASE]=2;"
        "mem[COUNT_BASE]=0;store_event(0,0,144,60,100,0);"
        "store_event(0,256,128,60,0,0);mem[LEN_BASE]=256;");
  h.midi(144,70,100);h.events();h.eq("phrase_playing(0)",1,"PRESS RELEASE starts immediately");
  h.block();h.events();h.block();messages=h.events();
  bool loopAttack=false,boundaryOff=false;
  for(auto &m:messages){if((m[0]&240)==144&&m[1]==60)loopAttack=true;if((m[0]&240)==128&&m[1]==60)boundaryOff=true;}
  check(loopAttack && boundaryOff,"held phrase loops with paired boundary events");
  h.eq("phrase_playing(0)",1,"held phrase continues beyond natural source end");
  queue(128,20);h.block();releases=0;
  while(ysfx_receive_midi(h.f,&e))if(e.size==3 && (e.data[0]&240)==128 && e.data[1]==60){++releases;check(e.offset==20,"physical RELEASE stops at exact MIDI offset");}
  check(releases==1,"RELEASE cleans up currently sounding held note");
  h.eq("phrase_playing(0)",0,"RELEASE removes loop voice");
  h.midi(144,70,100);h.events();h.eq("phrase_playing(0)",1,"new PRESS restarts held phrase");
  h.midi(144,70,0);h.events();h.eq("phrase_playing(0)",0,"velocity-zero PRESS is a reliable RELEASE");
  queue(144,20);queue(128,21);h.block();attacks=releases=0;
  while(ysfx_receive_midi(h.f,&e))if(e.size==3&&e.data[1]==60){if((e.data[0]&240)==144&&e.data[2]){++attacks;check(e.offset==20,"one-sample tap begins immediately");}if((e.data[0]&240)==128){++releases;check(e.offset==21,"one-sample tap releases immediately");}}
  check(attacks==1&&releases==1,"very short tap leaves no hidden note or voice");
  h.eq("phrase_playing(0)",0,"very short tap cancels held loop");
  h.run("mem[LEN_BASE]=1;");h.midi(144,70,100);h.events();
  h.eq("mem[PH_ERROR_BASE]",2,"sub-capacity loop period rejected before admission");
  h.eq("phrase_playing(0)",0,"bounded-loop rejection creates no voices");
  h.run("mem[PH_POLICY_BASE]=1;mem[COUNT_BASE]=0;store_event(0,0,144,60,100,0);"
        "store_event(0,32,128,60,0,0);mem[LEN_BASE]=32;");
  queue(144,0);queue(144,64);h.block();attacks=releases=0;
  while(ysfx_receive_midi(h.f,&e))if(e.size==3&&e.data[1]==60){
    if((e.data[0]&240)==144&&e.data[2]){check(e.offset==(attacks?64:0),"PRESS after intra-block natural end restarts");++attacks;}
    if((e.data[0]&240)==128){check(e.offset==(releases?96:32),"intra-block natural endings retain exact Note Off time");++releases;}
  }
  check(attacks==2&&releases==2,"two naturally completed passes in one block are not mistaken for toggle STOP");
  h.run("mem[COUNT_BASE]=0;store_event(0,0,144,60,100,0);store_event(0,128,128,60,0,0);mem[LEN_BASE]=128;");
  queue(144,0);h.block();h.events();h.eq("phrase_playing(0)",0,"natural end at buffer boundary is already complete");
  queue(144,0);h.block();attacks=releases=0;
  while(ysfx_receive_midi(h.f,&e))if(e.size==3&&e.data[1]==60){check(e.offset==0,"boundary cleanup and restart both occur at sample zero");if((e.data[0]&240)==128){++releases;check(attacks==0,"old Note Off precedes new Note On at boundary");}if((e.data[0]&240)==144&&e.data[2])++attacks;}
  check(attacks==1&&releases==1,"boundary restart preserves owned Note Off without early release");
  h.block();h.events();
  h.run("mem[PH_POLICY_BASE]=2;mem[LEN_BASE]=512;mem[COUNT_BASE]=0;"
        "store_event(0,0,144,60,100,0);store_event(0,400,128,60,0,0);");
  h.frame(345,204,1);h.block();h.events();h.eq("phrase_playing(0)",1,"REAPER mouse-down starts held mode");
  h.frame(0,0,0);h.block();h.events();h.eq("phrase_playing(0)",0,"REAPER mouse-up outside button releases held mode");
  h.midi(144,70,100);h.events();h.run("panic_pending=1;");h.block();h.events();
  h.eq("phrase_playing(0)",0,"PANIC cancels held loop");h.eq("mem[NOTE_REF_BASE+60]",0,"PANIC clears held ownership");
  // Sample timing remains identical at different host rates and buffer sizes.
  for(unsigned rate:{44100u,48000u,96000u})for(unsigned frames:{32u,128u,512u,8192u}) {
    Host timed(path);ysfx_set_sample_rate(timed.f,rate);ysfx_set_block_size(timed.f,frames);ysfx_init(timed.f);
    timed.run("panic_pending=0;state=STATE_STOPPED;mem[INST_ENABLED_BASE]=1;"
              "mem[INST_ENABLED_BASE+1]=0;mem[INST_ENABLED_BASE+2]=0;mem[INST_TRANSFORM_COUNT_BASE]=0;"
              "mem[COUNT_BASE]=0;store_event(0,0,144,60,100,0);store_event(0,"+std::to_string(frames*2)+",128,60,0,0);"
              "mem[LEN_BASE]="+std::to_string(frames*4)+";mem[MODE_BASE]=1;mem[PH_POLICY_BASE]=2;"
              "mem[PHRASE_NOTE_BASE]=70;mem[learn_phrase_channel(0)]=1;");
    uint8_t on[]={144,70,100},off[]={128,70,0};ysfx_midi_event_t input{};
    input.size=3;input.data=on;input.offset=7;check(ysfx_send_midi(timed.f,&input),"rate/buffer PRESS queued");
    input.data=off;input.offset=19;check(ysfx_send_midi(timed.f,&input),"rate/buffer RELEASE queued");
    ysfx_process_float(timed.f,nullptr,nullptr,0,0,frames);unsigned count=0;
    while(ysfx_receive_midi(timed.f,&e))if(e.size==3&&e.data[1]==60){++count;check(e.offset==((e.data[0]&240)==144?7:19),"gesture timing independent of sample rate and block size");}
    check(count==2,"every rate/buffer emits exactly one safe note pair");
  }
  Host reopened(path);h.run("mem[PH_POLICY_BASE]=1;");auto *saved=ysfx_save_state(h.f);
  ysfx_load_state(reopened.f,saved);reopened.block();reopened.events();
  reopened.eq("mem[PH_POLICY_BASE]",1,"REAPER project restore retains playback policy");
  Host legacy(path);
  legacy.run("mem[MODE_BASE]=1;save_patch(1);save_patch(2);IO_SCHEMA=7;PATCH_PAYLOAD_SIZE=PH_LEGACY_PAYLOAD;");
  auto *oldState=ysfx_save_state(legacy.f);
  reopened.run("mem[PH_POLICY_BASE]=2;ph_bank_save(1);ph_bank_save(2);");
  ysfx_load_state(reopened.f,oldState);reopened.block();reopened.events();
  reopened.eq("mem[MODE_BASE]",1,"old REAPER state keeps legacy ONCE value");
  reopened.eq("mem[PH_POLICY_BASE]",0,"old REAPER state clears a previously active new policy");
  reopened.run("ph_bank_load(1);");reopened.eq("mem[PH_POLICY_BASE]",0,"old first bank also defaults to legacy policy");
  reopened.run("ph_bank_load(2);");reopened.eq("mem[PH_POLICY_BASE]",0,"old second bank also defaults to legacy policy");
  ysfx_state_free(oldState);
  ysfx_state_free(saved);
}
