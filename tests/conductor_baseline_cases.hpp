// PR A: execute the production EEL dispatcher and report unmet PR55 contracts.
// No alternate renderer, scheduler, ownership implementation or engine edits.
#include <algorithm>
#include <chrono>
#include <iomanip>
#include <sstream>
#include "../headless/controller_host.hpp"

static void conductor_fixture(Host &h) {
  h.run("ext_noinit=1;gmem[0]=0;panic_pending=0;slider9=1;"
        "sw_defaults();sw_runtime_reset();native_hold_enabled=1;"
        "mem[INST_ENABLED_BASE]=1;mem[INST_ENABLED_BASE+1]=0;"
        "mem[INST_ENABLED_BASE+2]=0;mem[INST_OUT_BASE]=1;"
        "mem[INST_TRANSFORM_COUNT_BASE]=0;state=STATE_STOPPED;"
        "last_trigger_layer=-1;trigger_request=-1;"
        "clear_layer(0);clear_layer(1);"
        "store_event(0,0,144,48,91,0);store_event(0,4096,128,48,23,0);"
        "store_event(1,0,144,72,83,0);store_event(1,4096,128,72,31,0);"
        "mem[LEN_BASE]=8192;mem[LEN_BASE+1]=8192;"
        "mem[MODE_BASE]=1;mem[MODE_BASE+1]=1;"
        "mem[DECAY_BASE]=1;mem[DECAY_BASE+1]=1;"
        "b=sw_cfg(0);mem[b]=1;mem[b+20]=1;mem[b+2]=1;mem[b+3]=0;"
        "mem[b+4]=110;mem[b+5]=0;mem[b+6]=0;mem[b+11]=2;"
        "mem[b+14]=SW_NEXT;mem[b+15]=0;mem[b+16]=0;"
        "mem[b+SW_LIST]=0;mem[b+SW_LIST+1]=1;");
  h.events();
}
static int conductor_count(const std::vector<std::vector<int>> &events,
                           int type, int pitch) {
  int count=0;
  for (const auto &e:events) {
    check(e.size()==3,"baseline MIDI message is a complete channel event");
    const bool off=(e[0]&240)==128 || ((e[0]&240)==144 && e[2]==0);
    if(e[1]==pitch && (type==128?off:((e[0]&240)==144 && e[2]>0)))++count;
  }
  return count;
}
static int conductor_active(Host &h) {
  return int(h.eval("(cb_i=0;cb_n=0;loop(MAX_ONCE_VOICES,"
                    "cb_n+=mem[VOICE_ACTIVE_BASE+cb_i]>.5;cb_i+=1;);cb_n;)"));
}
static std::string conductor_events(const std::vector<std::vector<int>> &events) {
  std::ostringstream out;out<<"[";bool comma=false;
  for(const auto &e:events){if(comma)out<<",";comma=true;out<<"[";
    for(unsigned i=0;i<e.size();++i){if(i)out<<",";out<<e[i];}out<<"]";}
  out<<"]";return out.str();
}
static int conductor_baseline_tests(const char *source,bool strict) {
  unsigned xfails=0;
  std::ostringstream cases;bool comma=false;
  auto contract=[&](const char *id,bool satisfied,const std::string &observed){
    // A baseline run must reproduce the known failure. A future repair must
    // promote it to an ordinary regression, not silently keep an XFAIL forever.
    if(satisfied){fprintf(stderr,"XPASS %s: promote the corrected contract\n",id);exit(1);}
    ++xfails;printf("XFAIL %s %s\n",id,observed.c_str());
    if(comma)cases<<",";comma=true;
    cases<<"{\"id\":\""<<id<<"\",\"status\":\"XFAIL\",\"observed\":"<<observed<<"}";
  };
  {
    Host h(source);conductor_fixture(h);
    h.midi(144,110,127);auto first=h.events();
    check(conductor_count(first,144,48)==1,"first real MIDI switch PRESS emits bass attack");
    check(conductor_count(first,144,110)==0,"switch command is not leaked to output");
    h.midi(128,110,0);h.events();h.midi(144,110,127);auto second=h.events();
    check(conductor_count(second,144,72)==1,"second PRESS emits second phrase attack");
    const int voices=conductor_active(h);
    check(voices==1 && conductor_count(second,128,48)==1,"reproduce exact inter-source choke symptom");
    contract("ONCE_CROSS_SOURCE_CHOKE",voices==2 && conductor_count(second,128,48)==0,
      "{\"activeVoices\":"+std::to_string(voices)+",\"midi\":"+conductor_events(second)+"}");
    h.run("sw_action(0,SW_PANIC,0,0);");h.block();h.events();
    check(conductor_active(h)==0,"PANIC retires runtime voices");
    h.eq("layer_count(0)",2,"PANIC preserves bass source");
    h.eq("layer_count(1)",2,"PANIC preserves second source");
  }
  {
    Host h(source);conductor_fixture(h);
    for(unsigned i=0;i<12;++i){h.run("trigger_request=0;");h.block();h.events();}
    check(conductor_active(h)==12,"twelve overlapping same-source attacks are admitted");
    h.run("trigger_request=0;");h.block();auto output=h.events();int voices=conductor_active(h);
    check(voices==1 && conductor_count(output,128,48)==1,"reproduce global recycling on the thirteenth voice");
    contract("VOICE_EXHAUSTION_GLOBAL_RELEASE",voices>=12,
      "{\"before\":12,\"after\":"+std::to_string(voices)+",\"midi\":"+conductor_events(output)+"}");
  }
  {
    Host h(source);conductor_fixture(h);
    h.midi(144,48,100);check(conductor_count(h.events(),144,48)==1,"physical bass note starts independently");
    h.midi(144,110,127);h.events();h.midi(128,110,0);h.events();
    h.midi(144,110,127);auto output=h.events();
    const int live=int(h.eval("mem[engine_addr(SW_LIVE_OUT_BASE,48)]"));
    check(live==1 && conductor_count(output,128,48)==1,"choke emits Off despite physical output owner");
    contract("CHOKE_RELEASES_LIVE_OWNER",conductor_count(output,128,48)==0,
      "{\"liveOwners\":"+std::to_string(live)+",\"midi\":"+conductor_events(output)+"}");
  }
  Host capacities(source);conductor_fixture(capacities);
  std::ostringstream limits;limits<<"{";bool separator=false;
  for(const char *name:{"IO_SCHEMA","LAYERS","MAX_EVENTS_PER_LAYER","EV_SIZE",
       "MAX_ONCE_VOICES","INST_CAP","TRANSFORM_SLOTS","SW_COUNT","SW_STEPS",
       "EXP_POINTS","PATCH_PAYLOAD_SIZE","I_RUNTIME_END"}){
    if(separator)limits<<",";separator=true;limits<<"\""<<name<<"\":"<<capacities.eval(name);
  }limits<<",\"controllerTargets\":"<<controller::Engine::TargetCapacity
    <<",\"controllerPolicyMappings\":"<<controller::Engine::MappingCapacity
    <<",\"controllerSources\":"<<controller::Configuration().sources.size()
    <<",\"controllerBindings\":"<<controller::Configuration().bindings.size()
    <<",\"controllerCurvePoints\":"<<controller::Curve().points.size()
    <<",\"controllerCoreBytes\":"<<sizeof(controller::Engine)
    <<",\"controllerConfigBytes\":"<<sizeof(controller::Configuration)<<"}";
  // Wall-clock EEL workload, not JACK/Pi deadline or allocation qualification.
  // Warm-up and processing only: compilation, GUI, fixture edits excluded.
  std::ostringstream measurements;separator=false;
  for(unsigned rate:{44100u,48000u,96000u})for(unsigned block:{128u,256u,512u,8192u})
    for(unsigned voices:{1u,12u}){
      Host h(source,false);ysfx_set_sample_rate(h.f,rate);ysfx_set_block_size(h.f,block);ysfx_init(h.f);
      conductor_fixture(h);
      h.run("mem[LEN_BASE]=srate*100;mem[layer_base(0,1)]=srate*99;"
            "cb_j=0;loop("+std::to_string(voices)+",trigger_request=0;process_phrase_trigger(0,1);cb_j+=1;);");
      for(unsigned warm=0;warm<4;++warm){ysfx_process_float(h.f,nullptr,nullptr,0,0,block);h.events();}
      check(conductor_active(h)==int(voices),"measurement maintains its declared active workload");
      std::vector<double> times;
      for(unsigned repeat=0;repeat<64;++repeat){
        auto start=std::chrono::steady_clock::now();
        ysfx_process_float(h.f,nullptr,nullptr,0,0,block);
        auto end=std::chrono::steady_clock::now();
        times.push_back(std::chrono::duration<double,std::micro>(end-start).count());h.events();
      }
      std::sort(times.begin(),times.end());if(separator)measurements<<",";separator=true;
      measurements<<"{\"sampleRate\":"<<rate<<",\"block\":"<<block<<",\"voices\":"<<voices
        <<",\"iterations\":64,\"medianUs\":"<<times[32]<<",\"p95Us\":"<<times[60]
        <<",\"maxUs\":"<<times.back()<<",\"budgetUs\":"<<1e6*block/rate<<"}";
    }
  if(const char *path=getenv("CONDUCTOR_BASELINE_REPORT")){
    std::ofstream out(path);check(bool(out),"open baseline evidence file");
    out<<"{\"version\":1,\"scope\":\"production EEL; Cloud wall-clock workload, not hardware qualification\","
       <<"\"knownFailures\":["<<cases.str()<<"],\"capacities\":"<<limits.str()
       <<",\"measurements\":["<<measurements.str()<<"]}\n";
    out.close();check(bool(out),"write complete baseline evidence file");
  }
  printf("BASELINE: %d checks; %u known contract failures; no engine correction in PR A\n",checks,xfails);
  return strict&&xfails?1:0;
}
