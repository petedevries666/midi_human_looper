// Actual production EEL execution and output, not an ownership model simulation.
static void instance_ownership_tests(const char *source) {
  {
    Host h(source);conductor_fixture(h);
    h.run("a=phrase_admit_independent(0,0);ag=mem[instance_header(0)+1];");h.block();
    check(conductor_count(h.events(),144,48)==1,"independent bass emits actual attack");
    h.run("b=phrase_admit_independent(1,0);bg=mem[instance_header(1)+1];");h.block();auto output=h.events();
    check(conductor_count(output,144,72)==1 && conductor_count(output,128,48)==0,"independent second source does not choke bass");
    check(conductor_active(h)==2,"two independently owned sources remain active");
    check(h.val("a")>0 && h.val("b")>h.val("a"),"instance identities are monotonic, not voice indices");
    h.run("instance_request_stop(a,ag);");h.block();h.events();
    h.eq("mem[NOTE_REF_BASE+48]",0,"targeted stop releases bass ownership");
    h.eq("mem[NOTE_REF_BASE+72]",1,"targeted stop preserves another source");
    h.run("c=phrase_admit_independent(0,0);");h.block();h.events();
    h.eq("instance_request_stop(a,ag)",0,"stale ID/generation cannot stop replacement");
    h.eq("mem[NOTE_REF_BASE+48]",1,"replacement retains sounding note after stale stop");
    h.run("sw_action(0,SW_PANIC,0,0);");h.block();h.events();
    check(conductor_active(h)==0,"PANIC clears independent voices");
    h.eq("mem[instance_header(0)+5]",0,"PANIC retires owned attack records");
  }
  {
    Host h(source);conductor_fixture(h);
    h.run("clear_layer(1);store_event(1,0,144,48,88,0);store_event(1,4096,128,48,0,0);mem[LEN_BASE+1]=8192;a=phrase_admit_independent(0,0);ag=mem[instance_header(0)+1];");h.block();h.events();
    h.run("b=phrase_admit_independent(1,0);bg=mem[instance_header(1)+1];");h.block();h.events();
    // Stop inside DSP via queued test execution on the next render boundary.
    h.run("mem[LEN_BASE]=256;");h.block();auto output=h.events();
    check(conductor_count(output,128,48)==0,"same-pitch surviving instance suppresses premature Off");
    h.eq("mem[NOTE_REF_BASE+48]",1,"same-pitch owner count remains one");
    h.run("mem[LEN_BASE+1]=256;");h.block();output=h.events();
    check(conductor_count(output,128,48)==1,"last same-pitch owner emits release");
  }
  {
    Host h(source);conductor_fixture(h);
    h.run("mem[INST_TRANSFORM_COUNT_BASE]=1;mem[INST_TRANSFORM_TYPE_BASE]=1;mem[INST_TRANSPOSE_BASE]=12;mem[INST_OUT_BASE]=3;a=phrase_admit_independent(0,0);");h.block();auto output=h.events();
    check(conductor_count(output,144,60)==1 && output.back()[0]==146,"ledger observes transformed pitch and routed channel");
    // Adversarial direct write: release must use emission route even if a host
    // bypasses the normal parameter deferral guard.
    h.run("mem[INST_TRANSPOSE_BASE]=-12;mem[INST_OUT_BASE]=7;mem[LEN_BASE]=256;");h.block();output=h.events();
    bool exact=false,wrong=false;for(auto e:output){if(e[0]==130 && e[1]==60)exact=true;if((e[0]&240)==128 && (e[1]==36 || (e[0]&15)==6))wrong=true;}
    check(exact && !wrong,"release freezes exact emission destination/pitch across parameter changes");
  }
  {
    Host h(source);conductor_fixture(h);
    h.run("clear_layer(0);store_event(0,0,144,48,90,0);store_event(0,64,144,48,81,0);store_event(0,128,128,48,0,0);store_event(0,256,144,48,0,0);mem[LEN_BASE]=512;phrase_admit_independent(0,0);");
    h.block();auto output=h.events();check(conductor_count(output,144,48)==2,"repeated same-pitch attacks have separate FIFO records");
    h.block();output=h.events();check(conductor_count(output,128,48)==0,"first FIFO Off cannot cut second overlapping attack");
    h.block();output=h.events();check(conductor_count(output,128,48)==1,"velocity-zero On releases its corresponding FIFO attack");
    h.eq("mem[instance_header(0)+5]",0,"all FIFO records are returned after matching releases");
  }
  {
    Host h(source);conductor_fixture(h);
    h.run("mem[INST_TRANSFORM_COUNT_BASE]=1;mem[INST_TRANSFORM_TYPE_BASE]=5;mem[INST_ARP_ENABLED_BASE]=1;");
    h.eq("phrase_admit_independent(0,0)",0,"independent ARP route rejected, not silently bypassed");
    h.eq("instance_error",3,"unsafe-route refusal is explicit");
    h.block();check(conductor_count(h.events(),144,48)==0,"rejected instance cannot emit attacks");
    h.run("mem[INST_TRANSFORM_TYPE_BASE]=3;mem[INST_NOTE_MODE_BASE]=1;mem[INST_ARP_ENABLED_BASE]=0;");
    h.eq("phrase_admit_independent(0,0)",0,"independent mono route remains restricted");
  }
  {
    Host h(source);conductor_fixture(h);
    h.run("clear_layer(0);store_event(0,0,176,64,127,0);store_event(0,1,144,48,90,0);mem[LEN_BASE]=8192;clear_layer(1);store_event(1,0,176,64,127,0);store_event(1,1,144,72,90,0);mem[LEN_BASE+1]=8192;a=phrase_admit_independent(0,0);ag=mem[instance_header(0)+1];");h.block();h.events();
    h.run("b=phrase_admit_independent(1,0);bg=mem[instance_header(1)+1];");h.block();h.events();
    h.eq("mem[SUSTAIN_REF_BASE]",2,"two phrase owners retain independent pedal claims");
    h.run("instance_request_stop(a,ag);");h.block();auto output=h.events();
    bool pedalOff=false;for(auto e:output)if(e[0]==176 && e[1]==64 && e[2]==0)pedalOff=true;
    check(!pedalOff,"first owner STOP cannot release surviving pedal");
    h.eq("mem[SUSTAIN_REF_BASE]",1,"surviving pedal owner retained");
    h.midi(176,64,127);h.events();
    h.run("instance_request_stop(b,bg);");h.block();output=h.events();pedalOff=false;
    for(auto e:output)if(e[0]==176 && e[1]==64 && e[2]==0)pedalOff=true;
    check(!pedalOff,"last phrase STOP preserves held physical pedal");
    h.midi(176,64,0);output=h.events();pedalOff=false;
    for(auto e:output)if(e[0]==176 && e[1]==64 && e[2]==0)pedalOff=true;
    check(pedalOff,"physical pedal release eventually reaches MIDI destination");
  }
  {
    Host h(source);conductor_fixture(h);
    h.run("clear_layer(0);store_event(0,0,144,48,90,0);store_event(0,64,145,60,90,0);store_event(0,128,176,123,0,0);store_event(0,192,144,48,81,0);store_event(0,256,128,48,0,0);store_event(0,384,128,48,0,0);mem[LEN_BASE]=8192;phrase_admit_independent(0,0);");
    h.block();h.events();h.block();auto output=h.events();
    check(conductor_count(output,128,60)==0,"source channel-mode clear preserves other-channel owner");
    h.eq("mem[NOTE_REF_BASE+60]",1,"other source channel still owns routed pitch");
    h.block();output=h.events();check(conductor_count(output,128,48)==0,"pre-clear Off tombstone cannot cut post-clear attack");
    h.block();output=h.events();check(conductor_count(output,128,48)==1,"post-clear attack receives matching Off");
  }
  {
    Host h(source);conductor_fixture(h);
    h.run("mem[INST_TRANSFORM_COUNT_BASE]=1;mem[INST_TRANSFORM_TYPE_BASE]=2;mem[INST_RANGE_MODE_BASE]=3;mem[INST_RANGE_LOW_BASE]=64;mem[INST_RANGE_HIGH_BASE]=127;phrase_admit_independent(0,0);");h.block();auto output=h.events();
    check(conductor_count(output,144,48)==0,"filtered source attack emits no MIDI On");
    h.eq("mem[instance_header(0)+13]",0,"filtered attack has no emitted ownership");
    h.run("mem[LEN_BASE]=256;");h.block();output=h.events();
    check(conductor_count(output,128,48)==0,"filtered attack cleanup invents no MIDI Off");
  }
  {
    Host h(source);conductor_fixture(h);
    h.run("a=phrase_admit_independent(0,0);ag=mem[instance_header(0)+1];");h.block();h.events();
    h.run("instance_request_stop(a,ag);sw_action(0,SW_PANIC,0,0);b=phrase_admit_independent(1,0);");h.block();auto output=h.events();
    check(conductor_count(output,144,72)==1,"queued old STOP cannot cancel post-PANIC replacement");
    h.eq("mem[NOTE_REF_BASE+72]",1,"replacement owns emitted output after stale queue drain");
    h.run("instance_serial=9007199254740990;");h.eq("phrase_admit_independent(0,0)",0,"exhausted exact ID range rejects admission");
    h.eq("instance_error",5,"ID range refusal reported explicitly");
    h.eq("mem[NOTE_REF_BASE+72]",1,"ID refusal leaves surviving instance unchanged");
  }
  {
    Host h(source);conductor_fixture(h);
    h.run("a=phrase_admit_independent(1,0);");h.block();h.events();
    h.run("b=phrase_admit_independent(0,0);test_i=0;loop(INSTANCE_ROWS,instance_begin_attack(1,48);test_i+=1;);");
    h.eq("mem[instance_header(1)+5]",2048,"bounded records reserved before emission");
    h.block();auto output=h.events();
    check(conductor_count(output,144,48)==0,"no attack emitted without a release reservation");
    check(conductor_count(output,128,72)==0,"record exhaustion cannot cut another instance");
    h.eq("instance_error",4,"record exhaustion reported explicitly");
    h.eq("mem[NOTE_REF_BASE+72]",1,"unrelated sounding owner survives exhausted instance");
    h.eq("mem[instance_header(1)+5]",0,"exhausted instance retires its own bounded reservations");
  }
  {
    Host h(source);conductor_fixture(h);
    h.run("native_free_time=1;mem[MODE_BASE]=0;mem[TRIG_BASE]=1;mem[FREE_LOOP_ANCHOR_BASE]=0;play_sample_pos=0;state=STATE_PLAYING;");h.block();auto output=h.events();
    check(conductor_count(output,144,48)==1,"legacy free LOOP uses actual emitted-note ledger");
    h.eq("mem[instance_header(MAX_ONCE_VOICES)+13]",1,"legacy LOOP has its own owner, separate from voice slots");
    h.midi(144,48,100);h.events();
    h.run("free_loop_stop_mask=1;");h.block();output=h.events();
    check(conductor_count(output,128,48)==0,"legacy LOOP STOP preserves physical same-pitch owner");
    h.midi(128,48,0);output=h.events();check(conductor_count(output,128,48)==1,"physical release after LOOP STOP emits final Off");
    h.eq("mem[instance_header(MAX_ONCE_VOICES)+13]",0,"legacy LOOP ownership retired");
  }
  {
    Host h(source);conductor_fixture(h);
    h.run("clear_layer(0);store_event(0,0,176,64,127,0);store_event(0,1,144,48,90,0);mem[LEN_BASE]=8192;a=phrase_admit_independent(0,0);ag=mem[instance_header(0)+1];oldid=mem[I_IDS_BASE];");h.block();h.events();
    h.eq("mem[SUSTAIN_REF_BASE]",1,"pedal captures its emitted instrument destination");
    h.run("i_submit(2,0,oldid);");h.block();auto output=h.events();
    bool pedalOff=false;for(auto e:output)if(e[0]==176 && e[1]==64 && e[2]==0)pedalOff=true;
    check(pedalOff,"queued instrument deletion releases its last owned pedal destination");
    check(conductor_count(output,128,48)==1,"queued deletion emits owned note release");
    h.eq("mem[instance_header(0)+13]",0,"deleted destination leaves no ledger claim");
    h.eq("mem[SUSTAIN_REF_BASE]",0,"deleted destination leaves no pedal reference");
    h.run("i_submit(1,0,0);");h.block();h.events();
    check(h.eval("mem[I_IDS_BASE]!=oldid"),"replacement instrument never inherits deleted stable ID");
    h.run("instance_request_stop(a,ag);");h.block();output=h.events();
    check(conductor_count(output,128,48)==0,"old instance STOP cannot release replacement instrument");
  }
  for(unsigned secondChannel:{1u,2u}) {
    Host h(source);conductor_fixture(h);
    h.run("mem[INST_ENABLED_BASE+1]=1;mem[INST_OUT_BASE+1]="+std::to_string(secondChannel)+";clear_layer(0);store_event(0,0,176,64,127,0);store_event(0,1,144,48,90,0);mem[LEN_BASE]=8192;a=phrase_admit_independent(0,0);ag=mem[instance_header(0)+1];oldid=mem[I_IDS_BASE];");h.block();h.events();
    h.run("i_submit(2,0,oldid);");h.block();auto output=h.events();
    bool wrongPedal=false;for(auto e:output)if(e[0]==int(175+secondChannel) && e[1]==64 && e[2]==0)wrongPedal=true;
    check(!wrongPedal,"destination deletion preserves the remaining instrument pedal");
    h.eq("mem[SUSTAIN_REF_BASE+"+std::to_string(secondChannel-1)+"]",1,"surviving routed pedal retains exactly one source claim");
    h.eq("mem[instance_header(0)+13]",1,"deletion preserves one actual note destination");
    h.run("instance_request_stop(a,ag);");h.block();output=h.events();
    bool pedalOff=false,noteOff=false;for(auto e:output){if(e[0]==int(175+secondChannel) && e[1]==64 && e[2]==0)pedalOff=true;if(e[0]==int(127+secondChannel) && e[1]==48)noteOff=true;}
    check(pedalOff && noteOff,"final STOP releases surviving frozen note/pedal destination");
  }
  for(unsigned mode:{0u,2u}) {
    Host h(source);conductor_fixture(h);
    h.run("clear_layer(0);store_event(0,0,144,48,90,0);store_event(0,64,128,48,0,0);mem[LEN_BASE]=512;mem[MODE_BASE]="+std::to_string(mode)+";a=phrase_admit_independent(0,0);ag=mem[instance_header(0)+1];");
    int ons=0,offs=0;for(unsigned b=0;b<5;++b){h.block();auto output=h.events();ons+=conductor_count(output,144,48);offs+=conductor_count(output,128,48);}
    check(ons==2 && offs==2,"independent LOOP/HOLD repeats paired source content at its own boundary");
    h.eq("mem[MODE_BASE]",mode,"independent admission preserves persisted play mode");
    h.eq("mem[instance_header(0)]",h.val("a"),"repeating instance keeps identity across cycles");
    h.run("instance_request_stop(a,ag);");h.block();h.events();
    check(conductor_active(h)==0,"targeted STOP retires repeating independent instance");
  }
  {
    Host h(source);conductor_fixture(h);ysfx_set_midi_capacity(h.f,65536,false);
    h.run("clear_layer(0);test_j=0;loop(1024,store_event(0,0,144,48+test_j%12,90,0);store_event(0,4096,128,48+test_j%12,0,0);test_j+=1;);mem[LEN_BASE]=8192;test_j=0;loop(5,phrase_admit_independent(0,0);test_j+=1;);");
    h.block();auto output=h.events();unsigned ons=0;for(auto e:output)if((e[0]&240)==144 && e[2])++ons;
    unsigned claims=int(h.eval("test_j=0;test_n=0;loop(MAX_ONCE_VOICES,test_n+=mem[instance_header(test_j)+13];test_j+=1;);test_n;"));
    printf("OUTPUT CAPACITY attempted=5120 accepted=%u owned=%u error=%g panic=%g\n",ons,claims,h.val("instance_error"),h.val("panic_pending"));
    check(ons>0 && ons<5120 && ons==claims,"fixed output buffer owns only accepted attacks");
    h.eq("instance_error",6,"output buffer rejection reported distinctly from voice capacity");h.eq("panic_pending",1,"output rejection requests deferred existing PANIC");
    h.block();output=h.events();unsigned offs=0;for(auto e:output)if((e[0]&240)==128)++offs;
    check(offs>=2048 && conductor_active(h)==0,"fresh-buffer PANIC releases accepted notes and retires instances");
    unsigned emergency=0;for(auto e:output)if((e[0]&240)==176 && (e[1]==120 || e[1]==123) && !e[2])++emergency;
    check(emergency==32,"output failure emits bounded emergency channel cleanup, including stacked receivers");
    h.eq("mem[NOTE_REF_BASE+48]",0,"output overflow recovery leaves no ownership");
  }
  {
    Host h(source);conductor_fixture(h);ysfx_set_midi_capacity(h.f,65536,false);
    h.run("clear_layer(0);test_j=0;loop(1024,store_event(0,128,176,2,test_j%128,0);test_j+=1;);mem[LEN_BASE]=8192;clear_layer(1);store_event(1,0,144,60,90,0);store_event(1,129,128,60,0,0);mem[LEN_BASE+1]=8192;test_j=0;loop(5,phrase_admit_independent(0,0);test_j+=1;);phrase_admit_independent(1,0);");
    h.block();check(conductor_count(h.events(),144,60)==1,"note emits before subsequent full-buffer CC burst");
    h.block();auto output=h.events();check(conductor_count(output,128,60)==0,"fixture actually rejects the scheduled Off after CC burst");
    h.eq("instance_error",6,"failed release cannot silently abandon accepted output");
    h.eq("panic_pending",1,"failed release schedules bounded recovery");
    h.block();output=h.events();check(conductor_count(output,128,60)>=1,"existing PANIC eventually releases failed Off pitch");
    check(conductor_active(h)==0,"output recovery stops all burst instances explicitly");
  }
  for(unsigned type:{3u,5u}) {
    Host h(source);conductor_fixture(h);
    h.run("clear_layer(0);store_event(0,256,144,48,90,0);store_event(0,384,128,48,0,0);mem[LEN_BASE]=1024;phrase_admit_independent(0,0);");h.block();h.events();
    h.run("mem[INST_TRANSFORM_COUNT_BASE]=1;mem[INST_TRANSFORM_TYPE_BASE]="+std::to_string(type)+";mem[INST_NOTE_MODE_BASE]=1;mem[INST_ARP_ENABLED_BASE]=1;");h.block();auto output=h.events();
    check(conductor_count(output,144,48)==0 && conductor_active(h)==0,"late unsafe module activation retires independent admission before attack");
    h.eq("instance_error",3,"late unsafe transition is explicit, not an untracked continuation");
    h.eq("mem[engine_addr(ARP_HELD_COUNT_BASE,48)]",0,"rejected independent attack leaves no ARP held source");
  }
  for(unsigned rate:{44100u,48000u,96000u})for(unsigned frames:{128u,256u,512u,8192u}) {
    Host h(source);ysfx_set_sample_rate(h.f,rate);ysfx_set_block_size(h.f,frames);ysfx_init(h.f);conductor_fixture(h);
    h.run("clear_layer(0);store_event(0,0,144,48,90,0);store_event(0,"+std::to_string(frames-1)+",128,48,23,0);mem[LEN_BASE]="+std::to_string(frames+1)+";phrase_admit_independent(0,0);");
    ysfx_process_float(h.f,nullptr,nullptr,0,0,frames);
    ysfx_midi_event_t e{};int ons=0,offs=0;unsigned last=0;
    while(ysfx_receive_midi(h.f,&e)) {
      check(e.offset>=last,"owned events remain ordered across rates/buffer sizes");last=e.offset;
      if(e.size==3 && e.data[1]==48) {
        if((e.data[0]&240)==144 && e.data[2]>0){++ons;check(e.offset==0,"instance attack retains sample-zero offset");}
        if((e.data[0]&240)==128){++offs;check(e.offset==frames-1,"instance release retains last-sample offset");}
      }
    }
    check(ons==1 && offs==1,"one paired note at each sample-rate/buffer combination");
    h.eq("mem[instance_header(0)+13]",0,"no output ownership leaked at block boundary");
  }
  printf("PASS instance ownership actual EEL checks: %d\n",checks);
}
