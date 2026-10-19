// Real native EEL: widened gain, primary/extra blocks and MIDI saturation.
#include "native_test_host.hpp"
int main(int argc,char**argv){
 check(argc==2,"generated native source required");Host h(argv[1]);
 h.run("native_phrase_contract=2;native_free_time=1;ext_midi_bus=1;slider9=1;panic_pending=0;"
       "j=0;loop(INST_CAP,mem[engine_addr(INST_ENABLED_BASE,j)]=0;j+=1;);"
       "mem[INST_ENABLED_BASE]=1;mem[INST_IN_BASE]=1;mem[INST_OUT_BASE]=1;mem[INST_LEVEL_BASE]=127;"
       "mem[INST_TRANSFORM_COUNT_BASE]=1;mem[INST_TRANSFORM_TYPE_BASE]=4;param_apply(0,0,8);");
 h.block();h.events();h.eq("param_max(0)",8,"native gain range reaches eight");
 h.eq("param_scale(0,1)",8,"normalized controller endpoint reaches eight");
 h.eq("param_max(17)",3,"phrase velocity range preserved");
 for(const auto pair: {std::pair<int,int>{10,80},{20,127},{127,127}}){
  h.midi(144,60,pair.first);auto events=h.events();
  check(events.size()==1 && events[0]==std::vector<int>({144,60,pair.second}),"native gain and 127 saturation");
  h.midi(144,60,0);events=h.events();check(events.size()==1 && (events[0][0]&240)==128,"velocity-zero remains a note release");
 }
 h.run("param_apply(0,0,99);");h.block();h.events();h.eq("mem[INST_VEL_BASE]",8,"native manual value clamps at eight");
 h.run("tf_submit(0,1,4);");h.block();h.events();
 h.eq("mem[INST_TRANSFORM_COUNT_BASE]",2,"extra velocity block admitted");
 h.run("mem[cc_cfg(cc_index(0,7))+2]=8;");h.block();h.events();
 h.midi(144,61,1);auto events=h.events();check(events.size()==1 && events[0]==std::vector<int>({144,61,64}),"primary and extra gains both use widened range");
 h.midi(128,61,0);h.events();
 printf("PASS %d actual native velocity gain / MIDI saturation checks\n",checks);
}
