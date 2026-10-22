#include "native_test_host.hpp"
#include "conductor_baseline_cases.hpp"
#include "conductor_execution_cases.hpp"
static std::vector<unsigned> actionModel(const std::string& action,const std::string& target,bool phrase=false,const char* trigger="PRESS"){
 std::string s="{\"version\":1,\"sources\":[{\"id\":\""+conductor_uuid(1)+"\",\"type\":\"PHRASE\",\"slot\":1}],\"switches\":[{\"switchId\":1,\"traversal\":\"SEQUENTIAL\",\"transition\":\"IMMEDIATE\",\"gesture\":\"INSTANT\",\"steps\":[{\"id\":\""+conductor_uuid(10)+"\",\"transition\":\"INHERIT\",\"layers\":[{\"id\":\""+conductor_uuid(20)+"\",\"block\":";
 s+=phrase?"{\"id\":\""+conductor_uuid(30)+"\",\"type\":\"PHRASE\",\"sourceId\":\""+conductor_uuid(1)+"\",\"overrides\":{\"playMode\":{\"mode\":\"OVERRIDE\",\"value\":\"HOLD\"}}}":"null";
 s+="},{\"id\":\""+conductor_uuid(21)+"\",\"block\":{\"id\":\""+conductor_uuid(31)+"\",\"type\":\"ACTION\",\"action\":\""+action+"\",\"target\":"+target+",\"trigger\":\""+trigger+"\"}}]}]}]}";
 std::vector<unsigned> bytes(s.begin(),s.end());check(conductor::validDocument(bytes),"typed action validates");return bytes;
}
static void setup(Host&h){conductor_fixture(h);h.run("native_phrase_contract=2;native_free_time=1;ext_midi_bus=1;mem[MODE_BASE]=2;mem[MODE_BASE+1]=2;trigger_request=0;");h.block();h.events();}
int main(int argc,char**argv){
 check(argc==2,"generated source required");
 const std::string all="{\"type\":\"ALL_PHRASES\"}",self="{\"type\":\"SWITCH\",\"switchId\":1}",source="{\"type\":\"PHRASE\",\"sourceId\":\""+conductor_uuid(1)+"\"}";
 auto rejectsTrigger=[&](const char* trigger){
  auto bytes=actionModel("STOP",all);
  std::string text(bytes.begin(),bytes.end());
  const std::string original="\"trigger\":\"PRESS\"";
  auto at=text.find(original);
  check(at!=std::string::npos,"valid PRESS action fixture has trigger");
  text.replace(at,original.size(),std::string("\"trigger\":\"")+trigger+"\"");
  std::vector<unsigned> invalid(text.begin(),text.end());
  check(!conductor::validDocument(invalid),"unsupported Conductor action trigger is rejected, not reinterpreted as PRESS");
 };
 rejectsTrigger("LONG_HOLD");
 rejectsTrigger("RELEASE");
 for(const char* action:{"STOP","PANIC","STOP_RESET"}){
  Host h(argv[1]);setup(h);conductor_install(h,actionModel(action,std::string(action)=="STOP_RESET"?self:all));
  h.midi(144,110,100);auto events=h.events();check(conductor_count(events,128,48)==1,"action releases sounding phrase");check(conductor_active(h)==0,"action retires owners");
  h.midi(128,110,0);h.events();check(conductor_active(h)==0,"release never replays action");
 }
 {
  Host h(argv[1]);setup(h);h.run("trigger_request=1;");h.block();h.events();
  conductor_install(h,actionModel("STOP",source,true));h.midi(144,110,100);auto events=h.events();
  check(conductor_count(events,128,48)==1&&conductor_count(events,144,48)==1,"targeted STOP then same-source admission emits Off before new On");
  check(events.size()>=2&&events[0][0]==128&&events[1][0]==144,"STOP precedes fresh attack");
  check(conductor_active(h)==2,"targeted stop preserves unrelated owner and new admission");
 }
 {
  Host h(argv[1]);setup(h);conductor_install(h,actionModel("PANIC",all,true));h.midi(144,110,100);
  check(h.events().empty(),"conflicting PANIC plus phrase emits nothing");check(conductor_active(h)==1,"barrier conflict preserves existing voice");h.eq("mem[conductor_header(0)+4]",4,"barrier conflict explicit refusal");
 }
 {
  Host h(argv[1]);setup(h);conductor_install(h,actionModel("RESET_CURSOR",self));h.midi(144,110,100);h.events();
  h.eq("mem[conductor_header(0)+3]",-1,"self reset leaves next step at beginning");check(conductor_active(h)==1,"reset cursor does not stop unrelated notes");
 }
 {
  Host h(argv[1]);setup(h);conductor_install(h,actionModel("STOP",source,false,"HOLD"));h.midi(144,110,100);h.events();check(conductor_active(h)==1,"HOLD action does not execute on PRESS");
  h.run("mem[sw_rt(0)+1]=sw_clock-srate;");h.block();auto events=h.events();check(conductor_count(events,128,48)==1&&conductor_active(h)==0,"HOLD action executes once at its phase");
  h.block();check(h.events().empty(),"repeated HOLD notification cannot repeat action");
 }
 {
  Host h(argv[1]);setup(h);conductor_install(h,actionModel("PAUSE",all));h.midi(144,110,100);check(h.events().empty(),"unsupported legacy action never falls back");check(conductor_active(h)==1,"unsupported action preserves notes");
 }
 {
  Host h(argv[1]);setup(h);conductor_install(h,actionModel("STOP",all,true,"HOLD"));h.midi(144,110,100);
  check(h.events().empty(),"global STOP with other phase is an explicit barrier conflict");check(conductor_active(h)==1,"cross-phase conflict preserves original owner");
 }
 {
  Host h(argv[1]);setup(h);auto missing="{\"type\":\"PHRASE\",\"sourceId\":\""+conductor_uuid(99)+"\"}";
  conductor_install(h,actionModel("STOP",missing,true));h.midi(144,110,100);
  check(h.events().empty(),"missing action target rejects new phrase atomically");check(conductor_active(h)==1,"missing target preserves original owner");
 }
 printf("PASS %d actual native Conductor action checks\n",checks);
}
