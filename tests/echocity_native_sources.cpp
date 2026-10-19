// Runs the real generated native EEL with the pinned ysfx. No JACK, HTTP,
// user's patches or instrument instances are opened by this executable.
#include "native_test_host.hpp"
#include "../headless/echocity_source_journal.hpp"
#include <algorithm>
#include <limits>

using echocity::SourceEvent;
using echocity::SourceAction;
using native_notes::Origin;
struct NativeHost:Host {
  std::array<double*,1024*6> sourceCells{};
  echocity::SourceJournal<> journal;
  unsigned blockFrames;
  explicit NativeHost(const char *path,bool subscribed=true,unsigned rate=48000,unsigned frames=128):Host(path,false),blockFrames(frames){
    ysfx_set_sample_rate(f,rate);ysfx_set_block_size(f,frames);ysfx_init(f);
    run("native_phrase_contract=2;native_free_time=1;slider9=1;panic_pending=0;"
        "test_i=0;loop(INST_CAP,mem[engine_addr(INST_ENABLED_BASE,test_i)]=0;test_i+=1;);"
        "mem[INST_ENABLED_BASE]=1;mem[INST_IN_BASE]=1;mem[INST_OUT_BASE]=1;"
        "mem[INST_LEVEL_BASE]=127;mem[INST_TRANSFORM_COUNT_BASE]=0;"
        "native_echo_read=0;native_echo_write=0;native_echo_overflow=0;");
    for(size_t j=0;j<sourceCells.size();++j)sourceCells[j]=NSEEL_VM_getramptr(f->vm.get(),29000000+j,nullptr);
    *ysfx_find_var(f,"native_echo_sources")=subscribed;
  }
  void block(){ysfx_process_float(f,nullptr,nullptr,0,0,blockFrames);}
  void midi(int st,int note,int velocity){
    uint8_t bytes[]={uint8_t(st),uint8_t(note),uint8_t(velocity)};ysfx_midi_event_t e{};
    e.size=3;e.data=bytes;check(ysfx_send_midi(f,&e),"real native input MIDI admitted");block();
  }
  std::vector<SourceEvent> sources(){
    auto *read=ysfx_find_var(f,"native_echo_read"),*write=ysfx_find_var(f,"native_echo_write");
    std::vector<SourceEvent> result;
    check(journal.consume(*read,*write,*ysfx_find_var(f,"native_echo_overflow"),blockFrames,
      [&](size_t j){return *sourceCells[j];},[&](const SourceEvent &e){result.push_back(e);}),"whole actual VM journal validates before source admission");
    *read=*write=0;
    return result;
  }
};
static size_t count(const std::vector<SourceEvent>& events,SourceAction action){
  return std::count_if(events.begin(),events.end(),[&](const SourceEvent&e){return e.action==action;});
}
struct BridgeFixture {
  echocity::SourceBridge<> bridge{48000};
  std::vector<native_notes::Event> output;
  void process(const std::vector<SourceEvent>& events,uint64_t start){
    auto emit=[&](const native_notes::Event &e){output.push_back(e);return true;};
    auto attack=[&](native_notes::Token token,const SourceEvent &e,uint64_t sample){
      echocity::Unit unit(48000);echocity::Configuration c{};c.id=100+e.key.instrument;c.instrument=e.key.instrument;
      c.interval=10;c.repeats=2;c.wet=.5;c.decay=1;
      check(unit.configure(c),"configure bounded echo unit for real source");
      check(unit.trigger(bridge.scheduler,token,e.key.channel,e.key.pitch,e.velocity,sample).ok,"admit actual EEL source into native echo scheduler");
    };
    uint64_t cursor=start;
    for(const auto &e:events){const uint64_t sample=start+e.offset;
      if(sample>cursor)bridge.scheduler.render(cursor,unsigned(sample-cursor),emit);
      const bool ok=bridge.apply(e,sample,attack,emit);
      if(!ok)fprintf(stderr,"source action=%u inst=%u phrase=%llu origin=%u ch=%u note=%u sample=%llu unmatched=%llu\n",unsigned(e.action),e.key.instrument,(unsigned long long)e.key.instance,unsigned(e.key.origin),e.key.channel,e.key.pitch,(unsigned long long)sample,(unsigned long long)bridge.unmatchedOffs);
      check(ok,"native source lifetime accepted");cursor=sample;
    }
    if(cursor<start+128)bridge.scheduler.render(cursor,unsigned(start+128-cursor),emit);
  }
};
static void decoderTests(){
  SourceEvent e{};double row[]={1,1,0,60*16+100*2048,0,127};
  check(echocity::decodeSource(row,e,128),"maximum offset accepted");
  for(unsigned field=0;field<6;++field){double old=row[field];for(double bad:{-1.,.5,std::numeric_limits<double>::infinity(),std::numeric_limits<double>::quiet_NaN()}){
    row[field]=bad;check(!echocity::decodeSource(row,e,128),"malformed source fields rejected without truncation");}row[field]=old;}
  row[5]=128;check(!echocity::decodeSource(row,e,128),"right block edge refused by wire decoder");
  row[5]=0;row[2]=1;check(!echocity::decodeSource(row,e,128),"live source cannot impersonate phrase instance");
}
int main(int argc,char**argv){
  check(argc==2,"generated native source argument");decoderTests();
  for(unsigned rate:{44100u,48000u}){
    const unsigned frames=rate==44100?512:128;
    NativeHost h(argv[1],true,rate,frames);echocity::SourceBridge<> bridge(rate);std::vector<native_notes::Event> delayed;
    auto emit=[&](const native_notes::Event &e){check(e.offset<frames,"delayed timestamp fits actual block size");delayed.push_back(e);return true;};
    auto attack=[&](native_notes::Token token,const SourceEvent &e,uint64_t now){
      echocity::Unit unit(rate);echocity::Configuration c{};c.instrument=e.key.instrument;c.id=100;c.interval=10;c.repeats=2;c.decay=1;
      check(unit.configure(c) && unit.trigger(bridge.scheduler,token,e.key.channel,e.key.pitch,e.velocity,now).ok,"actual sample-rate source reaches matching scheduler");
    };
    for(uint64_t t=0;t<rate/10;t+=frames){
      if(!t)h.midi(144,60,100);else if(t==2*frames)h.midi(128,60,0);else h.block();
      h.events();for(const auto &e:h.sources())check(bridge.apply(e,t+e.offset,attack,emit),"sample-rate source lifetime accepted");
      bridge.scheduler.render(t,frames,emit);
    }
    unsigned attacks=0,releases=0;for(const auto &e:delayed){
      if(e.on)check(e.sample==uint64_t(++attacks)*rate/100,"echo attack cadence follows actual sample rate");
      else check(e.sample==uint64_t(++releases)*rate/100+2*frames,"echo gate follows duration measured by actual host rate");
    }
    check(attacks==2 && releases==2 && delayed.size()==4,"both real host rates produce complete echo pairs");
    check(!bridge.scheduler.active() && !bridge.scheduler.sources.active(),"both real host rates leave no echo source");
  }
  {
    NativeHost h(argv[1]);BridgeFixture b;
    h.midi(144,60,100);auto on=h.sources();check(count(on,SourceAction::On)==1,"real Akai-like input produces one logical source");
    auto dry=h.events();check(dry.size()==1 && dry[0]==std::vector<int>({144,60,100}),"journal leaves actual dry note unchanged");b.process(on,0);
    h.midi(144,60,0);auto off=h.sources();check(count(off,SourceAction::Off)==1,"velocity-zero MIDI On closes source");h.events();b.process(off,128);
    for(uint64_t t=256;t<1280;t+=128){h.block();h.events();b.process(h.sources(),t);}
    check(b.output.size()==4,"real source produces two complete echo note pairs");
    check(b.output[0].sample==480 && b.output[1].sample==608 && b.output[2].sample==960 && b.output[3].sample==1088,"actual source duration seals exact echo boundaries");
    check(!b.bridge.scheduler.active() && !b.bridge.scheduler.sources.active(),"real live source leaves no delayed ownership");
  }
  {
    NativeHost h(argv[1]);h.run("mem[INST_ENABLED_BASE+1]=1;mem[INST_IN_BASE+1]=1;mem[INST_OUT_BASE+1]=1;mem[INST_LEVEL_BASE+1]=127;mem[INST_TRANSFORM_COUNT_BASE+1]=0;");
    h.midi(144,60,100);auto notes=h.sources();check(count(notes,SourceAction::On)==2,"same-pitch instruments survive physical coalescing");
    check(notes[0].key.instrument!=notes[1].key.instrument,"source carries stable instrument identity");
    check(h.events().size()==1,"existing physical duplicate suppression unchanged");
    h.midi(128,60,0);check(count(h.sources(),SourceAction::Off)==2,"both instrument source lifetimes close");h.events();
  }
  {
    NativeHost h(argv[1]);BridgeFixture b;
    h.run("clear_layer(0);store_event(0,0,144,48,100,0);store_event(0,128,128,48,0,0);mem[LEN_BASE]=256;mem[MODE_BASE]=1;mem[VEL_BASE]=1;mem[phrase_output_addr(0)]=0;a=phrase_admit_independent(0,0);");
    h.block();auto on=h.sources();check(count(on,SourceAction::On)==1,"actual phrase playback produces owned source");
    check(on.back().key.origin==Origin::Phrase && on.back().key.instance==uint64_t(h.val("a")),"phrase identity is monotonic ID, not reusable voice slot");
    b.process(on,0);h.events();
    h.run("mem[INST_TRANSPOSE_BASE]=12;mem[INST_OUT_BASE]=7;");
    for(uint64_t t=128;t<1536;t+=128){h.block();h.events();b.process(h.sources(),t);}
    check(b.output.size()==4,"phrase captured output releases produce complete echo pairs");
    for(const auto &e:b.output)check(e.pitch==48 && e.channel==0,"saved source output survives route parameter edits");
    check(!b.bridge.scheduler.active() && !b.bridge.scheduler.sources.active(),"phrase echo records fully retired");
  }
  {
    NativeHost h(argv[1]);BridgeFixture b;
    h.midi(144,60,100);b.process(h.sources(),0);h.events();
    for(uint64_t t=128;t<512;t+=128){h.block();h.events();b.process(h.sources(),t);}
    check(b.output.size()==1 && b.output[0].on,"one real source echo is sounding before deletion");
    h.run("i_clear_runtime(0);");auto cleared=h.sources();check(count(cleared,SourceAction::RemoveInstrument)==1,"outside-DSP deletion persists until host drain");
    b.process(cleared,512);check(b.output.size()==2 && !b.output.back().on,"deletion emits sounding echo release and discards pending attacks");
    check(!b.bridge.scheduler.active() && !b.bridge.scheduler.sources.active(),"deletion releases held source leases");
  }
  {
    NativeHost h(argv[1]);BridgeFixture b;
    h.run("clear_layer(0);store_event(0,0,144,48,100,0);store_event(0,4096,128,48,0,0);mem[LEN_BASE]=8192;mem[MODE_BASE]=1;mem[VEL_BASE]=1;mem[phrase_output_addr(0)]=0;a=phrase_admit_independent(0,0);");
    h.midi(144,60,100);b.process(h.sources(),0);h.events();
    check(b.bridge.scheduler.sources.active()==2,"live and phrase sources coexist in native bridge");
    h.run("sw_stop_phrases();");auto stop=h.sources();check(count(stop,SourceAction::StopPhrases)==1,"phrase STOP is explicit in source journal");
    b.process(stop,128);check(b.bridge.scheduler.sources.active()==1,"STOP cancels phrase delays and preserves live source");
    h.run("reset_note_runtime();");b.process(h.sources(),256);check(!b.bridge.scheduler.sources.active() && !b.bridge.scheduler.active(),"global reset cancels every remaining echo source");
  }
  {
    NativeHost h(argv[1]);BridgeFixture b;
    h.midi(144,60,100);b.process(h.sources(),0);h.events();
    h.midi(144,60,80);b.process(h.sources(),128);h.events();
    check(b.bridge.scheduler.sources.active()==2,"overlapping repeated physical input has distinct FIFO sources");
    h.midi(128,60,0);b.process(h.sources(),256);h.events();
    h.midi(144,60,0);b.process(h.sources(),384);h.events();
    for(uint64_t t=512;t<1664;t+=128){h.block();h.events();b.process(h.sources(),t);}
    check(b.output.size()==8 && !b.bridge.unmatchedOffs,"both repeated source releases pair with their own echoes");
    check(!b.bridge.scheduler.active() && !b.bridge.scheduler.sources.active(),"FIFO input leaves no retained delayed source");
  }
  {
    NativeHost h(argv[1]);BridgeFixture b;
    h.run("clear_layer(0);clear_layer(1);store_event(0,0,144,48,100,0);store_event(0,4096,128,48,0,0);store_event(1,0,144,72,100,0);store_event(1,4096,128,72,0,0);mem[LEN_BASE]=8192;mem[LEN_BASE+1]=8192;mem[MODE_BASE]=1;mem[MODE_BASE+1]=1;mem[VEL_BASE]=1;mem[VEL_BASE+1]=1;mem[phrase_output_addr(0)]=0;mem[phrase_output_addr(1)]=0;a=phrase_admit_independent(0,0);ag=mem[instance_header(0)+1];b=phrase_admit_independent(1,0);");
    h.block();b.process(h.sources(),0);h.events();
    check(b.bridge.scheduler.sources.active()==2,"parallel phrases retain separate native identities");
    h.run("instance_request_stop(a,ag);");h.block();auto stopped=h.sources();
    check(count(stopped,SourceAction::StopInstance)==1,"targeted phrase STOP carries exactly one instance ID");
    b.process(stopped,128);h.events();check(b.bridge.scheduler.sources.active()==1 && b.bridge.scheduler.active()==2,"targeted STOP leaves other phrase echoes intact");
  }
  {
    NativeHost h(argv[1]);BridgeFixture b;
    h.run("mem[INST_TRANSFORM_COUNT_BASE]=1;mem[INST_TRANSFORM_TYPE_BASE]=3;param_apply(0,11,1);");
    h.eq("mem[INST_NOTE_MODE_BASE]",1,"native MONO mode is really enabled");
    h.midi(144,60,100);b.process(h.sources(),0);h.events();
    h.midi(144,48,90);b.process(h.sources(),128);h.events();
    h.midi(128,48,0);b.process(h.sources(),256);h.events();
    h.midi(128,60,0);b.process(h.sources(),384);h.events();
    for(uint64_t t=512;t<1664;t+=128){h.block();h.events();b.process(h.sources(),t);}
    check(!b.bridge.unmatchedOffs && !b.bridge.scheduler.sources.active(),"actual MONO replacement / revoice lifetimes remain balanced");
    check(!b.bridge.scheduler.active(),"MONO revoice leaves no echo lease");
    check(b.output.size()==12,"MONO change and restoration both produce their own complete echoes");
  }
  {
    NativeHost h(argv[1]);BridgeFixture b;
    h.midi(144,60,100);b.process(h.sources(),0);h.events();
    h.midi(176,64,127);auto pedal=h.sources();check(pedal.empty(),"sustain control is not a spurious note source");b.process(pedal,128);h.events();
    h.midi(128,60,0);b.process(h.sources(),256);h.events();
    h.midi(176,64,0);b.process(h.sources(),384);h.events();
    for(uint64_t t=512;t<1536;t+=128){h.block();h.events();b.process(h.sources(),t);}
    check(!b.bridge.unmatchedOffs && !b.bridge.scheduler.active() && !b.bridge.scheduler.sources.active(),"source note lifetime closes under sustain without held echo ownership");
  }
  {
    NativeHost h(argv[1],false);h.midi(144,60,100);check(h.sources().empty(),"unsubscribed production path creates no source traffic");
    check(h.events()==std::vector<std::vector<int>>({{144,60,100}}),"unsubscribed MIDI remains identical");
    h.run("native_echo_sources=1;test_i=0;loop(1025,native_echo_event(1,1,0,0,60,100,0,0);test_i+=1;);");
    check(h.val("native_echo_write")==1024 && h.val("native_echo_overflow")==1,"journal overload cannot overwrite an earlier release");
    unsigned visited=0;
    check(!h.journal.consume(0,h.val("native_echo_write"),h.val("native_echo_overflow"),128,
      [&](size_t j){return *h.sourceCells[j];},[&](const SourceEvent&){++visited;}),"overflow rejects whole block before native admission");
    check(!visited && h.journal.needsRecovery,"overflow cannot produce partial echoes or silently drop releases");
  }
  {
    NativeHost h(argv[1]);h.run("mem[INST_TRANSFORM_COUNT_BASE]=1;mem[INST_TRANSFORM_TYPE_BASE]=5;param_apply(0,3,1);");
    h.midi(144,60,100);check(count(h.sources(),SourceAction::On)==0,"ARP input chord is not mislabelled as emitted POLY source");h.events();
  }
  {
    // One fixture-only trigger invokes the unchanged production panic function
    // inside a real DSP block. No replacement panic/renderer implementation.
    std::ifstream input(argv[1]);std::string source((std::istreambuf_iterator<char>(input)),{});
    const std::string anchor="instance_output_open=1;instance_output_fault=0;";
    const auto at=source.find(anchor);check(at!=std::string::npos,"real native DSP entry fixture anchor");
    source.insert(at+anchor.size(),"test_native_echo_panic>0?(native_panic_at(test_native_echo_panic-1);test_native_echo_panic=0;);");
    const std::string path=std::string(argv[1])+".panic-fixture.jsfx";
    {std::ofstream output(path);output<<source;check(output.good(),"write private DSP trigger fixture");}
    NativeHost h(path.c_str());BridgeFixture b;h.midi(144,60,100);b.process(h.sources(),0);h.events();
    h.run("test_native_echo_panic=97;");h.block();auto panic=h.sources();
    check(count(panic,SourceAction::Reset)==1 && count(panic,SourceAction::RemoveInstrument)>0,"real native PANIC journals full ownership reset");
    for(const auto &e:panic)check(e.offset==96,"PANIC and all instrument cancellations preserve in-block offset");
    ysfx_midi_event_t event{};bool released=false;
    while(ysfx_receive_midi(h.f,&event))if(event.size==3 && (event.data[0]&240)==128 && event.data[1]==60){
      check(event.offset==96,"actual PANIC MIDI release retains same timestamp as source cancellation");released=true;
    }
    check(released,"real native PANIC emits held dry note release");b.process(panic,128);
    check(!b.bridge.scheduler.active() && !b.bridge.scheduler.sources.active(),"real PANIC cancels all pending echo sources");
    std::remove(path.c_str());
  }
  printf("PASS %d actual native EEL source / ECHOCITY lifecycle checks\n",checks);
}
