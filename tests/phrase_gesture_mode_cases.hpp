// Execute actual generated EEL; no substitute scheduler or note ownership.
static void gesture_fixture(Host& h,int mode){
 fixture(h,false);h.run("mem[NATIVE_PHRASE_PLAY_MODE_BASE]="+std::to_string(mode)+";");
}
static void phrase_gesture_mode_cases(const char* source){
 for(int mode:{3,4,5}){
  Host h(source);gesture_fixture(h,mode);trigger(h,false);auto first=h.events();
  check(bass_count(first,146,48)==1,"new phrase mode starts one real MIDI attack");
  h.eq("mem[instance_header(0)+8]",mode,"owner snapshots actual GATE/RETRIGGER/TOGGLE mode");
  h.eq("mem[MODE_BASE]",1,"new modes preserve old controller enum payload");
  if(mode==3){
   h.run("native_hold_enqueue(0,0);");h.block();check(bass_count(h.events(),130,48)==1,"GATE release stops current source owner");
   check(conductor_active(h)==0,"GATE release frees voice");
  }else if(mode==4){
   trigger(h,false);auto e=h.events();check(bass_count(e,130,48)==1&&bass_count(e,146,48)==1,"RETRIGGER sends previous Off before fresh On");
   check(conductor_active(h)==1,"RETRIGGER keeps exactly one source occurrence");
  }else{
   trigger(h,false);auto e=h.events();check(bass_count(e,130,48)==1&&bass_count(e,146,48)==0,"TOGGLE second press stops without readmission");
   check(conductor_active(h)==0,"TOGGLE second press frees voice");trigger(h,false);check(bass_count(h.events(),146,48)==1,"TOGGLE third press restarts from beginning");
  }
  h.run("native_phrase_stop(0,0);");h.block();h.events();
  trigger(h,false);h.events();int attacks=0;
  for(int n=0;n<12;++n){h.block();attacks+=bass_count(h.events(),146,48);}
  check(attacks==0&&conductor_active(h)==0,"GATE/RETRIGGER/TOGGLE finish naturally without looping");
  h.run("native_hold_enqueue(0,0);");h.block();check(h.events().empty(),"release after natural end cannot emit stale Off");
 }
 {
  Host h(source);gesture_fixture(h,4);
  h.run("mem[NATIVE_PHRASE_PLAY_MODE_BASE]=0;");
  for(int n=0;n<12;++n){h.run("phrase_admit_independent(0,0);");}
  h.block();h.events();check(conductor_active(h)==12,"full-pool RETRIGGER fixture");
  h.run("mem[NATIVE_PHRASE_PLAY_MODE_BASE]=4;");trigger(h,false);h.events();
  check(conductor_active(h)==1,"RETRIGGER reclaims own full-pool voices");
 }
 {
  Host h(source);gesture_fixture(h,3);h.run("clear_layer(1);store_event(1,0,144,72,80,0);store_event(1,4096,128,72,0,0);mem[LEN_BASE+1]=8192;mem[MODE_BASE+1]=1;mem[DECAY_BASE+1]=1;mem[VEL_BASE+1]=1;phrase_admit_independent(1,0);");h.block();h.events();
  trigger(h,false);h.events();h.run("native_hold_enqueue(0,0);");h.block();auto e=h.events();
  check(bass_count(e,130,48)==1&&bass_count(e,130,72)==0,"GATE release leaves another phrase untouched");
 }
 {
  Host h(source);fixture(h,true);auto doc=repeat_document(3);std::string text(doc.begin(),doc.end());std::string old="\"value\":\"ONCE\"";size_t pos=0;
  while((pos=text.find(old,pos))!=std::string::npos){text.replace(pos,old.size(),"\"value\":\"GATE\"");pos+=14;}
  doc.assign(text.begin(),text.end());check(conductor::validDocument(doc),"Conductor GATE override accepted");conductor_install(h,doc);
  h.midi(144,110,100);check(bass_count(h.events(),146,48)==1,"physical switch press admits GATE");
  h.run("mem[conductor_header(0)+3]=1;");h.midi(128,110,0);
  check(bass_count(h.events(),130,48)==1&&conductor_active(h)==0,"GATE release follows original switch stroke after cursor changes");
 }
 std::cout<<"PASS phrase modes: GATE press/release, RETRIGGER replacement, TOGGLE, natural ends, full pool and switch-stroke ownership\n";
}
