// Real production routing: two instruments share phrase input, only one has BASS.
static int bass_count(const std::vector<std::vector<int>>& events,int status,int note){
  int n=0;for(const auto &e:events)if(e.size()==3&&e[0]==status&&e[1]==note)++n;return n;
}
static void bass_fixture(Host& h,int policy){
  fixture(h,false);
  h.run("mem[INST_ENABLED_BASE+1]=1;mem[INST_IN_BASE+1]=0;mem[INST_OUT_BASE]=1;mem[INST_OUT_BASE+1]=3;mem[INST_LEVEL_BASE+1]=127;"
        "mem[INST_TRANSFORM_COUNT_BASE]=1;mem[INST_TRANSFORM_TYPE_BASE]=3;mem[TF_PRIMARY_IDS+2]=11;mem[INST_NOTE_MODE_BASE]=1;"
        "mem[INST_TRANSFORM_COUNT_BASE+1]=0;"
        "clear_layer(0);store_event(0,0,144,45,80,0);store_event(0,0,144,52,80,0);store_event(0,12000,128,45,0,0);store_event(0,12000,128,52,0,0);mem[LEN_BASE]=16384;mem[MODE_BASE]=2;"
        "clear_layer(1);store_event(1,0,144,33,80,0);store_event(1,4096,128,33,0,0);mem[LEN_BASE+1]=8192;mem[MODE_BASE+1]=1;"
        "clear_layer(2);store_event(2,0,144,44,80,0);store_event(2,0,144,51,80,0);store_event(2,8192,128,44,0,0);store_event(2,8192,128,51,0,0);mem[LEN_BASE+2]=16384;mem[MODE_BASE+2]=2;"
        "j=0;loop(3,mem[DECAY_BASE+j]=1;mem[VEL_BASE+j]=1;mem[PHRASE_GROUP_BASE+j]=0;j+=1;);"
        "mem[NATIVE_BASS_POLICY_BASE+1]=mem[I_IDS_BASE];mem[NATIVE_BASS_POLICY_BASE+2]=11;mem[NATIVE_BASS_POLICY_BASE]="+std::to_string(policy)+";");
  h.events();
}
static std::vector<std::vector<int>> bass_admit(Host& h,int source){
  h.run("phrase_admit_independent("+std::to_string(source)+",0);");h.block();return h.events();
}
static void bass_policy_cases(const char* source){
  for(int policy:{0,1,2}){
    Host h(source);bass_fixture(h,policy);auto first=bass_admit(h,0);
    check(bass_count(first,144,45)==1&&bass_count(first,146,45)==1,"HOLD chord initially reaches BASS and piano");
    int bass=0,piano=0;for(int repeat=0;repeat<3;++repeat){auto e=bass_admit(h,1);bass+=bass_count(e,144,33);piano+=bass_count(e,146,33);}
    check(piano==3,"ONCE repeated piano attacks remain intact under every BASS policy");
    check(bass==(policy==0?1:policy==1?3:0),"GLOBAL keeps old gate, LATEST reattacks, HOLD-only excludes ONCE");
    if(policy==2)h.eq("mem[MONO_ACTIVE_NOTE_BASE]",45,"ignored ONCE cannot disturb held bass");
    auto next=bass_admit(h,2);
    check(bass_count(next,146,44)==1,"next HOLD always reaches piano immediately");
    check(bass_count(next,144,44)==(policy?1:0),"new policies remove older ONCE masking without changing GLOBAL");
    if(policy){
      for(int n=0;n<34;++n){h.block();auto e=h.events();check(bass_count(e,128,44)==0,"older ONCE Off cannot cut newer HOLD bass");}
      h.eq("mem[MONO_ACTIVE_NOTE_BASE]",44,"new HOLD owns the bass after older ONCE expires");
      h.run("instance_stop_voice(4,0);");h.block();h.events();
      h.eq("mem[MONO_ACTIVE_NOTE_BASE]",-1,"ending latest HOLD never resurrects older HOLD");
    }
    h.run("panic_pending=1;");h.block();h.events();h.eq("mem[NOTE_REF_BASE+44]",0,"PANIC frees selected bass output");
    h.eq("mem[NATIVE_BASS_OWNER_BASE]",0,"PANIC resets selected phrase priority");
    h.eq("mem[INST_NOTE_MODE_BASE]",1,"BASS policy preserves enum/controller mapping value");
  }
  {
    Host h(source);bass_fixture(h,2);
    h.run("mem[MODE_BASE+1]=0;");auto e=bass_admit(h,1);
    check(bass_count(e,144,33)==0&&bass_count(e,146,33)==1,"HOLD-only also excludes LOOP phrase attacks, piano unchanged");
    h.midi(144,40,90);e=h.events();check(bass_count(e,144,40)==1,"HOLD-only permits direct keyboard notes");
    h.midi(128,40,0);e=h.events();check(bass_count(e,128,40)==1,"direct keyboard release remains balanced");
  }
  {
    Host h(source);bass_fixture(h,2);h.run("mem[TF_PRIMARY_IDS+2]=12;");auto e=bass_admit(h,1);
    check(bass_count(e,144,33)==1,"deleted/recreated module does not inherit stale BASS policy");
  }
  std::cout<<"PASS BASS policies: legacy GLOBAL, latest phrase, HOLD-only, repeat reattack, old Off, source isolation, live MIDI and PANIC\n";
}
