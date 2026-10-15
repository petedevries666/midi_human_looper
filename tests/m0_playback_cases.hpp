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
