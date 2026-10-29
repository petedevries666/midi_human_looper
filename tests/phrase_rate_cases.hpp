struct RateEdge {int kind,note;unsigned sample;};
static void rate_events(Host& h,unsigned frame,std::vector<RateEdge>& out){
  ysfx_midi_event_t e{};while(ysfx_receive_midi(h.f,&e))if(e.size==3){
    check(e.offset<128,"RATE MIDI timestamp remains inside callback");
    int kind=e.data[0]&240;if(kind==128||(kind==144&&e.data[2]==0))kind=128;
    if(kind==128||kind==144)out.push_back({kind,e.data[1],frame+e.offset});
  }
}
static void rate_fixture(Host& h,double rate){
  fixture(h,false);h.run("test_rate_input=0;");*ysfx_find_var(h.f,"test_rate_input")=rate;
  h.run("clear_layer(0);store_event(0,0,144,48,40,0);store_event(0,2560,128,48,0,0);mem[LEN_BASE]=4096;mem[NATIVE_PHRASE_RATE_BASE]=test_rate_input;");
}
static void phrase_rate_cases(const char* source){
  for(double rate:{.1,.5,1.,2.,16.}){
    Host h(source);rate_fixture(h,rate);trigger(h,false);std::vector<RateEdge> edges;rate_events(h,0,edges);
    h.eq("mem[VOICE_TIME_BASE]",1/rate,"RATE snapshots inverse speed on voice");
    h.run("mem[NATIVE_PHRASE_RATE_BASE]=8;");
    for(unsigned frame=128;frame<4096/rate+256;frame+=128){h.block();rate_events(h,frame,edges);}
    check(edges.size()==2&&edges[0].kind==144&&edges[0].note==48&&edges[0].sample==0&&edges[1].kind==128&&edges[1].note==48&&edges[1].sample==unsigned(std::llround(2560/rate)),"ONCE RATE preserves pitch and scales exact Note Off time despite later source edit");
    h.eq("mem[NOTE_REF_BASE+2*128+48]",0,"rated ONCE frees note owner");
  }
  for(double rate:{.1,.5,1.,2.,16.}){
    Host h(source);rate_fixture(h,rate);h.run("mem[MODE_BASE]=0;loop_len_samples=4096;b=sw_cfg(0);mem[b+11]=1;mem[b+SW_LIST]=0;sw_submit(0,0,0,0);");h.block();
    std::vector<RateEdge> edges;rate_events(h,0,edges);unsigned period=unsigned(std::llround(4096/rate));
    for(unsigned frame=128;frame<period+128;frame+=128){h.block();rate_events(h,frame,edges);}
    check(edges.size()==3&&edges[0].kind==144&&edges[0].sample==0&&edges[1].kind==128&&edges[1].sample==unsigned(std::llround(2560/rate))&&edges[2].kind==144&&edges[2].sample==period,"free LOOP RATE scales event and wrap times");
    h.run("b=sw_cfg(1);mem[b+14]=SW_STOP;sw_submit(1,0,0,0);");h.block();h.events();h.eq("mem[NOTE_REF_BASE+2*128+48]",0,"rated LOOP STOP frees note owner");
  }
  {
    Host h(source);rate_fixture(h,.5);auto doc=repeat_document(3);std::string text(doc.begin(),doc.end());
    auto at=text.find("\"slot\":1}");text.replace(at,9,"\"slot\":1,\"rate\":0.5}");
    const std::string old="\"overrides\":{\"playMode\":{\"mode\":\"OVERRIDE\",\"value\":\"ONCE\"}}";
    at=text.find(old);check(at!=std::string::npos,"RATE override fixture");
    text.replace(at,old.size(),"\"overrides\":{\"phrase_rate\":{\"mode\":\"OVERRIDE\",\"value\":2},\"phrase_time_decay\":{\"mode\":\"OVERRIDE\",\"value\":2}}");
    doc.assign(text.begin(),text.end());check(conductor::validDocument(doc),"RATE document valid");conductor_install(h,doc);
    for(int i=0;i<3;++i){trigger(h,true);h.events();h.eq("mem[VOICE_TIME_BASE+"+std::to_string(i)+"]",.5*std::pow(2.,i),"RATE composes with T.DEC for successive REPEAT admissions");h.eq("mem[NATIVE_PHRASE_RATE_BASE]",.5,"local RATE preserves source");}
    trigger(h,true);h.events();h.eq("mem[VOICE_TIME_BASE+3]",2,"following STEP inherits source RATE");
    h.eq("mem[VOICE_TIME_BASE]",.5,"older owner keeps its independent playback time");
  }
  {
    Host h(source);rate_fixture(h,2);h.run("mem[MODE_BASE]=0;loop_len_samples=4096;b=sw_cfg(0);mem[b+11]=1;mem[b+SW_LIST]=0;sw_submit(0,0,0,0);");h.block();h.events();
    h.run("overdub_layer=0;free_old_count=layer_count(0);free_old_length=mem[LEN_BASE];free_old_trigger=1;overdub_armed=1;overdub_wait_note=0;");
    for(int i=0;i<20&&h.eval("overdub_active")<.5;++i){h.block();h.events();}
    h.eq("overdub_active",1,"rated LOOP overdub starts at audible wrap");
    double start=h.eval("overdub_pos");
    uint8_t on[]={144,72,80};ysfx_midi_event_t e{};e.size=3;e.data=on;e.offset=32;check(ysfx_send_midi(h.f,&e),"queue rated overdub note");h.block();h.events();
    uint8_t off[]={128,72,0};e.data=off;e.offset=64;check(ysfx_send_midi(h.f,&e),"queue rated overdub release");h.block();h.events();
    h.eq("mem[layer_base(0,2)]",start+64,"overdub On stored in source time");
    h.eq("mem[layer_base(0,3)]",start+384,"overdub Off stored in source time");
    h.eq("mem[layer_base(0,1)]",2560,"existing recorded timestamps remain unchanged");
  }
  std::cout<<"PASS RATE: ONCE and LOOP timestamps, pitch, owner snapshots, STOP, T.DEC, REPEAT, inheritance and overdub alignment\n";
}
