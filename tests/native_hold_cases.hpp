// PR #45 shared voice renderer, exercised through the real native chain adapter.
static void native_hold_tests(const char* source) {
  for(unsigned rate:{44100u,48000u,96000u}) for(unsigned block:{32u,128u,512u,8192u}) {
    Host h(source,false);ysfx_set_sample_rate(h.f,rate);ysfx_set_block_size(h.f,block);ysfx_init(h.f);
    h.run("slider9=1;slider5=0;panic_pending=0;mem[INST_TRANSFORM_COUNT_BASE]=0;clear_layer(0);mem[MODE_BASE]=2;mem[VEL_BASE]=1;store_event(0,0,144,60,100,0);store_event(0,16,144,64,90,0);store_event(0,32,128,60,0,0);store_event(0,48,128,64,0,0);");
    *NSEEL_VM_getramptr(h.f->vm.get(),unsigned(h.val("LEN_BASE")),nullptr)=std::max(128u,block*2);
    ChainMode c(h.f,true,2);check(c.command(1,0),"native HOLD PRESS admitted");
    int ons=0,offs=0;auto process=[&]() {
      ysfx_process_float(h.f,nullptr,nullptr,0,0,block);ysfx_midi_event_t e{};
      while(ysfx_receive_midi(h.f,&e)) if(e.size==3 && (e.data[1]==60 || e.data[1]==64)) {
        check(e.offset<block,"held events retain valid block timestamps");
        if((e.data[0]&240)==144&&e.data[2]>0)++ons;
        if((e.data[0]&240)==128 || ((e.data[0]&240)==144&&!e.data[2]))++offs;
      }
    };
    for(unsigned i=0;i<12;++i){c.tick(i*block,block,rate,true,120);process();}
    check(ons>=4 && offs>=4,"native HOLD repeats paired chord while held");
    check(c.command(4,0),"native RELEASE enters existing block mailbox");process();
    h.eq("mem[HOLD_ACTIVE_BASE]",0,"release clears held latch");
    h.eq("phrase_playing(0)",0,"release cancels repeating voice");
    int prior=ons;process();process();check(ons==prior,"no delayed regeneration after release");
    // PRESS and RELEASE accepted before the same block cannot lose either edge.
    check(c.command(1,0)&&c.command(4,0),"short native tap queues both edges");process();
    h.eq("phrase_playing(0)",0,"short tap leaves no active voice");
    check(c.command(1,0),"re-press after RELEASE");
    h.run("reset_note_runtime();");process();h.eq("phrase_playing(0)",0,"PANIC cancels queued PRESS");
    check(c.command(2,0)&&c.armed,"REC can arm with selected HOLD mode");
    check(c.command(1,0)&&!c.armed&&!c.recording,"HOLD PRESS disarms pending REC independently of mode");
    process();check(c.command(4,0),"release after cancelling arm");process();
    for(int edge=0;edge<16;++edge)check(c.command(1,0),"bounded held PRESS mailbox admission");
    check(c.command(4,0),"saturated mailbox never rejects RELEASE");process();
    h.eq("phrase_playing(0)",0,"overflow RELEASE cancels pending held voice");
    h.eq("native_hold_release_mask",0,"emergency release mask drains once");
    // Repeated source sustain must not leave stale ownership after RELEASE.
    h.run("clear_layer(0);mem[MODE_BASE]=2;store_event(0,0,176,64,127,0);store_event(0,0,144,60,100,0);store_event(0,64,128,60,0,0);");
    *NSEEL_VM_getramptr(h.f->vm.get(),unsigned(h.val("LEN_BASE")),nullptr)=std::max(128u,block*2);
    check(c.command(1,0),"source-sustain held phrase admitted");process();
    check(c.command(4,0),"source-sustain RELEASE");process();
    h.eq("mem[I_SUSTAIN_BASE]",0,"phrase RELEASE clears deferred-parameter sustain ownership");
    h.eq("mem[SW_PHRASE_SUSTAIN_BASE]",0,"phrase sustain owner cleared");
    h.eq("mem[SUSTAIN_REF_BASE]",0,"bounded phrase sustain references cleared");
    h.run("mem[INST_TRANSFORM_COUNT_BASE]=1;mem[INST_TRANSFORM_TYPE_BASE]=5;mem[INST_ARP_ENABLED_BASE]=1;");
    check(!c.command(1,0),"unsafe native held ARP routing is explicitly rejected");
  }
}
