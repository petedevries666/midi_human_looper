// Actual generated production EEL, native ownership and Conductor compiler.
#include "native_test_host.hpp"
#include "conductor_baseline_cases.hpp"
#include "conductor_execution_cases.hpp"
#include "../headless/echocity_runtime.hpp"
static void fixture(Host &h,bool conductor,int mode=1) {
  conductor_fixture(h);
  h.run("native_phrase_contract=2;native_free_time=1;ext_midi_bus=1;"
        "mem[INST_IN_BASE]=0;mem[INST_OUT_BASE]=3;mem[INST_LEVEL_BASE]=127;"
        "clear_layer(0);store_event(0,0,144,48,40,0);"
        "store_event(0,640,128,48,0,0);mem[LEN_BASE]=1024;"
        "mem[DECAY_BASE]=1;mem[VEL_BASE]=1;mem[PHRASE_GROUP_BASE]=0;");
  h.run("mem[MODE_BASE]="+std::to_string(mode)+";");
  if(conductor){
    auto doc=conductor_model(1,false,mode);std::string s(doc.begin(),doc.end());
    for(unsigned i=2;i<=4;++i){const auto old="\"sourceId\":\""+conductor_uuid(i)+"\"";size_t at;
      while((at=s.find(old))!=std::string::npos)s.replace(at,old.size(),"\"sourceId\":\""+conductor_uuid(1)+"\"");}
    conductor_install(h,std::vector<unsigned>(s.begin(),s.end()));
  }
}
static void trigger(Host&h,bool conductor){
  if(conductor){
    uint8_t off[]={128,110,0};ysfx_midi_event_t e{};e.size=3;e.data=off;
    check(ysfx_send_midi(h.f,&e),"enqueue Conductor pedal release before next press");
    h.midi(144,110,100);
  }
  else {h.run("trigger_request=0;");h.block();}
}
static void pair(const char* source,bool conductor,double decay){
  Host h(source);fixture(h,conductor);h.run("mem[DECAY_BASE]="+std::to_string(decay)+";");
  trigger(h,conductor);auto first=h.events();
  check(first==std::vector<std::vector<int>>{{146,48,40}},"first ONCE attack routes to channel 3");
  trigger(h,conductor);auto second=h.events();
  check(second==std::vector<std::vector<int>>{{146,48,int(std::floor(40*decay+.5))}},"overlapping identical-pitch ONCE emits a fresh attack with decay and no artificial Off");
  check(conductor_active(h)==2,"mute group zero preserves both ONCE instances");
  h.eq("mem[NOTE_REF_BASE+2*128+48]",2,"two logical note owners");
  for(int i=0;i<3;++i){h.block();h.events();}
  h.block();check(h.events().empty(),"first recorded Off cannot cut later instance");
  h.eq("mem[NOTE_REF_BASE+2*128+48]",1,"only first owner released");
  h.block();check(h.events()==std::vector<std::vector<int>>{{130,48,0}},"last owner emits exact routed release");
  for(int i=0;i<3;++i){h.block();h.events();}
  check(conductor_active(h)==0,"ONCE completes naturally");
  for(int v=0;v<12;++v){auto b="instance_header("+std::to_string(v)+")";
    h.eq("mem["+b+"+5]",0,"completion frees every attack record");h.eq("mem["+b+"+13]",0,"completion frees output ownership");}
  if(!conductor){trigger(h,false);check(h.events()==first,"idle direct retrigger resets decay sequence");}
}
int main(int argc,char**argv){
  check(argc==2,"native generated source required");
  for(int tune:{-24,0,24}){
    Host h(argv[1]);fixture(h,false);h.run("mem[NATIVE_PHRASE_TUNE_BASE]="+std::to_string(tune)+";");
    trigger(h,false);check(h.events()==std::vector<std::vector<int>>{{146,48+tune,40}},"phrase TUNE transposes attack");
    h.run("mem[NATIVE_PHRASE_TUNE_BASE]=7;");
    unsigned releases=0;for(int i=0;i<12;++i){h.block();auto e=h.events();if(!e.empty()){check(e==std::vector<std::vector<int>>{{130,48+tune,0}},"TUNE release retains admitted pitch after source edit");++releases;}}
    check(releases==1,"recorded release is emitted exactly once");
    h.eq("mem[NOTE_REF_BASE+2*128+"+std::to_string(48+tune)+"]",0,"TUNE leaves no hanging owner");
  }
  {
    Host h(argv[1]);fixture(h,true);auto doc=conductor_model(1,false,1);std::string text(doc.begin(),doc.end());
    const std::string empty="\"overrides\":{\"playMode\":{\"mode\":\"OVERRIDE\",\"value\":\"ONCE\"}}";auto at=text.find(empty);check(at!=std::string::npos,"TUNE fixture overrides");
    text.replace(at,empty.size(),"\"overrides\":{\"phrase_tune\":{\"mode\":\"OVERRIDE\",\"value\":12}}");
    conductor_install(h,std::vector<unsigned>(text.begin(),text.end()));trigger(h,true);
    check(h.events()==std::vector<std::vector<int>>{{146,60,40}},"Conductor local TUNE routes transposed attack");
    h.eq("mem[NATIVE_PHRASE_TUNE_BASE]",0,"Conductor TUNE preserves source");
    h.run("sw_stop_phrases();");h.block();auto stopped=h.events();std::cout<<"TUNE STOP trace "<<conductor_events(stopped)<<std::endl;check(conductor_count(stopped,128,60)==1,"Conductor TUNE STOP releases exact pitch");h.eq("mem[NOTE_REF_BASE+2*128+60]",0,"TUNE STOP retires pitch owner");
  }
  for(bool conductor:{false,true})for(double decay:{.5,1.,1.5,2.})pair(argv[1],conductor,decay);
  for(bool conductor:{false,true}){
    Host h(argv[1]);fixture(h,conductor);
    // Saturate twelve slots while the phrase remains long enough to overlap.
    h.run("mem[LEN_BASE]=4096;");
    for(int i=0;i<12;++i){trigger(h,conductor);auto e=h.events();check(e==std::vector<std::vector<int>>{{146,48,40}},"every admitted ONCE reaches MIDI");}
    trigger(h,conductor);h.events();check(conductor_active(h)==12,"capacity refusal preserves owners");
    for(int i=0;i<45;++i){h.block();h.events();}
    check(conductor_active(h)==0,"completed capacity is reusable");
    trigger(h,conductor);check(h.events()==std::vector<std::vector<int>>{{146,48,40}},"reused slot emits first attack");
  }
  {
    Host h(argv[1]);fixture(h,false,2);trigger(h,false);h.events();
    for(int i=0;i<12;++i){h.block();check(h.events().empty(),"HOLD ignores source Off and remains latched");}
    check(conductor_active(h)==1,"mode 2 intentionally waits for cancellation");
    trigger(h,false);auto e=h.events();check(conductor_active(h)==1,"direct HOLD retrigger replaces old owner");
    check(e==std::vector<std::vector<int>>{{130,48,0},{146,48,40}},"HOLD replacement releases before attack");
    h.run("sw_stop_phrases();");h.block();h.events();check(conductor_active(h)==0,"STOP cancels HOLD");
  }
  {
    Host h(argv[1]);fixture(h,false,0);
    h.run("loop_len_samples=1024;b=sw_cfg(0);mem[b+11]=1;mem[b+SW_LIST]=0;sw_submit(0,0,0,0);");
    h.block();check(h.events()==std::vector<std::vector<int>>{{146,48,40}},"direct LOOP starts through existing switch dispatcher");
    h.eq("mem[TRIG_BASE]",1,"LOOP starts latched");
    h.run("sw_submit(0,0,0,0);");h.block();auto e=h.events();
    h.eq("mem[TRIG_BASE]",0,"direct LOOP retrigger toggles off");
    check(e==std::vector<std::vector<int>>{{130,48,0}},"LOOP stop releases its own output");
  }
  {
    Host h(argv[1]);fixture(h,false);
    h.run("clear_layer(0);store_event(0,0,144,48,40,0);store_event(0,64,144,48,80,0);store_event(0,128,128,48,0,0);store_event(0,256,144,48,0,0);mem[LEN_BASE]=512;");
    trigger(h,false);check(h.events()==std::vector<std::vector<int>>{{146,48,40},{146,48,80}},"same phrase FIFO repeated pitch emits both attacks");
    h.block();check(h.events().empty(),"first FIFO release preserves second attack");
    h.block();check(h.events()==std::vector<std::vector<int>>{{130,48,0}},"zero velocity On releases final FIFO owner");
    h.block();h.events();check(conductor_active(h)==0,"repeated pitch phrase finishes");
  }
  {
    Host h(argv[1]);fixture(h,false);
    h.run("clear_layer(0);store_event(0,0,144,48,40,0);mem[LEN_BASE]=512;");
    trigger(h,false);h.events();trigger(h,false);h.events();
    h.run("instance_request_stop(mem[instance_header(0)],mem[instance_header(0)+1]);");
    h.block();check(h.events().empty(),"targeted STOP cannot release surviving identical pitch");
    h.eq("mem[NOTE_REF_BASE+2*128+48]",1,"targeted STOP retires just one owner");
    for(int i=0;i<2;++i){h.block();h.events();}
    check(conductor_active(h)==0,"missing source Off is cleaned at natural completion");
    h.eq("mem[NOTE_REF_BASE+2*128+48]",0,"natural cleanup retires orphaned note ownership");
  }
  {
    Host h(argv[1]);fixture(h,false);h.eq("param_max(15)",2,"native decay maximum is 200 percent");
    check(std::isfinite(h.eval("native_phrase_repeat_gain(2,1000000000)")) && h.eval("native_phrase_repeat_gain(2,1000000000)")>1e99,"growth is bounded before exponentiation, retaining attenuation headroom");
    h.run("mem[DECAY_BASE]=2;mem[LEN_BASE]=4096;");
    for(int i=0;i<4;++i){trigger(h,false);auto e=h.events();check(e==std::vector<std::vector<int>>{{146,48,std::min(127,40*(1<<i))}},"growing ONCE velocity saturates at 127");}
  }
  {
    // The host switches to this native terminal route once ECHOCITY has ever
    // been configured. Its dry branch must preserve the same phrase contract.
    echocity::Runtime runtime(48000);std::vector<int> edges;
    auto emit=[&](uint64_t,bool on,uint8_t ch,uint8_t pitch,uint8_t vel,bool retrigger){check(ch==2&&pitch==48&&!retrigger,"dry phrase repeats never fabricate a destructive Off");edges.push_back(on?vel:0);return true;};
    echocity::SourceEvent e;e.action=echocity::SourceAction::On;e.key={1,native_notes::Origin::Phrase,1,2,48};e.velocity=40;
    check(runtime.source(e,0,120,emit),"native dry first owner");e.key.instance=2;e.velocity=80;check(runtime.source(e,128,120,emit),"native dry second owner");
    check(edges==std::vector<int>{40,80},"ECHOCITY terminal dry path emits both attacks");
    e.action=echocity::SourceAction::Off;e.key.instance=1;runtime.source(e,640,120,emit);check(edges.size()==2,"native terminal first Off preserves other owner");
    e.key.instance=2;runtime.source(e,768,120,emit);check(edges==std::vector<int>{40,80,0}&&runtime.sources()==0,"native terminal final release retires all resources");
  }
  printf("PASS %d native ONCE retrigger, decay, ownership and lifecycle checks\n",checks);
}
