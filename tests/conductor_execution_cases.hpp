#include "../headless/conductor_execution.hpp"
#include <iostream>
static std::string conductor_uuid(unsigned n){char b[64];snprintf(b,sizeof b,"00000000-0000-0000-0000-%012u",n);return b;}
static std::vector<unsigned> conductor_model(unsigned layers=1,bool missing=false,int mode=1){
  std::ostringstream s;s<<"{\"version\":1,\"sources\":[";
  for(unsigned i=0;i<4;++i){if(i)s<<',';s<<"{\"id\":\""<<conductor_uuid(i+1)<<"\",\"type\":\"PHRASE\",\"slot\":"<<i+1<<'}';}
  s<<"],\"switches\":[{\"switchId\":1,\"traversal\":\"SEQUENTIAL\",\"transition\":\"IMMEDIATE\",\"gesture\":\"INSTANT\",\"steps\":[";
  for(unsigned i=0;i<4;++i){if(i)s<<',';s<<"{\"id\":\""<<conductor_uuid(10+i)<<"\",\"transition\":\"INHERIT\",\"layers\":[";
    for(unsigned j=0;j<layers;++j){if(j)s<<',';s<<"{\"id\":\""<<conductor_uuid(100+i*20+j)<<"\",\"block\":{\"id\":\""<<conductor_uuid(1000+i*20+j)<<"\",\"type\":\"PHRASE\",\"sourceId\":\""<<conductor_uuid(missing?9999:(i+j)%4+1)<<"\",\"overrides\":{\"playMode\":{\"mode\":\"OVERRIDE\",\"value\":\""<<(mode==0?"LOOP":mode==1?"ONCE":"HOLD")<<"\"}}}}";}
    s<<"]}";}
  s<<"]}]}";auto text=s.str();std::vector<unsigned> bytes(text.begin(),text.end());check(conductor::validDocument(bytes),"production document validator accepts fixture");return bytes;
}
static void conductor_install(Host& h,const std::vector<unsigned>& bytes){
  std::array<unsigned,16> owners{};owners[0]=1;double base=h.val("CONDUCTOR_BASE");auto cells=conductor::compile(bytes,base,owners);
  for(unsigned i=0;i<cells.size();++i)*NSEEL_VM_getramptr(h.f->vm.get(),unsigned(base)+i,nullptr)=cells[i];
  h.run("conductor_host_enabled=1;");
}
static void conductor_execution_tests(const char* source){
  unsigned before=checks;
  {
    Host h(source);conductor_fixture(h);
    h.run("i=0;loop(4,clear_layer(i);store_event(i,0,144,48+i*4,100,0);store_event(i,4096,128,48+i*4,0,0);mem[LEN_BASE+i]=8192;mem[MODE_BASE+i]=1;mem[DECAY_BASE+i]=1;mem[VEL_BASE+i]=1;i+=1;);");
    conductor_install(h,conductor_model());std::vector<std::vector<int>> trace;
    for(unsigned i=0;i<5;++i){h.midi(144,110,127);auto events=h.events();check(conductor_count(events,144,48+(i%4)*4)==1,"PRESS emits correct STEP attack");for(auto e:events)check((e[0]&240)!=128,"STEP change never stops prior instance");trace.insert(trace.end(),events.begin(),events.end());h.midi(128,110,0);h.events();h.eq("mem[conductor_header(0)+3]",i%4,"selected STEP and wrap are authoritative");}
    check(conductor_active(h)==5,"five actual instances coexist across wrap");std::cout<<"CONDUCTOR EEL PRESS trace "<<conductor_events(trace)<<'\n';
    h.run("sw_submit(0,0,0,0);");h.block();check(conductor_count(h.events(),144,52)==1,"existing TEST reaches same actual engine dispatcher");
    h.run("sw_submit(0,0,0,0);");h.block();h.events();
    for(unsigned i=0;i<5;++i){h.run("sw_submit(0,0,0,0);");h.block();h.events();}
    check(conductor_active(h)==12,"existing twelve slots remain available");h.run("sw_submit(0,0,0,0);");h.block();auto output=h.events();check(output.empty(),"thirteenth admission emits no attack or release");h.eq("mem[conductor_header(0)+4]",2,"saturation is explicit");check(conductor_active(h)==12,"saturation preserves all owners");
    h.run("mem[sw_cfg(1)]=1;mem[sw_cfg(1)+14]=SW_STOP;sw_submit(1,0,0,0);");h.block();h.events();check(conductor_active(h)==0,"STOP cleans conductor instances");
  }
  {
    Host h(source);conductor_fixture(h);conductor_install(h,conductor_model(1,true));h.midi(144,110,127);
    check(h.events().empty()&&conductor_active(h)==0,"missing UUID never falls back to legacy source/index");h.eq("mem[conductor_header(0)+5]",1,"missing reference diagnostic");
  }
  {
    Host h(source);conductor_fixture(h);conductor_install(h,conductor_model(2));h.midi(144,110,127);auto e=h.events();
    check(conductor_count(e,144,48)==1&&conductor_count(e,144,72)==1,"two layers emit actual simultaneous MIDI");check(conductor_active(h)==2,"layers retain independent ownership");
    h.run("instance_request_stop(mem[instance_header(0)],mem[instance_header(0)+1]);");h.block();e=h.events();check(conductor_count(e,128,48)==1&&conductor_count(e,128,72)==0,"targeted STOP preserves other layer");
  }
  for(int mode: {0,2}){
    Host h(source);conductor_fixture(h);conductor_install(h,conductor_model(1,false,mode));h.midi(144,110,127);h.events();
    h.eq("mem[MODE_BASE]",1,"local play-mode override never rewrites source");h.eq("mem[instance_header(0)+8]",mode,"instance captures local mode");
    h.midi(128,110,0);auto e=h.events();check(conductor_active(h)==(mode==2?0:1),"HOLD release stops only held lifecycle; LOOP survives release");
    if(mode==2)check(conductor_count(e,128,48)==1,"HOLD matching actual Off");
    h.run("sw_action(0,SW_PANIC,0,0);");h.block();h.events();check(conductor_active(h)==0,"PANIC releases override instance");
  }
  {
    Host h(source);conductor_fixture(h);auto bytes=conductor_model();std::string data(bytes.begin(),bytes.end());
    for(unsigned i=2;i<=4;++i){auto from=conductor_uuid(i),to=conductor_uuid(1);auto needle="\"sourceId\":\""+from+"\"";auto at=data.find(needle);check(at!=std::string::npos,"fixture source ref found");data.replace(at,needle.size(),"\"sourceId\":\""+to+"\"");}
    size_t at=0;const std::string token="\"overrides\":{";
    const std::string local="\"phrase_base_velocity\":{\"mode\":\"OVERRIDE\",\"value\":0.5},\"phrase_velocity_decay\":{\"mode\":\"OVERRIDE\",\"value\":0.5},\"phrase_time_decay\":{\"mode\":\"OVERRIDE\",\"value\":2},";
    while((at=data.find(token,at))!=std::string::npos){at+=token.size();data.insert(at,local);at+=local.size();}
    bytes.assign(data.begin(),data.end());check(conductor::validDocument(bytes),"local numeric overrides validate");conductor_install(h,bytes);
    for(unsigned j=0;j<4;++j){h.midi(144,110,127);auto e=h.events();int expected[]={46,23,11,6};bool found=false;for(auto v:e)if(v[0]==144&&v[1]==48&&v[2]==expected[j])found=true;check(found,"real velocity reflects local base and multiplicative decay");h.midi(128,110,0);h.events();h.eq(("mem[VOICE_TIME_BASE+"+std::to_string(j)+"]").c_str(),std::pow(2.,j),"local TIME DECAY captures independent timing factor");}
    h.eq("mem[DECAY_BASE]",1,"local velocity decay preserves source");h.eq("phrase_time_ratio(0)",1,"local TIME DECAY preserves source");h.eq("mem[REPEAT_BASE]",0,"independent progression preserves legacy repeat counter");
  }
  {
    Host h(source);conductor_fixture(h);conductor_install(h,conductor_model(2));h.run("loop(11,phrase_admit_independent(0,0));");h.block();h.events();h.midi(144,110,127);check(h.events().empty()&&conductor_active(h)==11,"two-layer STEP refuses atomically with one free slot");h.eq("mem[conductor_header(0)+3]",-1,"refused STEP does not advance cursor");
  }
  {
    Host h(source);conductor_fixture(h);conductor_install(h,conductor_model());h.run("mem[INST_TRANSFORM_COUNT_BASE]=1;mem[INST_TRANSFORM_TYPE_BASE]=5;mem[INST_ARP_ENABLED_BASE]=1;");h.midi(144,110,127);check(h.events().empty()&&conductor_active(h)==0,"independent ARP configuration remains explicitly refused");h.eq("mem[conductor_header(0)+4]",3,"unsafe routing diagnostic");
  }
  {
    Host h(source);conductor_fixture(h);conductor_install(h,conductor_model());
    h.run("clear_layer(0);store_event(0,0,144,48,90,0);store_event(0,200,144,48,80,0);store_event(0,400,128,48,0,0);store_event(0,600,128,48,0,0);mem[LEN_BASE]=2048;");
    h.midi(144,48,100);h.events();h.midi(144,110,127);h.events();h.run("mem[MUTE_BASE]=1;");h.block();auto e=h.events();check(conductor_count(e,144,48)==0,"muted later attacks create silent FIFO placeholders");
    h.block();e=h.events();check(conductor_count(e,128,48)==0,"muted FIFO releases cannot cut held physical owner");h.block();h.events();h.block();h.events();h.midi(128,48,0);e=h.events();check(conductor_count(e,128,48)==1,"physical final release remains independent from muted source");
  }
  for(unsigned layers: {1u,2u,12u}){
    Host h(source);conductor_fixture(h);
    h.run("i=0;loop(4,clear_layer(i);store_event(i,0,144,48+i,100,0);store_event(i,4096,128,48+i,0,0);mem[LEN_BASE+i]=8192;mem[MODE_BASE+i]=1;mem[DECAY_BASE+i]=1;i+=1;);");
    conductor_install(h,conductor_model(layers));std::vector<double> times;
    for(unsigned j=0;j<110;++j){h.run("sw_stop_phrases();sw_submit(0,0,0,0);");auto start=std::chrono::steady_clock::now();h.block();double us=std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-start).count();h.events();if(j>=10)times.push_back(us);}
    std::sort(times.begin(),times.end());
    std::cout<<"CONDUCTOR COST {\"layers\":"<<layers<<",\"blocks\":100,\"frames\":128,\"medianUs\":"<<times[50]<<",\"p95Us\":"<<times[95]<<",\"maxUs\":"<<times.back()<<"}\n";
  }
  std::cout<<"PASS actual CONDUCTOR shared EEL checks: "<<checks-before<<'\n';
}
