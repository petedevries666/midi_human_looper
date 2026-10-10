// Executes the shared EEL2 engine at studio/live sample rates, no mathematical
// stand-in for note dispatch. The portable adapter scales source timestamps.
#define main expression_regression_main
#include "expression_host.cpp"
#undef main
struct Note { double seconds; std::vector<int> bytes; };
static std::vector<Note> replay(const char* path, unsigned rate) {
  Host h(path, false);
  ysfx_set_sample_rate(h.f,rate);ysfx_set_block_size(h.f,128);ysfx_init(h.f);
  h.run("mem[INST_RANGE_MODE_BASE]=0;mem[INST_TRANSFORM_COUNT_BASE]=0;"
        "mem[COUNT_BASE]=4;mem[MODE_BASE]=0;mem[VEL_BASE]=1;slider9=1;"
        "mem[DECAY_BASE]=1;loop_len_samples=srate;mem[LEN_BASE]=srate;"
        "mem[0]=0;mem[1]=146;mem[2]=60;mem[3]=100;mem[4]=0;"
        "mem[5]=srate*.05;mem[6]=146;mem[7]=64;mem[8]=91;mem[9]=0;"
        "mem[10]=srate*.25;mem[11]=130;mem[12]=60;mem[13]=30;mem[14]=0;"
        "mem[15]=srate*.5;mem[16]=130;mem[17]=64;mem[18]=20;mem[19]=0;"
        "state=STATE_PLAYING;play_sample_pos=0;slider5=0;mem[TRIG_BASE]=1;");
  std::vector<Note> notes;
  for(unsigned frame=0;frame<rate*.75;frame+=128) {
    h.block();ysfx_midi_event_t e{};
    while(ysfx_receive_midi(h.f,&e)) {
      if(e.size==3 && ((e.data[0]&240)==144 || (e.data[0]&240)==128))
        notes.push_back({(frame+e.offset)/double(rate),{e.data[0],e.data[1],e.data[2]}});
    }
  }
  return notes;
}
int main(int argc,char**argv) {
  if(argc!=2)return 2;
  auto a=replay(argv[1],44100),b=replay(argv[1],48000);
  check(a.size()==4 && b.size()==4,"four source notes emitted by both adapters");
  const double expected[]={0,.05,.25,.5};
  for(unsigned i=0;i<4;++i) {
    check(a[i].bytes==b[i].bytes,"pitch/velocity/channel and note pairing parity");
    check(std::abs(a[i].seconds-b[i].seconds)<.003,"studio/live block timing parity");
    check(std::abs(a[i].seconds-expected[i])<.003,"source-time playback");
  }
  Host bridge(argv[1],false);ysfx_set_sample_rate(bridge.f,48000);ysfx_init(bridge.f);
  bridge.run("state=STATE_PLAYING;gmem[19]=1;gmem[20]=11;gmem[0]=0;");bridge.block();
  bridge.eq("gmem[21]",11,"bridge rejection acknowledges exact request");
  bridge.eq("gmem[22]",0,"REAPER bridge refuses running playback");
  bridge.run("state=STATE_STOPPED;panic_pending=1;");bridge.block();bridge.events();
  bridge.run("gmem[19]=1;gmem[20]=12;");bridge.block();
  bridge.eq("gmem[22]",1,"REAPER bridge captures stopped patch");
  bridge.eq("gmem[3]",171649,"shared portable schema dimensions");
  const unsigned markers[]={164892,165316,165829,166494,166828,168366};unsigned markerIndex=0;
  for(const char* name : {"WORK_MEM_SIZE","SW_LEGACY_PAYLOAD","CC_LEGACY_PAYLOAD","TF_LEGACY_PAYLOAD","DS_LEGACY_PAYLOAD","I_LEGACY_PAYLOAD"}) check(bridge.val(name)==markers[markerIndex++],"portable layout agrees with actual JSFX schema");
  bridge.eq("gmem[17]",48000,"source adapter rate advertised");
  bridge.eq("payload_addr(164851)",bridge.val("INST_TRANSFORM_COUNT_BASE"),"portable legacy chain layout");
  bridge.eq("payload_addr(164854)",bridge.val("INST_TRANSFORM_TYPE_BASE"),"portable legacy instance layout");
  bridge.eq("payload_addr(168474)",bridge.val("I_INST_TRANSFORM_COUNT_BASE"),"portable dynamic chain layout");
  bridge.eq("payload_addr(169964)",bridge.val("I_INST_TRANSFORM_TYPE_BASE"),"portable dynamic instance layout");
  bridge.eq("payload_addr(166513)",bridge.val("TF_RECORD_BASE"),"portable legacy type-record layout");
  bridge.eq("payload_addr(171124)",bridge.val("I_TF_RECORD_BASE"),"portable dynamic type-record layout");

  bridge.run("gmem[10]=4;gmem[19]=2;gmem[20]=13;");bridge.block();
  bridge.eq("gmem[21]",13,"REAPER bridge apply acknowledgement");
  bridge.eq("gmem[22]",1,"REAPER bridge validated apply");
  bridge.eq("slider8",4,"actual EEL2 configuration applied");
  bridge.run("gmem[19]=1;gmem[20]=14;");bridge.block();
  bridge.run("gmem[2]=999;gmem[10]=9;gmem[19]=2;gmem[20]=14;");bridge.block();
  bridge.eq("gmem[22]",0,"invalid REAPER schema rejected");
  bridge.eq("slider8",4,"failed application preserves prior configuration");
  bridge.run("gmem[19]=1;gmem[20]=15;");bridge.block();
  bridge.run("slider9=.75;gmem[19]=2;gmem[20]=16;");bridge.block();
  bridge.eq("gmem[22]",0,"local edit after capture rejects PULL compare-and-apply");
  bridge.eq("slider9",.75,"local edit retained after rejected PULL");
  bridge.run("mem[SUSTAIN_REF_BASE]=1;gmem[19]=1;gmem[20]=17;");bridge.block();
  bridge.eq("gmem[22]",0,"held sustain rejects destructive capture");
  bridge.run("mem[SUSTAIN_REF_BASE]=0;");

  printf("PASS portable shared-EEL2 MIDI parity at 44100/48000 Hz (%d checks)\n",checks);
}
