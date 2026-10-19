#include "../headless/echocity_source_journal.hpp"
#include <cstdlib>
#include <iostream>
#include <new>
static bool realtime=false;static unsigned allocations=0,checks=0;
void *operator new(std::size_t n){if(realtime){++allocations;throw std::bad_alloc();}if(void *p=std::malloc(n?n:1))return p;throw std::bad_alloc();}
void *operator new[](std::size_t n){return ::operator new(n);}
void operator delete(void *p)noexcept{std::free(p);}void operator delete[](void *p)noexcept{std::free(p);}
void operator delete(void *p,std::size_t)noexcept{std::free(p);}void operator delete[](void *p,std::size_t)noexcept{std::free(p);}
#define CHECK(e) do{++checks;if(!(e)){realtime=false;std::cerr<<"FAIL line "<<__LINE__<<": "<<#e<<'\n';std::exit(1);}}while(false)
using namespace native_notes;
static echocity::Configuration config(){echocity::Configuration c;c.id=23;c.instrument=1;c.continuation=91;c.interval=10;c.repeats=3;return c;}
static SourceKey key(uint64_t instance=0,Origin origin=Origin::Live){return {1,origin,instance,0,60};}
struct Trace {std::array<Event,128> events{};size_t count=0;bool operator()(const Event&e){CHECK(count<events.size());events[count++]=e;return true;}};
static void coreAndCapturedSettings(){
 Scheduler<16,16> s(8000);echocity::Unit unit(8000);auto c=config();c.pitchStep=12;c.pingPong=true;c.otherChannel=3;c.decay=.5;c.gate=.5;c.gateDecay=.5;
 CHECK(unit.configure(c));auto source=s.sources.begin(key(),0);auto result=unit.trigger(s,source,0,60,100,0);
 CHECK(result.ok && result.dryVelocity==50 && result.admitted==3 && s.pending()==6);
 c.pitchStep=-12;c.otherChannel=9;c.gate=4;CHECK(unit.configure(c));
 CHECK(s.sealSource(source,40,40));Trace trace;s.render(0,264,[&](auto e){return trace(e);});
 CHECK(trace.count==6);const uint64_t samples[]={80,100,160,170,240,245};const unsigned pitches[]={72,72,84,84,96,96};
 for(unsigned i=0;i<6;++i){CHECK(trace.events[i].sample==samples[i]);CHECK(trace.events[i].pitch==pitches[i]);CHECK(trace.events[i].owner.module==23 && trace.events[i].owner.continuation==91);}
 CHECK(trace.events[0].channel==3 && trace.events[2].channel==0 && trace.events[4].channel==3);
 CHECK(trace.events[0].velocity==50 && trace.events[2].velocity==25 && trace.events[4].velocity==13);CHECK(s.sources.active()==0);
}
static void knownDurationAndTempo(){
 Scheduler<16,16> s(8000);echocity::Unit unit(8000);auto c=config();c.unit=echocity::TimeUnit::Beats;c.interval=.5;c.firstOffset=.5;c.repeats=2;c.wet=1;c.decay=1;
 CHECK(unit.configure(c));auto source=s.sources.begin(key(),0);CHECK(s.sources.close(source,100));
 CHECK(!unit.trigger(s,source,0,60,100,100).ok);CHECK(s.pending()==0);
 auto result=unit.trigger(s,source,0,60,100,100,120);CHECK(result.ok && result.admitted==2 && result.dryVelocity==0);
 Trace trace;s.render(0,8000,[&](auto e){return trace(e);});CHECK(trace.count==4);
 CHECK(trace.events[0].sample==1000 && trace.events[1].sample==1100 && trace.events[2].sample==3000 && trace.events[3].sample==3100);
 source=s.sources.begin(key(),10000);CHECK(s.sources.close(source,10100));CHECK(unit.trigger(s,source,0,60,100,10100,60).ok);
 trace.count=0;s.render(10000,10000,[&](auto e){return trace(e);});CHECK(trace.events[0].sample==12000 && trace.events[2].sample==16000);
}
static void bypassMixAndBounds(){
 Scheduler<64,16> s(8000);echocity::Unit unit(8000);auto c=config();auto source=s.sources.begin(key(),0);
 c.wet=0;CHECK(unit.configure(c));auto result=unit.trigger(s,source,0,60,127,0);CHECK(result.ok && result.dryVelocity==127 && !s.pending());
 c.wet=1;c.enabled=false;CHECK(unit.configure(c));result=unit.trigger(s,source,0,60,127,0);CHECK(result.ok && result.dryVelocity==127 && !s.pending());
 c.enabled=true;c.repeats=32;c.decay=1;CHECK(unit.configure(c));result=unit.trigger(s,source,0,60,127,0);CHECK(result.ok && result.admitted==32);
 CHECK(s.sealSource(source,10,10));Trace trace;s.render(0,3000,[&](auto e){return trace(e);});CHECK(trace.count==64 && !s.active());
 source=s.sources.begin(key(),10000);c.pitchStep=48;CHECK(unit.configure(c));result=unit.trigger(s,source,0,100,127,10000);CHECK(result.ok && !result.planned && !s.pending());
 c.pitchStep=0;c.decay=0;CHECK(unit.configure(c));result=unit.trigger(s,source,0,60,127,10000);CHECK(result.ok && result.admitted==1);
 s.resetAfterPanic();source=s.sources.begin(key(),0);c.gate=0;c.repeats=1;CHECK(unit.configure(c));CHECK(unit.trigger(s,source,0,60,127,0).ok);
 trace.count=0;s.render(0,100,[&](auto e){return trace(e);});CHECK(trace.count==2 && trace.events[0].sample==trace.events[1].sample);
 CHECK(trace.events[0].on && !trace.events[1].on);
}
static void lateGateAndWatchdog(){
 Scheduler<4,4> s(8000);echocity::Unit unit(8000);auto c=config();c.interval=1;c.repeats=1;c.gate=.1;CHECK(unit.configure(c));auto source=s.sources.begin(key(),0);
 CHECK(unit.trigger(s,source,0,60,100,0).ok);Trace trace;s.render(0,20,[&](auto e){return trace(e);});CHECK(trace.count==1 && s.active()==1);
 CHECK(!s.sealSource(source,1000,999));CHECK(s.sealSource(source,1000,1000));CHECK(s.lateGateReleases==1);
 s.render(1000,16,[&](auto e){return trace(e);});CHECK(trace.count==2 && trace.events[1].sample==1000 && !s.active() && !s.sources.active());
 source=s.sources.begin(key(),2000);CHECK(unit.trigger(s,source,0,60,100,2000).ok);trace.count=0;s.render(2000,64,[&](auto e){return trace(e);});
 CHECK(trace.count==1);s.render(482000,64,[&](auto e){return trace(e);});CHECK(trace.count==2 && !s.active());
 CHECK(s.sources.get(source)->held);CHECK(s.sealSource(source,482100,482100));CHECK(!s.sources.active());
}
static void refusalAndConfiguration(){
 Scheduler<4,8> s(8000);echocity::Unit unit(8000);auto c=config();CHECK(unit.configure(c));auto bad=c;bad.interval=std::numeric_limits<double>::quiet_NaN();CHECK(!unit.configure(bad));
 bad=c;bad.gate=std::numeric_limits<double>::infinity();CHECK(!unit.configure(bad));bad=c;bad.repeats=33;CHECK(!unit.configure(bad));bad=c;bad.otherChannel=16;CHECK(!unit.configure(bad));
 CHECK(unit.configuration().id==c.id && unit.configuration().interval==c.interval);
 bad=c;bad.id=16777216;CHECK(!unit.configure(bad));
 bad=c;bad.firstOffset=std::numeric_limits<double>::quiet_NaN();CHECK(!unit.configure(bad));
 bad=c;bad.gateDecay=std::numeric_limits<double>::quiet_NaN();CHECK(!unit.configure(bad));
 Scheduler<4,8> wrongRate(48000);auto wrongSource=wrongRate.sources.begin(key(),0);CHECK(!unit.trigger(wrongRate,wrongSource,0,60,100,0).ok);
 auto source=s.sources.begin(key(),0);Pair other{{1,99,0,Origin::Live,0},0,50,0,60,100};CHECK(s.admit(source,&other,1,0));
 c.repeats=4;c.wet=1;CHECK(unit.configure(c));auto result=unit.trigger(s,source,0,60,100,0);CHECK(!result.ok && result.dryVelocity==100 && !result.admitted && s.active()==1 && s.pending()==2);
 s.resetAfterPanic();source=s.sources.begin(key(),0);c.interval=60000;c.repeats=2;CHECK(unit.configure(c));result=unit.trigger(s,source,0,60,100,0);
 CHECK(!result.ok && result.dryVelocity==100 && s.pending()==0 && s.sources.get(source)->children==0);
 CHECK(!unit.trigger(s,{},0,60,100,0).ok);CHECK(!unit.trigger(s,source,16,60,100,0).ok);
 echocity::Unit invalidRate(0);CHECK(!invalidRate.configure(config()));
}
static void scopesCancellationAndAllocation(){
 Scheduler<64,64> s(8000);Outputs<128> outputs;echocity::Unit first(8000),second(8000);auto c=config();c.wet=1;c.decay=1;c.repeats=4;CHECK(first.configure(c));c.id=24;CHECK(second.configure(c));
 auto source=s.sources.begin(key(42,Origin::Phrase),0);CHECK(first.trigger(s,source,0,60,100,0).ok);CHECK(second.trigger(s,source,0,60,100,0).ok);
 CHECK(s.cancel(0,[](const Owner&o){return o.module==23;},[](const Event&){return true;}));CHECK(s.active()==4);
 CHECK(s.sealSource(source,10,10));uint64_t ons=0,offs=0;
 auto emit=[&](const Event&e){CHECK(e.owner.module==24 && e.owner.origin==Origin::Phrase && e.owner.instance==42);auto physical=[&](bool on,uint8_t,uint8_t,uint8_t){if(on)++ons;else ++offs;return true;};
  return e.on?outputs.attack(e.voice,0,e.channel,e.pitch,e.velocity,physical):outputs.release(e.voice,physical);};
 realtime=true;s.render(0,1000,emit);realtime=false;CHECK(ons==4 && offs==4 && s.sources.active()==0 && outputs.active()==0 && allocations==0);
 realtime=true;
 for(unsigned i=0;i<1000;++i){uint64_t now=uint64_t(i+1)*1000;source=s.sources.begin(key(42,Origin::Phrase),now);CHECK(source);CHECK(second.trigger(s,source,0,60,100,now).ok);CHECK(s.sealSource(source,now+10,now+10));s.render(now,1000,emit);CHECK(!s.active() && !s.sources.active());}
 realtime=false;CHECK(allocations==0 && ons==4004 && offs==4004);
}
static void sourceBridgeRealtime(){
 echocity::SourceBridge<16,16> bridge(8000);echocity::SourceJournal<4> journal;Trace trace;
 echocity::Unit unit(8000);auto c=config();c.repeats=1;CHECK(unit.configure(c));
 auto attack=[&](Token token,const echocity::SourceEvent &e,uint64_t now){CHECK(unit.trigger(bridge.scheduler,token,e.key.channel,e.key.pitch,e.velocity,now).ok);};
 auto emit=[&](const Event&e){return trace(e);};
 // Rows are intentionally in generation order, not timestamp order. Last row
 // is natural completion: finish its gates while allowing the delayed tail.
 std::array<double,24> cells{{2,1,42,60*16,1,20, 1,1,42,60*16+100*2048,1,0, 7,0,42,0,1,30, 0,0,0,0,0,0}};
 unsigned visited=0;realtime=true;
 CHECK(journal.consume(0,3,0,128,[&](size_t i){return cells[i];},[&](const echocity::SourceEvent&e){++visited;CHECK(bridge.apply(e,e.offset,attack,emit));}));
 bridge.scheduler.render(0,128,emit);realtime=false;
 CHECK(visited==3 && trace.count==2 && trace.events[0].sample==80 && trace.events[1].sample==100);
 CHECK(!bridge.scheduler.sources.active() && !bridge.scheduler.active() && !allocations);
 // Validation is all-or-nothing, including a corrupt release after a valid On.
 visited=0;cells[0]=std::numeric_limits<double>::quiet_NaN();
 realtime=true;CHECK(!journal.consume(0,3,0,128,[&](size_t i){return cells[i];},[&](const echocity::SourceEvent&){++visited;}));realtime=false;
 CHECK(!visited && journal.needsRecovery && !allocations);
 CHECK(!journal.consume(0,5,0,128,[&](size_t i){return cells[i];},[&](const echocity::SourceEvent&){++visited;}));
 CHECK(!journal.consume(0,0,1,128,[&](size_t i){return cells[i];},[&](const echocity::SourceEvent&){++visited;}));
 // Stable order at equal sample, and read cursors wrapping the fixed ring.
 echocity::SourceJournal<4> wrapped;cells[0]=2;unsigned order=0;
 CHECK(wrapped.consume(4,7,0,128,[&](size_t i){return cells[i];},[&](const echocity::SourceEvent&e){const unsigned expected[]={1,2,7};CHECK(unsigned(e.action)==expected[order++]);}));
 CHECK(order==3);
 cells[5]=cells[11]=cells[17]=0;order=0;
 CHECK(wrapped.consume(0,3,0,128,[&](size_t i){return cells[i];},[&](const echocity::SourceEvent&e){const unsigned expected[]={2,1,7};CHECK(unsigned(e.action)==expected[order++]);}));
 CHECK(order==3);
}
int main(){coreAndCapturedSettings();knownDurationAndTempo();bypassMixAndBounds();lateGateAndWatchdog();refusalAndConfiguration();scopesCancellationAndAllocation();sourceBridgeRealtime();std::cout<<"PASS ECHOCITY native core: "<<checks<<" checks; no callback allocation\n";}
