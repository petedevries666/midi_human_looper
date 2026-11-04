// Included after fixture/trigger: real native EEL, MIDI edges and compiler.
static std::vector<unsigned> repeat_document(int count,int mode=1,bool release=false,bool end=false){
  auto bytes=conductor_model(1,false,mode);std::string text(bytes.begin(),bytes.end());
  for(unsigned i=2;i<=4;++i){const auto old="\"sourceId\":\""+conductor_uuid(i)+"\"";size_t at;
    while((at=text.find(old))!=std::string::npos)text.replace(at,old.size(),"\"sourceId\":\""+conductor_uuid(1)+"\"");}
  const std::string transition="\"transition\":\"INHERIT\"";auto at=text.find(transition);
  text.replace(at,transition.size(),"\"repeat\":"+std::to_string(count)+",\"transition\":\""+(end?"END_OF_PHRASE":"INHERIT")+"\"");
  if(release){const std::string key="\"gesture\":\"INSTANT\"";text.replace(text.find(key),key.size(),key+",\"advance\":\"RELEASE\"");}
  bytes.assign(text.begin(),text.end());check(conductor::validDocument(bytes),"REPEAT document accepted");return bytes;
}
static void repeat_cases(const char* source){
  for(int mode:{0,1,2}){
    Host h(source);fixture(h,true,mode);h.run("mem[LEN_BASE]=8192;");conductor_install(h,repeat_document(3,mode));
    const int expected[]={0,0,0,1,2,3,0};
    for(unsigned i=0;i<7;++i){trigger(h,true);h.events();
      h.eq("mem[conductor_header(0)+3]",expected[i],"three presses share STEP, fourth advances; wrap restarts count");
      h.eq("mem[NATIVE_CONDUCTOR_REPEAT_BASE]",i<3?i+1:1,"one counter admission per PRESS");
      h.run("conductor_apply(0,0,1);conductor_apply(0,0,2);conductor_apply(0,0,3);");
      h.eq("mem[NATIVE_CONDUCTOR_REPEAT_BASE]",i<3?i+1:1,"HOLD LONG HOLD RELEASE consume no repetition");
    }
    h.run("sw_reset(0);");trigger(h,true);h.events();h.eq("mem[conductor_header(0)+3]",0,"RESET starts first STEP");
    h.eq("mem[NATIVE_CONDUCTOR_REPEAT_BASE]",1,"RESET restarts first repetition");
  }
  {
    Host h(source);fixture(h,true);h.run("mem[LEN_BASE]=8192;");conductor_install(h,repeat_document(3));
    trigger(h,true);h.events();h.run("i=0;loop(11,phrase_admit_independent(0,0);i+=1;);");h.block();h.events();
    check(conductor_active(h)==12,"REPEAT refusal fixture fills real voice pool");
    trigger(h,true);h.events();h.eq("mem[conductor_header(0)+4]",2,"capacity refusal remains explicit");
    h.eq("mem[NATIVE_CONDUCTOR_REPEAT_BASE]",1,"refused press consumes no repetition");
    h.eq("mem[conductor_header(0)+3]",0,"refusal preserves cursor");
  }
  {
    Host h(source);fixture(h,true);conductor_install(h,repeat_document(3,1,true));
    for(unsigned i=0;i<4;++i){trigger(h,true);h.events();h.eq("mem[NATIVE_CONDUCTOR_REPEAT_BASE]",i<3?i:3,"RELEASE mode press only prepares target");
      h.midi(128,110,0);h.events();h.eq("mem[conductor_header(0)+3]",i<3?0:1,"RELEASE selects repeated destination");
      h.eq("mem[NATIVE_CONDUCTOR_REPEAT_BASE]",i<3?i+1:1,"RELEASE admission counts once");}
  }
  {
    Host h(source);fixture(h,true);conductor_install(h,repeat_document(2,1,false,true));
    trigger(h,true);h.events();trigger(h,true);h.events();
    h.eq("mem[CONDUCTOR_GESTURE_BASE+3]",1,"end-of-phrase queues repeated STEP, not next STEP");
    h.eq("mem[NATIVE_CONDUCTOR_REPEAT_BASE]",1,"queued entry has not consumed repetition");
    for(int i=0;i<12&&h.eval("mem[NATIVE_CONDUCTOR_REPEAT_BASE]")<2;++i){h.block();h.events();}
    h.eq("mem[NATIVE_CONDUCTOR_REPEAT_BASE]",2,"phrase boundary admits second repetition");
    h.eq("mem[conductor_header(0)+3]",0,"boundary keeps repeated cursor");
  }
  std::cout<<"PASS native REPEAT: modes, MIDI PRESS/RELEASE, phase isolation, refusal, RESET, wrap and phrase boundary\n";
}
