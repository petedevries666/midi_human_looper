// The reported five-step HOLD wrap on the real generated-EEL engine.
#include "native_test_host.hpp"
#include "conductor_baseline_cases.hpp"
#include "conductor_execution_cases.hpp"
static unsigned countMidi(const std::vector<std::vector<int>>& events,int status,int pitch){
  unsigned n=0;for(const auto&e:events)if(e.size()==3&&e[0]==status&&e[1]==pitch&&(status<144||e[2]>0))++n;return n;
}

static std::vector<unsigned> fiveSteps() {
  std::ostringstream s;
  s << "{\"version\":3,\"ccRate\":25,\"movements\":[],\"sources\":[";
  for(unsigned i=0;i<4;++i){if(i)s<<',';s<<"{\"id\":\""<<conductor_uuid(i+1)<<"\",\"type\":\"PHRASE\",\"slot\":"<<i+1<<",\"muteGroup\":0}";}
  s<<"],\"switches\":[{\"switchId\":1,\"traversal\":\"SEQUENTIAL\",\"transition\":\"IMMEDIATE\",\"gesture\":\"INSTANT\",\"steps\":[";
  for(unsigned i=0;i<5;++i){if(i)s<<',';unsigned source=i==4?2:i+1;
    s<<"{\"id\":\""<<conductor_uuid(20+i)<<"\",\"transition\":\"INHERIT\",\"layers\":[{\"id\":\""<<conductor_uuid(40+i)<<"\",\"block\":{\"id\":\""<<conductor_uuid(60+i)<<"\",\"type\":\"PHRASE\",\"sourceId\":\""<<conductor_uuid(source)<<"\",\"overrides\":{\"playMode\":{\"mode\":\"OVERRIDE\",\"value\":\""<<(i==0?"HOLD":"ONCE")<<"\"}}}}]}";
  }
  s<<"]}]}";auto text=s.str();std::vector<unsigned> result(text.begin(),text.end());
  check(conductor::validDocument(result),"five-step group-zero HOLD document validates");return result;
}
int main(int argc,char**argv){
  check(argc==2,"native source required");
  Host h(argv[1]);conductor_fixture(h);
  h.run("native_phrase_contract=2;native_free_time=1;ext_midi_bus=1;mem[INST_IN_BASE]=0;mem[INST_OUT_BASE]=3;mem[INST_LEVEL_BASE]=127;");
  h.run("i=0;loop(4,clear_layer(i);store_event(i,0,144,48+i,40,0);store_event(i,640,128,48+i,0,0);mem[LEN_BASE+i]=1024;mem[DECAY_BASE+i]=1;mem[VEL_BASE+i]=1;mem[PHRASE_GROUP_BASE+i]=0;i+=1;);");
  conductor_install(h,fiveSteps());
  for(unsigned step=0;step<6;++step){
    h.midi(144,110,100);auto events=h.events();unsigned pitch=step==5?48:step==4?49:48+step;
    check(countMidi(events,146,pitch)==1,"every step including 5-to-1 emits its actual MIDI attack");
    h.eq("mem[conductor_header(0)+3]",step%5,"five-step cursor wraps once");
    h.midi(128,110,0);events=h.events();
    check(countMidi(events,130,48)==0,"pedal release does not kill latched MASTER HOLD");
    for(unsigned n=0;n<12;++n){h.block();events=h.events();check(countMidi(events,130,48)==0,"recorded Off and natural boundary retain HOLD ownership");}
  }
  check(conductor_active(h)==2,"two legitimate HOLD occurrences remain after wrap");
  h.eq("mem[NOTE_REF_BASE+2*128+48]",2,"both same-pitch HOLD owners are retained");
  h.run("sw_stop_phrases();");h.block();auto events=h.events();
  check(countMidi(events,130,48)==1,"STOP releases final shared owner exactly once");
  check(conductor_active(h)==0,"STOP retires both HOLD occurrences");
  std::cout<<"PASS M5 HOLD wrap: "<<checks<<" checks\n";
}
