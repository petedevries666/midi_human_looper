// Actual production compiler, existing Smart Switch clock, full DSP and MIDI.
static std::vector<unsigned> m2_model() {
  auto bytes=conductor_model(2);std::string s(bytes.begin(),bytes.end());
  std::string needle="\"sourceId\":\""+conductor_uuid(2)+"\",\"overrides\":{";
  auto at=s.find(needle);check(at!=std::string::npos,"M2 held layer fixture reference");
  s.insert(at+needle.size(),"\"trigger\":{\"mode\":\"OVERRIDE\",\"value\":\"HOLD\"},");
  bytes.assign(s.begin(),s.end());check(conductor::validDocument(bytes),"M2 uses existing persisted HOLD override");return bytes;
}
static void m2_gesture_tests(const char *source) {
  for(unsigned rate:{44100u,48000u,96000u})for(unsigned frames:{128u,256u,512u,8192u})for(int release:{-1,0,1}) {
    Host h(source,false);ysfx_set_sample_rate(h.f,rate);ysfx_set_block_size(h.f,frames);ysfx_init(h.f);
    conductor_fixture(h);ChainMode chain(h.f,true,2);conductor_install(h,m2_model());
    h.run("mem[sw_cfg(0)+8]=250;i=0;loop(4,clear_layer(i);store_event(i,0,144,i==0?48:i==1?72:76+i,100,0);store_event(i,srate,128,i==0?48:i==1?72:76+i,0,0);mem[LEN_BASE+i]=2*srate;mem[MODE_BASE+i]=1;mem[DECAY_BASE+i]=1;i+=1;);");
    auto input=[&](unsigned st,unsigned offset){uint8_t data[]={uint8_t(st),110,uint8_t(st==144?127:0)};ysfx_midi_event_t e{};e.offset=offset;e.size=3;e.data=data;check(ysfx_send_midi(h.f,&e),"M2 actual timed footswitch input");};
    const unsigned press=17,threshold=press+unsigned(std::ceil(rate*.25));
    unsigned position=0;std::vector<unsigned> bass,held;unsigned bassOff=0;
    for(unsigned block=0;position<threshold+2*frames;++block,position+=frames){
      if(!block)input(144,press);
      // -1: remain pressed; 0: release one sample before; 1: exact threshold.
      if(release>=0){unsigned at=threshold-(release==0);if(at>=position&&at<position+frames)input(128,at-position);}
      ysfx_process_float(h.f,nullptr,nullptr,0,0,frames);
      ysfx_midi_event_t event{};while(ysfx_receive_midi(h.f,&event)){
        if(event.size!=3)continue;auto d=event.data;
        if((d[0]&240)==144&&d[2]>0){if(d[1]==48)bass.push_back(position+event.offset);if(d[1]==72)held.push_back(position+event.offset);}
        if((d[0]&240)==128&&d[1]==48)++bassOff;
      }
    }
    check(bass==std::vector<unsigned>{press},"M2 PRESS bass immediate, never delayed or restarted at HOLD");
    check(release==0?held.empty():held==std::vector<unsigned>{threshold},"M2 HOLD exact threshold / early release cancels / equality admits");
    check(bassOff==0,"M2 HOLD/RELEASE does not stop PRESS phrase");
    printf("M2 MIDI rate=%u block=%u release=%d PRESS=%u HOLD=%d expected=%u\n",rate,frames,release,bass[0],held.empty()?-1:int(held[0]),threshold);
  }
  {
    Host h(source);conductor_fixture(h);ChainMode chain(h.f,true,2);conductor_install(h,m2_model());
    h.run("mem[sw_cfg(0)+8]=250;");h.midi(144,110,127);h.events();
    h.midi(144,110,127);check(h.events().empty(),"M2 repeated Note On while held cannot advance STEP");
    h.eq("mem[conductor_header(0)+3]",0,"M2 duplicate PRESS retains STEP");
    h.run("sw_stop_phrases();");h.block();h.events();for(unsigned j=0;j<120;++j){h.block();check(conductor_count(h.events(),144,72)==0,"M2 STOP ALL invalidates pending HOLD");}
    check(conductor_active(h)==0,"M2 STOP leaves no instances");
  }
  {
    Host h(source);conductor_fixture(h);ChainMode chain(h.f,true,2);conductor_install(h,m2_model());
    h.run("sw_submit(0,0,0,0);");h.block();check(conductor_count(h.events(),144,48)==1,"M2 TEST TAP actual PRESS MIDI");
    h.run("sw_submit(0,0,2,0);");h.block();check(conductor_count(h.events(),144,72)==1,"M2 TEST HOLD actual selected STEP MIDI");
    h.run("sw_submit(0,0,2,0);");h.block();check(h.events().empty(),"M2 TEST HOLD is single admission per PRESS");
    h.eq("mem[conductor_header(0)+3]",0,"M2 TEST HOLD never advances STEP");
  }
}
