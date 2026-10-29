static int pitch_quantize_expected(int note,int mask,int direction=0){note=std::max(0,std::min(127,note));int best=-1,distance=1000;for(int n=0;n<128;++n)if(mask&(1<<(n%12)))if(std::abs(n-note)<distance||(direction>0&&std::abs(n-note)==distance)){best=n;distance=std::abs(n-note);}return best;}
static std::string random_layer_json(bool fixed=false,bool hold=false){
 std::ostringstream s;s<<"{\"version\":1,\"sources\":[";
 for(unsigned i=0;i<3;++i){if(i)s<<',';s<<"{\"id\":\""<<conductor_uuid(i+1)<<"\",\"type\":\"PHRASE\",\"slot\":"<<i+1<<'}';}
 s<<"],\"switches\":[{\"switchId\":1,\"traversal\":\"SEQUENTIAL\",\"transition\":\"IMMEDIATE\",\"gesture\":\"INSTANT\",\"steps\":[{\"id\":\""<<conductor_uuid(50)<<"\",\"transition\":\"INHERIT\",\"layerSelection\":\"RANDOM_NO_REPEAT\",\"layers\":[";
 for(unsigned i=0;i<3;++i){if(i)s<<',';s<<"{\"id\":\""<<conductor_uuid(100+i)<<"\""<<(fixed&&i==0?",\"selectionRole\":\"FIXED\"":"")<<",\"block\":{\"id\":\""<<conductor_uuid(200+i)<<"\",\"type\":\"PHRASE\",\"sourceId\":\""<<conductor_uuid(i+1)<<"\",\"overrides\":{\"playMode\":{\"mode\":\"OVERRIDE\",\"value\":\"ONCE\"}";
  if(hold&&i>0)s<<",\"trigger\":{\"mode\":\"OVERRIDE\",\"value\":\"HOLD\"}";
  s<<"}}}";
 }s<<"]}]}]}";return s.str();
}
static void phrase_randomization_cases(const char* source){
 for(auto test:std::vector<std::vector<int>>{{60,1,62},{62,-1,60},{61,0,60},{60,-1,60},{127,24,122},{0,-24,0}}){
  Host h(source);fixture(h,false);h.run("clear_layer(0);store_event(0,0,144,"+std::to_string(test[0])+",90,0);store_event(0,640,128,"+std::to_string(test[0])+",0,0);mem[LEN_BASE]=1024;mem[NATIVE_RANDOM_SOURCE+3]=1;mem[NATIVE_RANDOM_SOURCE+4]="+std::to_string(test[1])+";mem[NATIVE_RANDOM_SOURCE+5]="+std::to_string(test[1])+";mem[NATIVE_RANDOM_SOURCE+6]=5;");trigger(h,false);check(bass_count(h.events(),146,test[2])==1,"nearest allowed pitch resolves ties by transposition direction and clamps MIDI bounds");for(int i=0;i<10;++i){h.block();h.events();}h.eq("mem[NOTE_REF_BASE+2*128+"+std::to_string(test[2])+"]",0,"quantized Note Off releases the actual pitch");
 }
 {
  Host h(source);fixture(h,false);h.run("clear_layer(0);store_event(0,0,144,60,90,0);store_event(0,0,144,61,90,0);store_event(0,384,128,60,0,0);store_event(0,640,128,61,0,0);mem[LEN_BASE]=1024;mem[NATIVE_RANDOM_SOURCE+3]=1;mem[NATIVE_RANDOM_SOURCE+4]=0;mem[NATIVE_RANDOM_SOURCE+5]=0;mem[NATIVE_RANDOM_SOURCE+6]=1;");trigger(h,false);check(bass_count(h.events(),146,60)==2,"two source notes may quantize to one output pitch");h.eq("mem[NOTE_REF_BASE+2*128+60]",2,"quantized collision retains both owners");for(int n=0;n<3;++n){h.block();h.events();}h.eq("mem[NOTE_REF_BASE+2*128+60]",1,"first quantized release cannot cut the second source note");for(int n=0;n<5;++n){h.block();h.events();}h.eq("mem[NOTE_REF_BASE+2*128+60]",0,"last quantized release frees the shared pitch");
 }
 {
  Host h(source);fixture(h,false);h.run("native_random_seed=2147483646;native_random_begin();");
  long long expected=2147483646LL;for(int n=0;n<64;++n){expected=(expected*16807)%2147483647;h.run("test_draw=native_random_draw();");h.eq("native_random_work",double(expected),"Park-Miller sequence matches exactly on ARM and x86");check(h.eval("test_draw")>0&&h.eval("test_draw")<1,"random draw stays inside the open unit interval");}
 }
 {
  Host h(source);fixture(h,false);h.run("mem[NATIVE_RANDOM_SOURCE+3]=1;mem[NATIVE_RANDOM_SOURCE+4]=-1;mem[NATIVE_RANDOM_SOURCE+5]=-1;mem[NATIVE_RANDOM_SOURCE+6]=2048;");trigger(h,false);check(bass_count(h.events(),146,47)==1,"negative semitone palette uses mathematical pitch classes");
 }
 {
  Host h(source);fixture(h,false);h.run("clear_layer(4);store_event(4,0,144,48,90,0);store_event(4,0,144,51,90,0);store_event(4,0,144,54,90,0);store_event(4,0,144,56,90,0);store_event(4,640,128,48,0,0);store_event(4,640,128,51,0,0);store_event(4,640,128,54,0,0);store_event(4,640,128,56,0,0);mem[LEN_BASE+4]=1024;mem[MODE_BASE+4]=1;mem[PHRASE_GROUP_BASE+4]=0;mem[NATIVE_RANDOM_SOURCE+4*8+3]=1;mem[NATIVE_RANDOM_SOURCE+4*8+4]=0;mem[NATIVE_RANDOM_SOURCE+4*8+5]=12;mem[NATIVE_RANDOM_SOURCE+4*8+6]=3925;native_random_seed=2147483646;");
  int previous=-1;for(int n=0;n<10;++n){h.run("trigger_request=4;");h.block();auto e=h.events();int delta=int(h.eval("mem[NATIVE_RANDOM_PITCH_LAST+4]"));check(delta>=0&&delta<=12&&delta!=previous,"PHRASE 05 chord draws a different offset inside the full requested range at every successful admission");std::map<int,int> expected;for(int note:{48,51,54,56})++expected[pitch_quantize_expected(note+delta,3925,delta)];for(auto pair:expected)check(bass_count(e,146,pair.first)==pair.second,"each transposed note is quantized to the nearest checked class");previous=delta;for(int k=0;k<10;++k){h.block();h.events();}}
  h.run("mem[NATIVE_RANDOM_SOURCE+4*8+6]=0;test_seed=native_random_seed;trigger_request=4;");h.block();h.events();h.eq("mem[NATIVE_RANDOM_PITCH_LAST+4]",previous,"refused pitch preserves last admitted history");h.eq("native_random_seed",h.eval("test_seed"),"refused pitch preserves random stream");
 }
 {
  Host h(source);fixture(h,false);h.run("mem[NATIVE_RANDOM_SOURCE+3]=1;mem[NATIVE_RANDOM_SOURCE+4]=-12;mem[NATIVE_RANDOM_SOURCE+5]=12;mem[NATIVE_RANDOM_SOURCE+6]=1;native_random_seed=1;");
  trigger(h,false);auto e=h.events();check(bass_count(e,146,36)==1,"RANDOM PITCH applies its offset then snaps to the checked pitch class");
  for(int n=0;n<10;++n){h.block();h.events();}h.eq("mem[NOTE_REF_BASE+2*128+36]",0,"random pitch release follows actual admitted pitch");
 }
 {
  Host h(source);fixture(h,false);h.run("mem[NATIVE_PHRASE_PLAY_MODE_BASE]=4;mem[NATIVE_RANDOM_SOURCE+3]=1;mem[NATIVE_RANDOM_SOURCE+4]=0;mem[NATIVE_RANDOM_SOURCE+5]=0;mem[NATIVE_RANDOM_SOURCE+6]=4095;native_random_seed=12345;");
  trigger(h,false);h.events();h.eq("native_random_seed",12345,"single legal transposition consumes no random draw");
  h.run("mem[NATIVE_RANDOM_SOURCE+6]=0;test_seed=native_random_seed;");trigger(h,false);
  check(h.events().empty()&&conductor_active(h)==1,"no legal pitch refuses RETRIGGER without cutting the previous occurrence");
  h.eq("native_random_seed",12345,"refused pitch consumes no random draw");h.eq("instance_error",20,"empty palette has an explicit diagnostic");
 }
 {
  Host h(source);fixture(h,false);h.run("clear_layer(0);store_event(0,0,144,60,90,0);store_event(0,900,128,60,23,0);mem[LEN_BASE]=1024;mem[NATIVE_RANDOM_SOURCE]=1;mem[NATIVE_RANDOM_SOURCE+1]=1;native_random_seed=65536;");
  trigger(h,false);std::vector<RateEdge> edges;rate_events(h,0,edges);unsigned start=unsigned(h.eval("mem[NATIVE_RANDOM_STATE]"));
  check(start>400&&start<700,"FREE start is drawn inside the configured percentage window");
  for(unsigned t=128;t<1152;t+=128){h.block();rate_events(h,t,edges);}
  check(edges.size()==2&&edges[0].kind==144&&edges[0].sample==0&&edges[1].kind==128&&edges[1].sample+start==900,"FREE reconstructs a crossing note with its remaining duration");
  check(conductor_active(h)==0,"jittered ONCE ends at its shortened END");h.eq("mem[layer_base(0,1)]",900,"START JITTER leaves recorded MIDI unchanged");
 }
 {
  Host h(source);fixture(h,false);h.run("clear_layer(0);store_event(0,0,144,60,90,0);store_event(0,100,176,64,127,0);store_event(0,400,128,60,0,0);store_event(0,900,176,64,0,0);mem[LEN_BASE]=1024;mem[NATIVE_RANDOM_SOURCE]=1;mem[NATIVE_RANDOM_SOURCE+1]=1;native_random_seed=65536;");
  trigger(h,false);auto e=h.events();
  if(e.size()<3||e[0]!=std::vector<int>({178,64,127}))std::cerr<<"prefix MIDI: "<<conductor_events(e)<<"\n";
  check(e.size()>=3&&e[0]==std::vector<int>({178,64,127})&&e[1][0]==146&&e[2][0]==130,"FREE recreates sustain before resuming an already released key");
  int offs=0;for(int n=0;n<10;++n){h.block();for(auto x:h.events())offs+=x==std::vector<int>({178,64,0});}
  check(offs==1&&conductor_active(h)==0,"reconstructed sustain has its real later release");
 }
 {
  Host h(source);direction_fixture(h,1);h.run("mem[NATIVE_RANDOM_SOURCE]=1;native_random_seed=65536;");trigger(h,false);auto e=h.events();
  double start=h.eval("mem[NATIVE_RANDOM_STATE]");check(start==0||start==896,"SUR NOTE chooses an attack in the effective reverse direction");
  check(bass_count(e,146,start==0?67:60)>=1,"reverse onset jitter emits a real selected attack");
 }
 {
  Host h(source);fixture(h,true);auto doc=conductor_model(1,false,1);std::string text(doc.begin(),doc.end());
  for(unsigned i=2;i<=4;++i){const auto old="\"sourceId\":\""+conductor_uuid(i)+"\"";size_t at;while((at=text.find(old))!=std::string::npos)text.replace(at,old.size(),"\"sourceId\":\""+conductor_uuid(1)+"\"");}
  auto at=text.find("\"slot\":1}");check(at!=std::string::npos,"Conductor pitch source fixture");text.replace(at,9,"\"slot\":1,\"randomPitch\":{\"enabled\":1,\"low\":0,\"high\":12,\"notes\":4095}}");
  doc.assign(text.begin(),text.end());conductor_install(h,doc);int previous=-1;
  for(int pass=0;pass<8;++pass){trigger(h,true);auto e=h.events();int delta=int(h.eval("mem[NATIVE_RANDOM_PITCH_LAST]"));check(delta!=previous&&bass_count(e,146,48+delta)==1,"Conductor admissions commit distinct successive random pitches");previous=delta;for(int n=0;n<10;++n){h.block();h.events();}}
 }
 for(bool fixed:{false,true}){
  Host h(source);fixture(h,true);h.run("clear_layer(1);store_event(1,0,144,60,90,0);store_event(1,640,128,60,0,0);mem[LEN_BASE+1]=1024;clear_layer(2);store_event(2,0,144,72,90,0);store_event(2,640,128,72,0,0);mem[LEN_BASE+2]=1024;native_random_seed=1;");
  auto text=random_layer_json(fixed);std::vector<unsigned> doc(text.begin(),text.end());check(conductor::validDocument(doc),"random layer document validates");conductor_install(h,doc);
  int previous=-1;for(int pass=0;pass<5;++pass){trigger(h,true);auto e=h.events();int chosen=int(h.eval("mem[NATIVE_RANDOM_LAYER]"));check(chosen>0&&chosen!=previous,"RANDOM LAYER avoids immediate repeats");
   check(bass_count(e,146,48)+bass_count(e,146,60)+bass_count(e,146,72)==(fixed?2:1),"one candidate plays alongside exactly the fixed layers");previous=chosen;for(int n=0;n<10;++n){h.block();h.events();}
  }
 }
 {
  Host h(source);fixture(h,false,0);h.run("clear_layer(0);store_event(0,0,144,60,90,0);store_event(0,3500,128,60,0,0);mem[LEN_BASE]=4096;loop_len_samples=4096;mem[NATIVE_RANDOM_SOURCE]=1;mem[NATIVE_RANDOM_SOURCE+1]=1;mem[NATIVE_RANDOM_SOURCE+2]=1;native_random_seed=65536;native_random_cycle_seed=17;native_hold_enqueue(0,2);");h.block();h.events();
  std::set<int> starts;for(int frame=0;frame<160;++frame){starts.insert(int(h.eval("mem[NATIVE_RANDOM_STATE+MAX_ONCE_VOICES*16+4]")));h.block();h.events();}
  check(starts.size()>1&&h.eval("mem[NATIVE_RANDOM_STATE+MAX_ONCE_VOICES*16+1]")>2,"direct LOOP redraws the start at real shortened cycle boundaries");
  h.run("b=sw_cfg(1);mem[b+14]=SW_STOP;sw_submit(1,0,0,0);");h.block();h.events();h.eq("mem[NOTE_REF_BASE+2*128+60]",0,"jitter LOOP STOP frees its actual note");
 }
 {
  Host h(source);fixture(h,true);h.run("native_random_seed=65536;b=sw_cfg(0);mem[b+8]=100;");auto text=random_layer_json(false,true);std::vector<unsigned> doc(text.begin(),text.end());conductor_install(h,doc);
  trigger(h,true);check(h.events().empty(),"selected HOLD candidate waits for its gesture");h.eq("mem[NATIVE_RANDOM_LAYER]",2,"one candidate selected at PRESS");double seed=h.eval("native_random_seed");
  h.run("sw_clock+=50000;");h.block();check(bass_count(h.events(),146,72)==1,"HOLD uses the retained selected candidate");
  h.eq("native_random_seed",seed,"later HOLD phase consumes no layer draw");h.eq("mem[NATIVE_RANDOM_LAYER]",2,"HOLD cannot reroll the step");
 }
 std::cout<<"PASS phrase randomization: palette filtering, transactional draws, crossing notes/sustain, reverse onsets and fixed/random layers\n";
}
