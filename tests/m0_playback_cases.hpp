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
