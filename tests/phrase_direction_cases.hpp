static void direction_fixture(Host& h,int direction,int mode=1){
 fixture(h,false,mode);
 h.run("clear_layer(0);store_event(0,0,144,60,40,0);store_event(0,127,128,60,17,0);store_event(0,256,144,67,90,0);store_event(0,1023,128,67,23,0);mem[LEN_BASE]=1024;mem[MODE_BASE]="+std::to_string(mode)+";mem[NATIVE_DIRECTION_SOURCE]="+std::to_string(direction)+";loop_len_samples=1024;");
}
static void phrase_direction_cases(const char* source){
 {
  Host h(source);direction_fixture(h,1);trigger(h,false);
  std::vector<RateEdge> edges;rate_events(h,0,edges);
  for(unsigned t=128;t<1152;t+=128){h.block();rate_events(h,t,edges);}
  check(edges.size()==4,"REVERSE emits exactly two balanced notes");
  check(edges[0].kind==144&&edges[0].note==67&&edges[0].sample==0,"REVERSE starts with final note");
  check(edges[1].kind==128&&edges[1].note==67&&edges[1].sample==767,"REVERSE keeps long note duration");
  check(edges[2].kind==144&&edges[2].note==60&&edges[2].sample==896,"REVERSE mirrors short note position");
  check(edges[3].kind==128&&edges[3].note==60&&edges[3].sample==1023,"REVERSE keeps short note duration");
  h.eq("mem[layer_base(0,0)]",0,"REVERSE never rewrites source timestamps");
  h.eq("mem[layer_base(0,2)+3]",90,"REVERSE never rewrites source velocity");
  h.eq("mem[NOTE_REF_BASE+2*128+60]+mem[NOTE_REF_BASE+2*128+67]",0,"REVERSE frees all note owners");
 }
 {
  Host h(source);direction_fixture(h,2);h.run("mem[NATIVE_PHRASE_PLAY_MODE_BASE]=4;");
  for(int pass=0;pass<3;++pass){trigger(h,false);auto e=h.events();check(bass_count(e,146,pass%2?67:60)==1,"PING-PONG RETRIGGER alternates each successful press");for(int n=0;n<9;++n){h.block();h.events();}}
  h.run("phrase_toggle_stop(0,0);");h.block();h.events();trigger(h,false);check(bass_count(h.events(),146,60)==1,"scoped STOP resets source PING-PONG");
  h.run("reset_note_runtime();");trigger(h,false);check(bass_count(h.events(),146,60)==1,"STOP/PANIC resets PING-PONG to forward");
 }
 {
  Host h(source);direction_fixture(h,2,0);h.run("native_hold_enqueue(0,2);");h.block();
  std::vector<RateEdge> edges;rate_events(h,0,edges);
  for(unsigned t=128;t<2176;t+=128){h.block();rate_events(h,t,edges);}
  check(edges.size()>=9,"PING-PONG LOOP produces successive complete cycles");
  check(edges[0].note==60&&edges[0].sample==0&&edges[4].note==67&&edges[4].sample==1024&&edges[8].note==60&&edges[8].sample==2048,"direct LOOP alternates direction at cycle boundaries");
 }
 {
  Host h(source);direction_fixture(h,1);h.run("clear_layer(0);store_event(0,0,144,60,40,0);mem[LEN_BASE]=1024;");
  trigger(h,false);check(h.events().empty()&&conductor_active(h)==0,"unbalanced source is refused without starting a stuck note");
  direction_fixture(h,2,2);trigger(h,false);check(h.events().empty()&&conductor_active(h)==0,"PING-PONG HOLD is explicitly unsupported");
 }
 {
  Host h(source);direction_fixture(h,1);h.run("clear_layer(0);store_event(0,0,176,64,127,0);store_event(0,10,144,60,70,0);store_event(0,100,128,60,0,0);store_event(0,200,176,64,0,0);mem[LEN_BASE]=256;native_reverse_prepare(0);b=native_direction_event(0,0,1);");
  h.eq("mem[b+3]",127,"REVERSE pedal release becomes pedal press");
  h.run("b=native_direction_event(0,3,1);");h.eq("mem[b+3]",0,"REVERSE pedal press becomes pedal release");
 }
 {
  Host h(source);direction_fixture(h,0);auto doc=repeat_document(3);std::string text(doc.begin(),doc.end());
  const std::string old="\"overrides\":{\"playMode\":{\"mode\":\"OVERRIDE\",\"value\":\"ONCE\"}}";
  auto at=text.find(old);check(at!=std::string::npos,"direction block fixture");
  text.replace(at,old.size(),"\"overrides\":{\"playMode\":{\"mode\":\"OVERRIDE\",\"value\":\"ONCE\"},\"direction\":{\"mode\":\"OVERRIDE\",\"value\":\"REVERSE\"}}");
  doc.assign(text.begin(),text.end());check(conductor::validDocument(doc),"Conductor direction override validates");conductor_install(h,doc);
  trigger(h,true);check(bass_count(h.events(),146,67)==1,"Conductor local REVERSE affects actual MIDI");
  h.eq("mem[NATIVE_DIRECTION_SOURCE]",0,"local direction restores shared source");
 }
 std::cout<<"PASS non-destructive phrase REVERSE, PING-PONG, pedal reversal and Conductor overrides\n";
}
