// Real native EEL, no JACK ports or user patch. The host writes only its private
// handoff; the same ingress merger and original instrument functions run in DSP.
static void destinationQueue(NativeHost&h,std::initializer_list<std::array<unsigned,5>> notes){
 std::string code="native_destination_count="+std::to_string(notes.size())+";native_destination_read=0;";unsigned q=0;
 for(auto n:notes){const unsigned b=29060000+q++*9;
  const unsigned fields[]={n[0],1,1,0,n[1],n[2],n[3],n[4],0};
  for(unsigned j=0;j<9;++j)code+="mem["+std::to_string(b+j)+"]="+std::to_string(fields[j])+";";
 }h.run(code);
}
static void destinationTests(const char*path){
 {
  NativeHost h(path);h.run("clear_layer(10);record_layer=10;state=STATE_READY;free_record_ready=1;controller_learn=0;learn_candidate=-1;");
  destinationQueue(h,{{0,60,100,1,16}});h.block();h.sources();h.events();
  h.eq("layer_count(10)",0,"destination ingress never records into an armed phrase");
  h.eq("free_record_active",0,"destination ingress never starts recording");
  h.eq("controller_learn",0,"destination ingress cannot consume MIDI Learn");h.eq("learn_candidate",-1,"destination ingress cannot become a Learn candidate");
  destinationQueue(h,{{0,60,0,0,16}});h.block();h.sources();h.events();
 }
 {
  NativeHost h(path);h.run("mem[INST_TRANSFORM_COUNT_BASE]=1;mem[INST_TRANSFORM_TYPE_BASE]=3;mem[INST_NOTE_MODE_BASE]=2;");
  destinationQueue(h,{{0,60,100,1,16}});uint8_t bytes[]={144,64,100};ysfx_midi_event_t packet{};packet.data=bytes;packet.size=3;packet.offset=8;
  check(ysfx_send_midi(h.f,&packet),"enqueue real physical note alongside destination ingress");h.block();auto events=h.sources();h.events();
  check(events.size()==3 && events[0].key.origin==Origin::Live && events[0].key.pitch==64 && events[0].offset==8,"physical MIDI precedes a later echo at its original offset");
  destinationQueue(h,{{0,60,0,0,16}});h.block();events=h.sources();h.events();
  bool fallback=false;for(const auto&e:events)fallback|=e.action==SourceAction::On && e.key.pitch==64 && e.key.origin==Origin::Live;
  check(fallback,"mono release of routed echo restores the still-held physical note");
  destinationQueue(h,{});h.midi(128,64,0);h.sources();h.events();h.eq("mem[MONO_ACTIVE_NOTE_BASE]",-1,"mixed physical/echo mono ownership retires");
 }
 {
  NativeHost h(path);h.run("mem[INST_TRANSFORM_COUNT_BASE]=2;mem[INST_TRANSFORM_TYPE_BASE]=1;mem[INST_TRANSFORM_TYPE_BASE+1]=4;mem[INST_TRANSPOSE_BASE]=12;mem[INST_VEL_BASE]=.5;");
  destinationQueue(h,{{0,60,100,1,16}});h.block();auto on=h.sources();h.events();
  check(on.size()==1 && on[0].action==SourceAction::On && on[0].key.origin==Origin::Echo && on[0].key.pitch==72 && on[0].velocity==50 && on[0].offset==16,"full destination applies native transpose and velocity at scheduled attack");
  h.run("mem[INST_TRANSPOSE_BASE]=-12;");destinationQueue(h,{{0,60,0,0,24}});h.block();auto off=h.sources();h.events();
  check(off.size()==1 && off[0].action==SourceAction::Off && off[0].key.origin==Origin::Echo && off[0].key.pitch==72 && off[0].offset==24,"full destination releases captured pitch after transpose changes");
  h.eq("mem[PARAM_ACTIVE_BASE]",0,"destination input activity is balanced");
 }
 for(unsigned mode:{1u,2u,3u}){
  NativeHost h(path);h.run("mem[INST_TRANSFORM_COUNT_BASE]=1;mem[INST_TRANSFORM_TYPE_BASE]=3;mem[INST_NOTE_MODE_BASE]="+std::to_string(mode)+";");
  destinationQueue(h,{{0,60,100,1,8},{1,72,100,1,24}});h.block();auto events=h.sources();h.events();
  check(!events.empty(),"full destination enters original native mono/legato processor");
  for(const auto&e:events)check(e.key.origin==Origin::Echo,"polyphony-generated transitions retain echo provenance");
  destinationQueue(h,{{0,60,0,0,8},{1,72,0,0,24}});h.block();events=h.sources();h.events();
  for(const auto&e:events)check(e.key.origin==Origin::Echo,"mono fallback and releases cannot create another echo series");
  h.eq("mem[MONO_ACTIVE_NOTE_BASE]",-1,"all destination mono notes retire");h.eq("mem[PARAM_ACTIVE_BASE]",0,"mono destination input activity retires");
 }
 for(unsigned mode=0;mode<=12;++mode){
  NativeHost h(path);h.run("mem[INST_TRANSFORM_COUNT_BASE]=1;mem[INST_TRANSFORM_TYPE_BASE]=5;mem[INST_ARP_ENABLED_BASE]=1;mem[INST_ARP_MODE_BASE]="+std::to_string(mode)+";mem[INST_ARP_RATE_BASE]=16;mem[INST_ARP_GATE_BASE]=.5;mem[INST_ARP_HOLD_BASE]=0;");
  destinationQueue(h,{{0,60,100,1,8},{1,64,90,1,16},{2,67,80,1,24}});
  unsigned attacks=0;echocity::Runtime runtime(48000);echocity::Configurations settings{};settings[0].id=settings[0].instrument=1;settings[0].dry=0;runtime.configure(settings);
  auto emit=[](auto...){return true;};
  for(unsigned block=0;block<48;++block){
   if(block)destinationQueue(h,{});h.block();h.events();auto edges=h.sources();
   for(const auto&e:edges){check(e.key.origin==Origin::Echo,"ARP keeps echo provenance across later DSP blocks");attacks+=e.action==SourceAction::On;check(runtime.source(e,block*128+e.offset,120,emit),"destination ARP source reaches final output ledger");}
   check(runtime.pending()==0,"destination ECHOCITY is bypassed, not recursively triggered");
  }
  check(attacks>=2,"original ARP advances across blocks for routed echo chord");
  destinationQueue(h,{{0,60,0,0,8},{1,64,0,0,16},{2,67,0,0,24}});h.block();h.events();
  for(const auto&e:h.sources()){check(e.key.origin==Origin::Echo,"ARP release retains originating echo identity");check(runtime.source(e,48*128+e.offset,120,emit),"ARP tail retires final dry lease");}
  check(!runtime.sources()&&!runtime.pending()&&!runtime.failed,"full routed ARP leaves no hung native note ownership");
 }
 {
  NativeHost h(path);destinationQueue(h,{{0,60,100,1,80}});h.run("panic_pending=1;");h.block();auto events=h.sources();h.events();
  check(count(events,SourceAction::On)==0,"panic cancels an echo attack waiting in the internal handoff");
 }
}
