// Execute the real generated EEL and inspect actual emitted MIDI.
#include "native_test_host.hpp"
#include <algorithm>
int main(int argc,char**argv){
 check(argc==2,"expanded native source argument");
 for(int mode=3;mode<=12;++mode){
  Host h(argv[1],false);ysfx_set_sample_rate(h.f,44100);ysfx_set_block_size(h.f,512);ysfx_init(h.f);
  ysfx_time_info_t time{};time.tempo=300;ysfx_set_time_info(h.f,&time);
  h.run("slider9=1;panic_pending=0;test_i=1;loop(7,mem[engine_addr(INST_ENABLED_BASE,test_i)]=0;test_i+=1;);mem[INST_LEVEL_BASE]=127;mem[INST_TRANSFORM_COUNT_BASE]=1;mem[INST_TRANSFORM_TYPE_BASE]=5;param_apply(0,3,1);param_apply(0,4,"+std::to_string(mode)+");param_apply(0,5,16);param_apply(0,6,.5);");
  h.eq("mem[INST_ARP_MODE_BASE]",mode,"native parameter accepts new mode");
  for(int pitch:{48,52,55,60,64,67}){uint8_t data[]={144,uint8_t(pitch),100};ysfx_midi_event_t e{};e.size=3;e.data=data;check(ysfx_send_midi(h.f,&e),"input note admitted");}
  std::vector<int> notes;std::map<int,int> sounding;
  for(unsigned frame=0;frame<44100*5;frame+=512){
   ysfx_process_float(h.f,nullptr,nullptr,0,0,512);ysfx_midi_event_t e{};
   while(ysfx_receive_midi(h.f,&e))if(e.size==3){
    check(e.offset<512,"timestamp remains in block");int kind=e.data[0]&240,n=e.data[1];
    if(kind==144&&e.data[2]){check(n==48||n==52||n==55||n==60||n==64||n==67,"only held pitches emitted");check(!sounding[n],"no overlapping same-note ownership");++sounding[n];notes.push_back(n);}
    if(kind==128){check(sounding[n]>0,"release has matching attack");--sounding[n];}
   }
  }
  check(notes.size()>100,"actual MIDI arp continued");
  for(unsigned i=1;i<notes.size();++i){
   if(mode==3||mode==4||mode==6||mode>=9)check(notes[i]!=notes[i-1],"no consecutive duplicate");
   if(mode==6){std::vector<int> pool={48,52,55,60,64,67};auto a=std::find(pool.begin(),pool.end(),notes[i]),b=std::find(pool.begin(),pool.end(),notes[i-1]);check(std::abs(a-b)==1,"walk visits neighbours");}
   if(mode==5)check(notes[i]==notes[i%8],"random loop repeats its eight-step motif");
   if(mode==9)check(notes[i]>notes[i-1]||notes[i-1]==67,"climb up wraps only at top");
   if(mode==10)check(notes[i]<notes[i-1]||notes[i-1]==48,"climb down wraps only at bottom");
   if(mode==9&&notes[i-1]==67)check(notes[i]==48,"climb up restarts at lowest pitch");
   if(mode==10&&notes[i-1]==48)check(notes[i]==67,"climb down restarts at highest pitch");
  }
  if(mode==4)for(unsigned i=0;i+6<=notes.size();i+=6){std::set<int> bag(notes.begin()+i,notes.begin()+i+6);check(bag.size()==6,"bag visits each held pitch once");}
  if(mode==11||mode==12){int direction=mode==11?1:-1;check(notes[0]==(direction>0?48:67),"climb initial endpoint");for(unsigned i=1;i<notes.size();++i){if(notes[i-1]==67)direction=-1;if(notes[i-1]==48)direction=1;check((notes[i]-notes[i-1])*direction>0,"climb changes direction only at endpoint");}}
  h.run("send_all_notes_off();reset_note_runtime();");h.eq("mem[ARP_ACTIVE_NOTE_BASE]",-1,"panic clears arp ownership");
  // Set a single held pitch directly, then exercise the same native selector.
  h.run("memset(ARP_HELD_COUNT_BASE,0,128);mem[ARP_HELD_COUNT_BASE+60]=1;test_pick=native_arp_pick(0,"+std::to_string(mode)+");");h.eq("test_pick",60,"one-note fallback remains playable");
 }
 Host h(argv[1],false);ysfx_init(h.f);
 h.run("mem[CONDUCTOR_BASE+3]=3;mem[sw_rt(0)+22]=1;sw_action(1,SW_STOP_RESET,SW_COUNT,0);");
 h.eq("mem[CONDUCTOR_BASE+3]",-1,"STOP+RESET ALL clears Conductor cursor");h.eq("mem[sw_rt(0)+22]",0,"STOP+RESET cancels pending advance");
 printf("PASS %d native random ARP MIDI and Conductor reset checks\n",checks);
}
