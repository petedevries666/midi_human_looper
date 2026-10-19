#include "../headless/echocity_runtime.hpp"
#include <cstdio>
#include <cstdlib>
#include <new>
static bool realtime=false;static unsigned checks=0,allocations=0;
void *operator new(size_t n){if(realtime){++allocations;throw std::bad_alloc();}if(void*p=std::malloc(n?n:1))return p;throw std::bad_alloc();}
void *operator new[](size_t n){return ::operator new(n);}void operator delete(void*p)noexcept{std::free(p);}void operator delete[](void*p)noexcept{std::free(p);}
void operator delete(void*p,size_t)noexcept{std::free(p);}void operator delete[](void*p,size_t)noexcept{std::free(p);}
#define CHECK(x) do{++checks;if(!(x)){realtime=false;fprintf(stderr,"FAIL %u: %s\n",__LINE__,#x);std::exit(1);}}while(false)
using namespace echocity;using namespace native_notes;
struct Packet {uint64_t sample;bool on;unsigned ch,pitch,velocity;};
struct Output {
 std::array<Packet,8192> events{};size_t count=0,limit=8192;
 bool operator()(uint64_t sample,bool on,uint8_t ch,uint8_t pitch,uint8_t velocity,bool retrigger){
  const unsigned need=on&&retrigger?2:1;if(count+need>limit)return false;
  if(on&&retrigger)events[count++]={sample,false,ch,pitch,0};events[count++]={sample,on,ch,pitch,velocity};return true;
 }
};
static Configurations settings(){Configurations c{};c[0].id=c[0].instrument=1;c[0].interval=10;c[0].repeats=2;c[0].decay=1;return c;}
static SourceEvent edge(bool on,Origin origin=Origin::Live,uint64_t instance=0,unsigned pitch=60){return {on?SourceAction::On:SourceAction::Off,{1,origin,instance,0,uint8_t(pitch)},on?100u:0u,0};}
int main(){
 {
  Runtime r(8000);Output out;auto emit=[&](auto...args){return out(args...);};r.configure(settings());
  realtime=true;r.begin(0,emit);CHECK(r.source(edge(true),0,120,emit));CHECK(r.source(edge(false),40,120,emit));r.render(0,256,emit);realtime=false;
  CHECK(out.count==6 && out.events[0].velocity==50);const uint64_t expected[]={0,40,80,120,160,200};
  for(unsigned j=0;j<6;++j)CHECK(out.events[j].sample==expected[j]);CHECK(!r.sources()&&!r.pending()&&!r.failed&&!allocations);
 }
 {
  Runtime r(8000);Output out;auto emit=[&](auto...args){return out(args...);};r.configure(settings());
  realtime=true;CHECK(r.source(edge(true),0,120,emit));r.render(0,200,emit);CHECK(r.source(edge(false),200,120,emit));r.render(200,200,emit);realtime=false;
  CHECK(out.count==6);const uint64_t expected[]={0,80,80,160,160,360};
  for(unsigned j=0;j<6;++j)CHECK(out.events[j].sample==expected[j]);
  CHECK(out.events[1].on==false && out.events[2].on && out.events[3].on==false && out.events[4].on);
  CHECK(!r.sources()&&!r.pending()&&!r.failed&&!allocations);
 }
 {
  Runtime r(8000);Output out;auto emit=[&](auto...args){return out(args...);};auto c=settings();r.configure(c);
  CHECK(r.source(edge(true),0,120,emit));r.render(0,200,emit);const auto before=out.count;c[0].enabled=false;r.configure(c);r.begin(200,emit);
  CHECK(!r.pending() && r.sources()==1 && out.count==before);CHECK(r.source(edge(false),201,120,emit));CHECK(out.events[out.count-1].sample==201 && !r.sources());
  CHECK(r.source(edge(true),300,120,emit));CHECK(out.events[out.count-1].velocity==100 && !r.pending());
  CHECK(r.cancel(400,[](const SourceKey&){return true;},emit));CHECK(!r.sources());
 }
 {
  Runtime r(8000);Output out;auto emit=[&](auto...args){return out(args...);};r.configure(settings());
  CHECK(r.source(edge(true),0,120,emit));CHECK(r.source(edge(true,Origin::Phrase,99),0,120,emit));
  CHECK(r.source({SourceAction::StopPhrases,{},0,0},10,120,emit));CHECK(r.sources()==1 && r.pending()==2 && out.count==1);
  CHECK(r.source(edge(false),20,120,emit));r.render(0,256,emit);CHECK(!r.sources()&&!r.pending());
 }
 {
  Runtime r(8000);Output out;auto emit=[&](auto...args){return out(args...);};r.configure(settings());
  CHECK(r.source(edge(true),0,120,emit));out.limit=2;r.render(0,100,emit);
  CHECK(r.failed && r.rejected==1 && out.count==1); // Never half an Off/On retrigger.
  out.limit=8192;CHECK(r.cancel(100,[](const SourceKey&){return true;},emit));CHECK(out.count==2 && !out.events[1].on);
  r.recovered();CHECK(!r.failed&&!r.sources()&&!r.pending());
 }
 {
  Runtime r(8000);Output out;auto emit=[&](auto...args){return out(args...);};auto c=settings();c[0].repeats=32;r.configure(c);
  realtime=true;for(unsigned j=0;j<9;++j)CHECK(r.source(edge(true,Origin::Live,0,60+j),0,120,emit));
  CHECK(r.pending()==256 && r.rejected==1 && out.events[8].velocity==100);
  for(unsigned j=0;j<9;++j)CHECK(r.source(edge(false,Origin::Live,0,60+j),40,120,emit));r.render(0,3000,emit);realtime=false;
  CHECK(!r.failed&&!r.sources()&&!r.pending()&&!allocations);
 }
 {
  Runtime r(8000);Output out;auto emit=[&](auto...args){return out(args...);};auto c=settings();c[0].enabled=false;r.configure(c);
  CHECK(r.source(edge(true),0,120,emit));CHECK(out.count==1);
  CHECK(r.source({SourceAction::ChannelClear,{1,Origin::Live,0,0,0},0,0},10,120,emit));
  CHECK(r.source(edge(false),20,120,emit));CHECK(out.count==1 && !r.sources());
  CHECK(r.source(edge(true),30,120,emit));CHECK(out.count==2 && out.events[1].on);
  CHECK(r.source(edge(false),40,120,emit));CHECK(out.count==3 && !out.events[2].on);
 }
 {
  Runtime r(8000);Output out;auto emit=[&](auto...args){return out(args...);};r.configure(settings());
  CHECK(r.source(edge(true,Origin::Phrase),0,120,emit));
  CHECK(r.source({SourceAction::StopPhrases,{},0,0},10,120,emit));
  CHECK(r.sources()==1 && !r.pending() && out.count==1);
  CHECK(r.source(edge(false,Origin::Live),20,120,emit));CHECK(!r.sources() && out.count==2);
 }
 printf("PASS %u terminal ECHOCITY output / retrigger / recovery checks; no callback allocation\n",checks);
}
