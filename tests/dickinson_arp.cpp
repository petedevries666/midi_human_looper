// Real generated native EEL: emitted MIDI, not a selector simulation.
#include "native_test_host.hpp"
#include <algorithm>
struct Rig {
 Host h;std::vector<int> notes;std::map<int,int> owned;unsigned frame=0;bool trace=false;
 Rig(const char*path,int mode,int max,int once):h(path,false){
  ysfx_set_sample_rate(h.f,48000);ysfx_set_block_size(h.f,256);ysfx_init(h.f);
  ysfx_time_info_t t{};t.tempo=300;ysfx_set_time_info(h.f,&t);
  h.run("slider9=1;panic_pending=0;native_phrase_contract=2;j=1;loop(7,mem[engine_addr(INST_ENABLED_BASE,j)]=0;j+=1;);mem[INST_LEVEL_BASE]=127;mem[INST_TRANSFORM_COUNT_BASE]=1;mem[INST_TRANSFORM_TYPE_BASE]=5;param_apply(0,3,1);param_apply(0,4,"+std::to_string(mode)+");param_apply(0,5,16);param_apply(0,6,.5);param_apply(0,27,"+std::to_string(max)+");param_apply(0,28,"+std::to_string(once)+");");
 }
 void send(int pitch,int velocity){uint8_t d[]={uint8_t(velocity?144:128),uint8_t(pitch),uint8_t(velocity)};ysfx_midi_event_t e{};e.size=3;e.data=d;check(ysfx_send_midi(h.f,&e),"input admitted");}
 void play(unsigned frames){for(unsigned j=0;j<frames;j+=256,frame+=256){ysfx_process_float(h.f,nullptr,nullptr,0,0,256);ysfx_midi_event_t e{};
  while(ysfx_receive_midi(h.f,&e)){if(e.size!=3)continue;check(e.offset<256,"MIDI timestamp in block");unsigned k=e.data[0]&240,n=e.data[1];
   if(k==144 && e.data[2]){check(owned[n]==0,"no unpaired overlapping output attack");owned[n]++;notes.push_back(n);}
   else if(k==128 || (k==144 && !e.data[2])){check(owned[n]>0,"actual Note Off owns a preceding attack");owned[n]--;}
   if(trace && (k==144||k==128))printf("MIDI %u %u %u %u\n",frame+e.offset,e.data[0],n,e.data[2]);
  }
 }}
 void silence(){for(auto kv:owned)check(kv.second==0,"all emitted notes released");}
};
int main(int argc,char**argv){check(argc==2,"native source required");
 for(int max=1;max<=4;++max){Rig r(argv[1],9,max,0);r.trace=true;printf("STEP_MAX %d\n",max);
  for(int n:{48,50,52,54,56,58,60,62})r.send(n,100);
  r.play(48000);check(r.notes.size()>60,"continuous CLIMB emits MIDI");bool full=false;
  for(unsigned i=1;i<r.notes.size();++i){int delta=std::abs(r.notes[i]-r.notes[i-1])/2;check(delta>=1&&delta<=max,"step distance honours configured maximum");full|=delta==max;}
  check(full,"configured maximum is actually visited");for(int n:{48,50,52,54,56,58,60,62})r.send(n,0);r.play(4800);r.silence();
 }
 for(int mode=0;mode<=12;++mode){Rig r(argv[1],mode,2,1);printf("ONCE_MODE %d\n",mode);r.trace=true;
  for(int n:{48,52,55,60})r.send(n,100);r.play(48000*4);auto size=r.notes.size();
  check(size>0,"ONCE generated real notes");
  if(mode<9)check(size==unsigned(mode==5||mode==7?8:4),"one complete random/pool/motif traversal");
  else{check(r.notes.front()==(mode==10||mode==12?60:48),"CLIMB origin");check(r.notes.back()==r.notes.front(),"CLIMB returns to origin");check(std::find(r.notes.begin(),r.notes.end(),mode==10||mode==12?48:60)!=r.notes.end(),"CLIMB visits far boundary before ending");}
  r.play(48000);check(r.notes.size()==size,"held chord never auto-restarts ONCE");r.silence();
  // Same pitch overlap doesn't change the effective held set or restart.
  r.send(48,100);r.play(2400);r.send(48,0);r.play(2400);check(r.notes.size()==size,"same-pitch overlapping voice does not retrigger");
  for(int n:{48,52,55,60})r.send(n,0);r.play(256);r.silence();
  for(int n:{48,52,55,60})r.send(n,100);r.play(48000*4);check(r.notes.size()==2*size || mode>=9,"release/retrigger admits new traversal");r.silence();
  r.h.run("send_all_notes_off();reset_note_runtime();");r.play(256);r.h.eq("mem[ARP_ACTIVE_NOTE_BASE]",-1,"PANIC clears active ARP");
 }
 // A changed effective pitch set is a new gesture; active release pairing survives.
 {Rig r(argv[1],1,2,1);for(int n:{48,52,55})r.send(n,100);r.play(256);r.send(60,100);r.play(48000);
  check(r.notes==std::vector<int>({48,48,52,55,60}),"chord change starts one fresh traversal from its boundary");r.silence();}
 // Continuous never uses the ONCE budget, including all native mode families.
 for(int mode=0;mode<=12;++mode){Rig r(argv[1],mode,2,0);for(int n:{48,52,55,60})r.send(n,100);r.play(48000);check(r.notes.size()>60,"all modes remain CONTINUOUS by default");for(int n:{48,52,55,60})r.send(n,0);r.play(4800);r.silence();}
 printf("PASS %d DICKINSON actual EEL MIDI checks\n",checks);
}
