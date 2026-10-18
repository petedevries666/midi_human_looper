// M0: production native ChainMode -> full ysfx DSP -> actual MIDI output.
static void m0_playback_tests(const char *source) {
  for(unsigned block:{128u,512u,8192u}) {
    Host h(source,false);ysfx_set_sample_rate(h.f,48000);ysfx_set_block_size(h.f,block);ysfx_init(h.f);
    h.run("panic_pending=0;slider9=1;mem[INST_ENABLED_BASE]=1;mem[INST_ENABLED_BASE+1]=0;mem[INST_ENABLED_BASE+2]=0;mem[INST_TRANSFORM_COUNT_BASE]=0;mem[INST_OUT_BASE]=1;clear_layer(0);mem[MODE_BASE]=0;mem[VEL_BASE]=1;mem[DECAY_BASE]=1;store_event(0,0,144,60,100,0);");
    h.run("store_event(0,"+std::to_string(block*8)+",128,60,0,0);mem[LEN_BASE]="+std::to_string(block*16)+";loop_len_samples=mem[LEN_BASE];state=STATE_STOPPED;");
    ChainMode chain(h.f,true,2);h.events();
    auto process=[&](){ysfx_process_float(h.f,nullptr,nullptr,0,0,block);chain.observe();return h.events();};
    check(chain.command(1,0),"M0 direct LOOP first PLAY admitted");auto first=process();
    printf("M0 LOOP block=%u first=%s\n",block,conductor_events(first).c_str());fflush(stdout);
    check(conductor_count(first,144,60)==1,"M0 LOOP first PLAY emits an attack");
    check(chain.command(1,0),"M0 LOOP second PLAY admitted");auto second=process();
    printf("M0 LOOP block=%u second=%s\n",block,conductor_events(second).c_str());fflush(stdout);
    check(conductor_count(second,128,60)==1,"M0 LOOP second PLAY releases its owned note");
    check(conductor_count(second,144,60)==0,"M0 LOOP STOP does not retrigger");
    h.eq("mem[TRIG_BASE]",0,"M0 LOOP authoritative trigger is stopped");check(!chain.run,"M0 LOOP native observation stopped");
    check(chain.command(1,0),"M0 LOOP third PLAY admitted");auto third=process();
    check(conductor_count(third,144,60)==1,"M0 LOOP third PLAY restarts at source time zero");
    check(chain.run,"M0 LOOP native observation playing");
    check(chain.command(6,0),"M0 per-source explicit STOP admitted");auto stopped=process();
    check(conductor_count(stopped,128,60)==1,"M0 explicit STOP emits owned release");
    for(int i=0;i<20;++i){auto silent=process();check(conductor_count(silent,144,60)==0,"M0 stopped LOOP never regenerates");}
  }
}

static void m0_once_tests(const char *source) {
  Host h(source);conductor_fixture(h);ChainMode chain(h.f,true,2);
  auto process=[&](){h.block();chain.observe();return h.events();};
  check(chain.command(1,0),"M0 first ONCE source admitted");auto first=process();
  check(conductor_count(first,144,48)==1,"M0 first ONCE emits actual MIDI");
  check(chain.command(1,1),"M0 second ONCE source admitted");auto second=process();
  printf("M0 ONCE overlap second=%s active=%d\n",conductor_events(second).c_str(),conductor_active(h));fflush(stdout);
  check(conductor_active(h)==2,"M0 ONCE distinct sources overlap");
  check(conductor_count(second,144,72)==1 && conductor_count(second,128,48)==0,"M0 new ONCE never chokes earlier owner");
  h.run("reset_note_runtime();panic_pending=1;");process();
  conductor_fixture(h);h.run("mem[layer_base(1,0)+2]=48;mem[layer_base(1,1)+2]=48;");
  h.midi(144,48,107);h.events();
  check(chain.command(1,0),"M0 same-pitch first command accepted");auto a=process();check(chain.command(1,1),"M0 same-pitch second command accepted");auto b=process();
  printf("M0 same-pitch first=%s second=%s active=%d native=%.0f error=%.0f\n",conductor_events(a).c_str(),conductor_events(b).c_str(),conductor_active(h),h.val("native_phrase_contract"),h.val("instance_error"));fflush(stdout);
  check(conductor_active(h)==2,"M0 same-pitch ONCE sources have independent instances");
  int off=0;for(int i=0;i<80;++i)off+=conductor_count(process(),128,48);
  check(off==0,"M0 ONCE endings cannot release a physically held shared pitch");
  h.midi(128,48,0);check(conductor_count(h.events(),128,48)==1,"M0 final physical owner releases exactly once");
}

static void m0_latched_hold_tests(const char *source) {
  Host h(source);conductor_fixture(h);h.run("clear_layer(0);mem[MODE_BASE]=2;store_event(0,0,144,60,100,0);store_event(0,128,128,60,0,0);store_event(0,256,144,64,90,0);store_event(0,384,128,64,0,0);mem[LEN_BASE]=1024;");
  ChainMode chain(h.f,true,2);auto process=[&](){h.block();chain.observe();return h.events();};
  check(chain.command(1,0),"M0 HOLD first PRESS admitted");
  int ons=0,offs=0;for(int i=0;i<20;++i){auto e=process();ons+=conductor_count(e,144,60)+conductor_count(e,144,64);offs+=conductor_count(e,128,60)+conductor_count(e,128,64);}
  printf("M0 HOLD after source end: on=%d off=%d active=%d\n",ons,offs,conductor_active(h));fflush(stdout);
  check(ons==2 && offs==0,"M0 HOLD plays source once and retains notes, without looping or recorded Off");
  check(conductor_active(h)==1,"M0 HOLD remains truthfully active after source end");
  check(chain.command(4,0),"M0 HOLD RELEASE accepted as non-destructive edge");auto released=process();
  check(conductor_count(released,128,60)==0 && conductor_count(released,128,64)==0,"M0 HOLD ignores RELEASE");
  check(chain.command(1,0),"M0 HOLD second PRESS must not be rejected");auto restarted=process();
  printf("M0 HOLD retrigger=%s\n",conductor_events(restarted).c_str());fflush(stdout);
  check(conductor_count(restarted,128,60)==1 && conductor_count(restarted,128,64)==1,"M0 HOLD retrigger releases previous owned notes");
  check(conductor_count(restarted,144,60)==1,"M0 HOLD retrigger restarts at source time zero");
  check(conductor_active(h)==1,"M0 HOLD replacement consumes exactly one existing voice");
  check(chain.command(6,0),"M0 HOLD explicit source STOP is distinct from RELEASE");auto stopped=process();
  check(conductor_count(stopped,128,60)==1,"M0 HOLD source STOP releases current owned note");
  check(conductor_active(h)==0 && !chain.run,"M0 HOLD source STOP has authoritative inactive state");
  for(int i=0;i<20;++i)check(conductor_count(process(),144,60)==0,"M0 HOLD STOP never regenerates stale notes");
}

static void m0_entry_tests(const char *source) {
  for(bool smart:{false,true})for(int mode:{1,2}) {
    Host h(source);conductor_fixture(h);ChainMode chain(h.f,true,2);
    h.run("mem[PHRASE_NOTE_BASE]=111;mem[PHRASE_NOTE_BASE+1]=112;mem[learn_phrase_channel(0)]=1;mem[learn_phrase_channel(1)]=1;mem[MODE_BASE]="+std::to_string(mode)+";mem[MODE_BASE+1]="+std::to_string(mode)+";mem[sw_cfg(0)+11]="+std::to_string(mode==2?1:2)+";");
    const int firstNote=smart?110:111,secondNote=smart?110:mode==2?111:112;
    h.midi(144,firstNote,127);check(conductor_count(h.events(),144,48)==1,"M0 learned/switch ONCE or HOLD real first attack");
    h.midi(128,firstNote,0);auto release=h.events();check(conductor_count(release,128,48)==0,"M0 learned/switch RELEASE never ends ONCE or latched HOLD");
    h.midi(144,secondNote,127);auto output=h.events();
    printf("M0 %s %s second PRESS=%s\n",smart?"Smart Switch":"learned MIDI",mode==1?"ONCE":"HOLD",conductor_events(output).c_str());
    if(mode==1){check(conductor_active(h)==2 && conductor_count(output,144,72)==1 && conductor_count(output,128,48)==0,"M0 native learned/switch ONCE overlaps sources");}
    else{check(conductor_active(h)==1 && conductor_count(output,128,48)==1 && conductor_count(output,144,48)==1,"M0 native learned/switch HOLD cuts and retriggers");}
  }
  {
    Host h(source);conductor_fixture(h);ChainMode chain(h.f,true,2);
    h.run("snap_host_enabled=1;snap_parameter_apply(0,0,0,20,0);");h.block();h.events();
    h.eq("mem[MODE_BASE]",0,"M0 descriptor selects LOOP without musical trigger");
    h.eq("mem[TRIG_BASE]",0,"M0 mode edit must not pre-arm LOOP");
    check(chain.command(1,1),"M0 another source may start after LOOP mode edit");h.block();auto e=h.events();
    check(conductor_count(e,144,48)==0 && conductor_count(e,144,72)==1,"M0 unrelated PLAY cannot start edited LOOP");
  }
  for(bool smart:{false,true}) {
    Host h(source);conductor_fixture(h);ChainMode chain(h.f,true,2);
    h.run("mem[MODE_BASE]=0;mem[PHRASE_NOTE_BASE]=111;mem[learn_phrase_channel(0)]=1;mem[sw_cfg(0)+11]=1;loop_len_samples=8192;");
    const int note=smart?110:111;
    h.midi(144,note,100);auto on=h.events();
    check(conductor_count(on,144,48)==1,"M0 learned/Smart Switch LOOP emits attack");
    h.midi(128,note,0);h.events();h.midi(144,note,100);auto off=h.events();
    printf("M0 %s LOOP second PRESS=%s\n",smart?"Smart Switch":"learned MIDI",conductor_events(off).c_str());
    check(conductor_count(off,128,48)==1 && conductor_count(off,144,48)==0,"M0 every direct LOOP entry toggles source STOP");
    h.eq("mem[TRIG_BASE]",0,"M0 MIDI LOOP stopped state");
  }
  {
    Host h(source);conductor_fixture(h);ChainMode chain(h.f,true,2);
    conductor_install(h,conductor_model(1,false,2));
    h.midi(144,110,127);auto on=h.events();check(conductor_count(on,144,48)==1,"M0 Conductor HOLD override emits source");
    h.eq("mem[MODE_BASE]",1,"M0 Conductor HOLD never changes source mode");
    h.midi(128,110,0);check(conductor_count(h.events(),128,48)==0,"M0 Conductor HOLD ignores RELEASE");
    int attacks=0,offs=0;for(int i=0;i<90;++i){h.block();auto e=h.events();attacks+=conductor_count(e,144,48);offs+=conductor_count(e,128,48);}
    check(attacks==0 && offs==0 && conductor_active(h)==1,"M0 Conductor HOLD retained after timeline without repeat");
    check(chain.command(6,0),"M0 source STOP accepts Conductor owner");h.block();auto off=h.events();
    check(conductor_count(off,128,48)==1 && conductor_active(h)==0,"M0 explicit source STOP releases independent HOLD");
  }
  {
    Host h(source);conductor_fixture(h);ChainMode chain(h.f,true,2);
    for(int i=0;i<12;++i){check(chain.command(1,0),"M0 ONCE command queued");h.block();h.events();}
    check(conductor_active(h)==12,"M0 native direct ONCE retains twelve owners");
    check(chain.command(1,1),"M0 thirteenth reaches authoritative DSP admission");h.block();auto e=h.events();
    check(e.empty() && conductor_active(h)==12,"M0 thirteenth emits neither attack nor destructive release");
    h.eq("instance_error",2,"M0 native saturation explicitly diagnosed");
  }
}

static void m1_group_tests(const char *source) {
  {
    Host h(source);conductor_fixture(h);ChainMode chain(h.f,true,2);
    h.run("mem[PHRASE_GROUP_BASE]=7;mem[PHRASE_GROUP_BASE+1]=7;mem[MODE_BASE]=0;loop_len_samples=8192;");
    check(chain.command(1,0),"M1 grouped LOOP command queued");h.block();check(conductor_count(h.events(),144,48)==1,"M1 grouped LOOP attack");
    check(chain.command(1,1),"M1 ONCE replacing LOOP queued");h.block();auto e=h.events();
    check(conductor_count(e,128,48)==1 && conductor_count(e,144,72)==1,"M1 ONCE releases only old grouped LOOP");h.eq("mem[TRIG_BASE]",0,"M1 old LOOP stays stopped");
    check(chain.command(1,0),"M1 LOOP replacing ONCE queued");h.block();e=h.events();
    check(conductor_count(e,128,72)==1 && conductor_count(e,144,48)==1 && conductor_active(h)==0,"M1 LOOP releases old ONCE then attacks");
  }
  {
    Host h(source);conductor_fixture(h);ChainMode chain(h.f,true,2);
    h.run("mem[PHRASE_GROUP_BASE]=7;mem[INST_TRANSFORM_COUNT_BASE]=1;mem[INST_TRANSFORM_TYPE_BASE]=3;mem[INST_NOTE_MODE_BASE]=1;");
    check(chain.command(1,0),"M1 unsafe grouped source request queued");h.block();auto e=h.events();
    check(conductor_active(h)==0 && conductor_count(e,144,48)==0,"M1 grouped mono source cleanly refused before attack");h.eq("instance_error",3,"M1 unsafe group routing diagnosed");
  }
  {
    Host h(source);conductor_fixture(h);ChainMode chain(h.f,true,2);
    h.run("mem[PHRASE_GROUP_BASE]=7;mem[PHRASE_GROUP_BASE+1]=7;mem[PHRASE_GROUP_BASE+2]=8;clear_layer(2);store_event(2,0,144,80,99,0);store_event(2,4096,128,80,0,0);mem[LEN_BASE+2]=8192;mem[MODE_BASE+2]=1;");
    h.midi(176,64,127);h.events();h.midi(144,48,110);h.events();
    check(chain.command(1,0),"M1 first group source accepted");h.block();h.events();
    check(chain.command(1,2),"M1 unrelated group accepted");h.block();h.events();
    check(chain.command(1,1),"M1 replacement group source accepted");h.block();auto events=h.events();
    printf("M1 group replacement actual MIDI=%s active=%d\n",conductor_events(events).c_str(),conductor_active(h));
    check(conductor_active(h)==2,"M1 same-group old owner stops; unrelated group remains");
    for(const auto& event:events)check(!((event[0]&240)==176 && (event[1]>=120 || (event[1]==64 && event[2]==0))),"M1 group replacement never clears physical sustain or sends channel panic");
    check(conductor_count(events,144,72)==1 && conductor_count(events,128,48)==0 && conductor_count(events,128,80)==0,"M1 physical shared pitch and unrelated phrase never released");
    h.midi(128,48,0);check(conductor_count(h.events(),128,48)==1,"M1 physical owner still has exact release");
  }
  {
    Host h(source);conductor_fixture(h);ChainMode chain(h.f,true,2);
    h.run("mem[PHRASE_GROUP_BASE]=5;mem[PHRASE_GROUP_BASE+1]=5;");
    for(int i=0;i<12;++i){check(chain.command(1,0),"M1 same source allows independent occurrences");h.block();h.events();}
    check(chain.command(1,1),"M1 saturated request reaches native admission");h.block();auto e=h.events();
    check(conductor_active(h)==12 && e.empty(),"M1 capacity refusal cannot stop old group before reserving new admission");
    h.eq("instance_error",2,"M1 saturation retains explicit diagnostic");
  }
  {
    auto bytes=conductor_model(2);std::string text(bytes.begin(),bytes.end());
    text.replace(text.find("\"version\":1"),11,"\"version\":3");
    for(unsigned i=1;i<=4;++i){const std::string needle="\"slot\":"+std::to_string(i);auto pos=text.find(needle);text.insert(pos+needle.size(),",\"muteGroup\":7");}
    text.insert(text.size()-1,",\"movements\":[],\"ccRate\":25");bytes.assign(text.begin(),text.end());
    check(conductor::validDocument(bytes),"M1 real validator accepts explicit version 3");
    Host h(source);conductor_fixture(h);ChainMode chain(h.f,true,2);h.run("mem[PHRASE_GROUP_BASE]=7;mem[PHRASE_GROUP_BASE+1]=7;");
    conductor_install(h,bytes);h.midi(144,110,100);auto e=h.events();
    check(conductor_count(e,144,48)==1 && conductor_count(e,144,72)==0,"M1 intra-STEP smallest PHRASE ID wins");
    h.midi(128,110,0);h.events();h.midi(144,110,100);e=h.events();
    check(conductor_count(e,144,72)==1,"M1 next STEP min source is recomputed independently");
  }
}
