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
  printf("PASS portable shared-EEL2 MIDI parity at 44100/48000 Hz (%d checks)\n",checks);
}
