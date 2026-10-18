// Production EEL phrase renderer/ownership. No substitute MIDI routing model.
static void phrase_output_tests(const char *source) {
  for (int policy=0;policy<=17;++policy) {
    Host h(source);conductor_fixture(h);
    h.run("clear_layer(0);mem[INST_OUT_BASE]=7;slider8=12;"
          "store_event(0,0,148,48,91,0);store_event(0,64,185,42,87,0);"
          "store_event(0,96,180,64,127,0);store_event(0,128,226,0,64,0);"
          "store_event(0,160,167,48,30,0);store_event(0,192,197,12,0,0);"
          "store_event(0,224,214,50,0,0);store_event(0,512,132,48,23,0);"
          "store_event(0,576,180,64,0,0);mem[LEN_BASE]=768;"
          "mem[phrase_output_addr(0)]="+std::to_string(policy)+";phrase_admit_independent(0,0);");
    std::vector<std::vector<int>> output;
    for(int block=0;block<7;++block){h.block();auto events=h.events();output.insert(output.end(),events.begin(),events.end());}
    int expected=policy==17?16:1;
    for(const auto &pair:std::vector<std::pair<int,int>>{{144,48},{128,48},{176,42},{224,0},{160,48},{192,12},{208,50}}){
      std::set<int> channels;int count=0;
      for(const auto &e:output)if((e[0]&240)==pair.first && e[1]==pair.second){++count;channels.insert(e[0]&15);}
      check(count==expected,"one channel-voice event per selected destination");
      if(policy>0 && policy<17)check(channels==std::set<int>{policy-1},"fixed PHRASE channel wins over Instrument/global output");
      if(policy==17)check(channels.size()==16,"ALL emits every MIDI channel once");
    }
    if(policy==0){
      for(const auto &e:output){int type=e[0]&240;int ch=type==144||type==128?4:type==176?(e[1]==42?9:4):type==224?2:type==160?7:type==192?5:6;
        check((e[0]&15)==ch,"ORIGINAL keeps each source event's recorded channel");}
    }
    int down=0,up=0;for(const auto &e:output)if((e[0]&240)==176 && e[1]==64){if(e[2])++down;else++up;}
    check(down==expected && up==expected,"sustain claims release on every emitted destination");
    h.eq("mem[layer_base(0,0)+1]",148,"recorded source status is unchanged");
    h.eq("mem[layer_base(0,7)+1]",132,"recorded source Note Off is unchanged");
    h.eq("mem[instance_header(0)+13]",0,"all emitted output claims released");
    h.eq("mem[instance_header(0)+9]",0,"all sustain claims released");
  }
  {
    Host h(source);conductor_fixture(h);
    h.run("mem[INST_OUT_BASE]=5;mem[phrase_output_addr(0)]=17;");
    h.midi(144,48,99);h.events();
    h.run("phrase_admit_independent(0,0);");h.block();auto attacks=h.events();
    check(conductor_count(attacks,144,48)==16,"ALL reserves one bounded record before sixteen attacks");
    h.run("mem[phrase_output_addr(0)]=2;instance_request_stop(mem[instance_header(0)],mem[instance_header(0)+1]);");h.block();auto releases=h.events();
    check(conductor_count(releases,128,48)==15,"phrase stop preserves physical owner on CH5");
    for(const auto &e:releases)if((e[0]&240)==128)check((e[0]&15)!=4,"no premature Note Off for held physical note");
    h.midi(128,48,0);releases=h.events();check(conductor_count(releases,128,48)==1 && releases[0][0]==132,"physical release cleans its actual remaining channel");
  }
  {
    Host h(source);conductor_fixture(h);
    h.run("mem[phrase_output_addr(0)]=17;phrase_admit_independent(0,0);");h.block();h.events();
    h.run("mem[phrase_output_addr(0)]=3;");
    std::vector<std::vector<int>> output;for(int i=0;i<33;++i){h.block();auto events=h.events();output.insert(output.end(),events.begin(),events.end());}
    check(conductor_count(output,128,48)==16,"policy edit cannot remap already emitted Note Offs");
    h.run("phrase_admit_independent(0,0);");h.block();output=h.events();
    check(conductor_count(output,144,48)==1 && output.back()[0]==146,"next trigger uses edited channel");
  }
  for(int mode:{0,2}) {
    Host h(source);conductor_fixture(h);
    h.run("clear_layer(0);store_event(0,0,144,48,90,0);store_event(0,64,128,48,0,0);mem[LEN_BASE]=512;mem[MODE_BASE]="+std::to_string(mode)+";mem[phrase_output_addr(0)]=17;a=phrase_admit_independent(0,0);ag=mem[instance_header(0)+1];");
    int on=0,off=0;for(int i=0;i<5;++i){h.block();auto output=h.events();on+=conductor_count(output,144,48);off+=conductor_count(output,128,48);}
    check(on==32 && off==32,"ALL LOOP/HOLD repeats sixteen correctly paired destinations");
    h.run("instance_request_stop(a,ag);");h.block();h.events();
    h.eq("mem[instance_header(0)+13]",0,"ALL LOOP/HOLD STOP leaves no owned outputs");
  }
  {
    Host h(source);conductor_fixture(h);
    h.run("mem[phrase_output_addr(0)]=17;mem[INST_TRANSFORM_COUNT_BASE]=1;mem[INST_TRANSFORM_TYPE_BASE]=5;mem[INST_ARP_ENABLED_BASE]=1;trigger_request=0;process_phrase_trigger(0,1);");
    h.eq("instance_error",3,"unsafe shared ARP ALL combination is explicitly refused");
    h.block();check(conductor_count(h.events(),144,48)==0,"refused unsafe ALL cannot emit an unowned attack");
  }
  {
    Host h(source);conductor_fixture(h);
    h.run("mem[phrase_output_addr(0)]=17;mem[phrase_output_addr(15)]=16;save_patch(1);"
          "mem[phrase_output_addr(0)]=2;mem[phrase_output_addr(15)]=0;save_patch(2);load_patch(1);");
    h.eq("phrase_output_policy(0)",17,"ALL survives patch bank save/load");
    h.eq("phrase_output_policy(15)",16,"last PHRASE channel survives patch bank save/load");
    h.run("sw_begin_edit(0,0);mem[phrase_output_addr(0)]=7;sw_commit_edit();");
    h.eq("phrase_output_policy(0)",7,"Smart Switch draft cannot overwrite phrase output");
  }
}
