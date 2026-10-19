#include "../headless/native_note_scheduler.hpp"
#include <cstdlib>
#include <iostream>
#include <new>

static bool realtime=false;
static unsigned allocations=0,checks=0;
void *operator new(std::size_t n){if(realtime){++allocations;throw std::bad_alloc();}if(void *p=std::malloc(n?n:1))return p;throw std::bad_alloc();}
void *operator new[](std::size_t n){return ::operator new(n);}
void operator delete(void *p) noexcept{std::free(p);}
void operator delete[](void *p) noexcept{std::free(p);}
void operator delete(void *p,std::size_t) noexcept{std::free(p);}
void operator delete[](void *p,std::size_t) noexcept{std::free(p);}
#define CHECK(expression) do{++checks;if(!(expression)){realtime=false;std::cerr<<"FAIL line "<<__LINE__<<": "<<#expression<<'\n';std::exit(1);}}while(false)
using namespace native_notes;
struct Trace {
 std::array<Event,1024> data{};size_t length=0;
 bool operator()(const Event &e){CHECK(length<data.size());data[length++]=e;return true;}
};
static SourceKey sourceKey(unsigned instrument=1,Origin origin=Origin::Live,uint64_t instance=0){return {instrument,origin,instance,0,60};}
static Pair pair(uint64_t on,uint64_t off,unsigned channel=0,unsigned pitch=60,Origin origin=Origin::Live,uint64_t instance=0,unsigned module=50){
 return {{1,module,71,origin,instance},on,off,uint8_t(channel),uint8_t(pitch),100};
}
static void edgesAndOrdering(){
 Scheduler<8,8> s;Trace trace;auto src=s.sources.begin(sourceKey(),0);Pair p=pair(128,256);
 CHECK(s.admit(src,&p,1,0));CHECK(s.pending()==2);CHECK(s.sources.get(src)->children==1);
 CHECK(s.sources.close(src,64));CHECK(!s.sources.retire(src));
 s.render(0,128,[&](auto e){return trace(e);});CHECK(trace.length==0);
 s.render(128,128,[&](auto e){return trace(e);});CHECK(trace.length==1 && trace.data[0].on && trace.data[0].offset==0);
 s.render(256,128,[&](auto e){return trace(e);});CHECK(trace.length==2 && !trace.data[1].on && trace.data[1].offset==0);
 CHECK(s.pending()==0 && s.active()==0 && s.sources.active()==0);
 src=s.sources.begin(sourceKey(),400);Pair reversed[]={pair(600,660),pair(500,550),pair(525,525)};
 CHECK(s.admit(src,reversed,3,400));trace.length=0;s.render(400,300,[&](auto e){return trace(e);});
 CHECK(trace.length==6);const uint64_t expected[]={500,525,525,550,600,660};
 for(size_t i=0;i<6;++i)CHECK(trace.data[i].sample==expected[i]);
 CHECK(trace.data[1].on && !trace.data[2].on);CHECK(trace.data[1].voice==trace.data[2].voice);
}
static void atomicAdmission(){
 Scheduler<4,4> s;auto src=s.sources.begin(sourceKey(),0);Pair three[]={pair(10,20),pair(11,21),pair(12,22)};
 CHECK(s.admit(src,three,3,0));Pair two[]={pair(30,40),pair(31,41)};
 CHECK(!s.admit(src,two,2,0));CHECK(s.lastRefusal==Refusal::Capacity);CHECK(s.pending()==6 && s.active()==3 && s.sources.get(src)->children==3);
 s.resetAfterPanic();CHECK(!s.admit(src,two,2,0));CHECK(s.lastRefusal==Refusal::InvalidSource);
 src=s.sources.begin(sourceKey(),0);two[1].velocity=0;CHECK(!s.admit(src,two,2,0));CHECK(s.pending()==0 && s.active()==0 && s.sources.get(src)->children==0);
 two[1]=pair(31,30);CHECK(!s.admit(src,two,2,0));two[1]=pair(31,41,16);CHECK(!s.admit(src,two,2,0));
 two[1]=pair(31,41,0,128);CHECK(!s.admit(src,two,2,0));two[1]=pair(31,41);two[1].owner.instrument=2;CHECK(!s.admit(src,two,2,0));
 two[1]=pair(31,41);two[1].owner.origin=Origin::Phrase;CHECK(!s.admit(src,two,2,0));
 two[1]=pair(31,41);two[1].owner.instance=5;CHECK(!s.admit(src,two,2,0));CHECK(!s.admit(src,nullptr,1,0));CHECK(!s.admit(src,two,0,0));
 Pair horizon=pair(1,48000*60+1);CHECK(!s.admit(src,&horizon,1,0));CHECK(s.lastRefusal==Refusal::Horizon);
 Pair past=pair(1,4);CHECK(!s.admit(src,&past,1,2));CHECK(s.pending()==0);
}
static void sourcesAndGenerations(){
 Sources<3> sources;const auto key=sourceKey();auto a=sources.begin(key,10),b=sources.begin(key,11),phrase=sources.begin(sourceKey(1,Origin::Phrase,123),12);
 CHECK(a && b && phrase);CHECK(sources.oldestHeld(key)==a);CHECK(sources.oldestHeld(sourceKey(1,Origin::Phrase,123))==phrase);
 CHECK(sources.close(a,20));CHECK(sources.oldestHeld(key)==b);CHECK(sources.retain(a));CHECK(!sources.retire(a));CHECK(sources.drop(a));CHECK(!sources.get(a));
 auto reused=sources.begin(key,30);CHECK(reused.slot==a.slot && reused.generation!=a.generation);CHECK(!sources.close(a,35));CHECK(!sources.retain(a));CHECK(sources.get(reused)->held);
 sources.resetAfterPanic();auto fresh=sources.begin(key,40);CHECK(fresh.generation>reused.generation);CHECK(!sources.get(reused));
 CHECK(!sources.begin(sourceKey(0),0));auto invalid=key;invalid.pitch=128;CHECK(!sources.begin(invalid,0));
 Token wrong=fresh;wrong.domain=TokenDomain::Voice;CHECK(!sources.get(wrong));CHECK(!(wrong==fresh));
 invalid=key;invalid.origin=static_cast<Origin>(99);CHECK(!sources.begin(invalid,0));
}
static void capturedDownstreamOutputs(){
 Scheduler<4,4> s;Outputs<8> outputs;Trace trace;int transpose=12;unsigned channel=2;bool moduleAlive=true;
 auto src=s.sources.begin(sourceKey(),0);Pair p=pair(10,20);CHECK(s.admit(src,&p,1,0));
 auto emit=[&](const Event &e){CHECK(e.owner.continuation==71);auto physical=[&](bool on,uint8_t ch,uint8_t note,uint8_t velocity){Event out=e;out.on=on;out.channel=ch;out.pitch=note;out.velocity=velocity;return trace(out);};
  return e.on?outputs.attack(e.voice,0,uint8_t(channel),uint8_t(e.pitch+transpose),e.velocity,physical):outputs.release(e.voice,physical);};
 s.render(0,15,emit,[&](const Owner&){return moduleAlive;});CHECK(trace.length==1);CHECK(trace.data[0].channel==2 && trace.data[0].pitch==72);
 transpose=-12;channel=9;moduleAlive=false;s.render(15,10,emit,[&](const Owner&){return moduleAlive;});
 CHECK(trace.length==2 && trace.data[1].channel==2 && trace.data[1].pitch==72 && !trace.data[1].on);CHECK(outputs.active()==0);
 p=pair(30,40);CHECK(s.admit(src,&p,1,25));s.render(25,20,emit,[&](const Owner&){return moduleAlive;});CHECK(trace.length==2 && s.active()==0);
}
static void overlapAndProvenance(){
 Scheduler<8,8> s;Outputs<8> outputs;Trace trace;
 auto live=s.sources.begin(sourceKey(),0),phrase=s.sources.begin(sourceKey(1,Origin::Phrase,42),0);
 Pair a=pair(0,100),b=pair(0,100,0,60,Origin::Phrase,42);CHECK(s.admit(live,&a,1,0));CHECK(s.admit(phrase,&b,1,0));
 auto emit=[&](const Event &e){auto physical=[&](bool on,uint8_t ch,uint8_t note,uint8_t velocity){Event out=e;out.on=on;out.channel=ch;out.pitch=note;out.velocity=velocity;return trace(out);};
  return e.on?outputs.attack(e.voice,0,e.channel,e.pitch,e.velocity,physical):outputs.release(e.voice,physical);};
 s.render(0,1,emit);CHECK(trace.length==1 && outputs.owners(0,60)==2);
 CHECK(s.cancel(1,[](const Owner&o){return o.origin==Origin::Phrase;},emit));CHECK(trace.length==1 && outputs.owners(0,60)==1 && s.active()==1);
 CHECK(s.cancel(2,[](const Owner&o){return o.origin==Origin::Live;},emit));CHECK(trace.length==2 && !trace.data[1].on && outputs.active()==0 && s.pending()==0);
 s.render(3,200,emit);CHECK(trace.length==2);
}
static void failuresAndRetries(){
 Scheduler<4,4> s;Trace trace;auto src=s.sources.begin(sourceKey(),0);Pair p=pair(0,10);
 CHECK(s.admit(src,&p,1,0));s.render(0,20,[](const Event&){return false;});CHECK(s.failedAttacks==1 && s.active()==0 && s.pending()==0);
 CHECK(s.admit(src,&p,1,0));bool failOff=true;
 auto emit=[&](const Event&e){if(!e.on && failOff)return false;return trace(e);};
 s.render(0,20,emit);CHECK(trace.length==1 && s.failedReleases==1 && s.needsRecovery && s.active()==1 && s.pending()==1);
 s.render(20,20,emit);CHECK(trace.length==1 && s.failedReleases==2 && s.pending()==1);
 failOff=false;s.render(40,20,emit);CHECK(trace.length==2 && !trace.data[1].on && trace.data[1].sample==40 && s.active()==0);
 s.resetAfterPanic();CHECK(!s.needsRecovery && s.sources.active()==0);
 src=s.sources.begin(sourceKey(),100);p=pair(100,200);CHECK(s.admit(src,&p,1,100));s.render(100,10,emit);failOff=true;
 CHECK(!s.cancel(110,[](const Owner&){return true;},emit));CHECK(s.active()==1 && s.pending()==1);
 failOff=false;s.render(110,10,emit);CHECK(s.active()==0 && s.pending()==0 && !trace.data[trace.length-1].on);
}
static void sourceScopeCleanup(){
 Scheduler<8,8> s;Trace trace;
 auto first=s.sources.begin(sourceKey(),0);auto untouched=s.sources.begin(sourceKey(2),0);auto heldOnly=s.sources.begin(sourceKey(),1);CHECK(heldOnly);
 Pair a=pair(10,20),b=pair(10,20);b.owner.instrument=2;CHECK(s.admit(first,&a,1,0));CHECK(s.admit(untouched,&b,1,0));
 auto emit=[&](const Event&e){return trace(e);};
 CHECK(s.cancelSources(5,[](const SourceKey &key){return key.instrument==1;},emit));
 CHECK(s.sources.active()==1 && s.active()==1 && !s.sources.get(first) && !s.sources.get(heldOnly));
 CHECK(!s.admit(first,&a,1,5));s.render(5,10,emit);CHECK(trace.length==1 && trace.data[0].owner.instrument==2);
 CHECK(s.cancelSources(15,[](const SourceKey&){return true;},emit));CHECK(s.sources.active()==0 && s.active()==0 && s.pending()==0 && trace.length==2);
}
static void atomicFanoutAndPartialRelease(){
 Outputs<2> outputs;using Routed=Outputs<2>::Routed;Token voice{0,10};unsigned physical=0;
 Routed tooMany[]={{1,0,60,100},{2,1,61,100},{3,2,62,100}};
 auto batch=[&](const Routed*,size_t count){physical+=unsigned(count);return true;};
 CHECK(!outputs.attackBatch(voice,tooMany,3,batch));CHECK(!physical && !outputs.active());
 CHECK(!outputs.attackBatch(voice,tooMany,2,[](const Routed*,size_t){return false;}));CHECK(outputs.active()==0);
 Routed shared[]={{1,0,60,100},{2,0,60,90}};CHECK(outputs.attackBatch(voice,shared,2,batch));CHECK(physical==1 && outputs.owners(0,60)==2);
 CHECK(outputs.release(voice,[&](bool on,uint8_t,uint8_t,uint8_t){CHECK(!on);++physical;return true;}));CHECK(physical==2 && outputs.active()==0);
 physical=0;CHECK(outputs.attackBatch(voice,tooMany,2,batch));bool failSecond=true;
 auto release=[&](bool on,uint8_t ch,uint8_t,uint8_t){CHECK(!on);if(ch==1 && failSecond)return false;++physical;return true;};
 CHECK(!outputs.release(voice,release));CHECK(outputs.active()==1 && outputs.owners(0,60)==0 && outputs.owners(1,61)==1);
 failSecond=false;CHECK(outputs.release(voice,release));CHECK(outputs.active()==0 && physical==4);
 Token reused{0,11};CHECK(outputs.attack(reused,0,2,72,100,[](bool,uint8_t,uint8_t,uint8_t){return true;}));
 CHECK(outputs.release(voice,release));CHECK(outputs.owners(2,72)==1);outputs.resetAfterPanic();CHECK(outputs.active()==0 && outputs.owners(2,72)==0);
}
static void noAllocationStress(){
 Scheduler<64,64> s;Outputs<64> outputs;uint64_t onCount=0,offCount=0;
 auto emit=[&](const Event&e){auto physical=[&](bool on,uint8_t,uint8_t,uint8_t){if(on)++onCount;else ++offCount;return true;};
  return e.on?outputs.attack(e.voice,0,e.channel,e.pitch,e.velocity,physical):outputs.release(e.voice,physical);};
 realtime=true;
 for(unsigned i=0;i<2000;++i){uint64_t now=uint64_t(i)*64;auto src=s.sources.begin(sourceKey(),now);CHECK(src);
  Pair notes[]={pair(now+5,now+8,0,60),pair(now+10,now+13,1,64),pair(now+15,now+18,2,67)};
  CHECK(s.admit(src,notes,3,now));CHECK(s.sources.close(src,now+1));s.render(now,64,emit);
  CHECK(s.active()==0 && s.pending()==0 && s.sources.active()==0 && outputs.active()==0);
 }
 realtime=false;CHECK(allocations==0 && onCount==6000 && offCount==6000);
 Scheduler<> full;Outputs<> fullOutputs;auto src=full.sources.begin(sourceKey(),0);std::array<Pair,256> notes{};uint64_t attacks=0,releases=0;
 for(unsigned i=0;i<256;++i)notes[i]=pair(0,32,i/128,i%128);
 realtime=true;CHECK(full.admit(src,notes.data(),notes.size(),0));CHECK(full.pending()==512);
 full.render(0,64,[&](const Event&e){auto physical=[&](bool on,uint8_t,uint8_t,uint8_t){if(on)++attacks;else ++releases;return true;};return e.on?fullOutputs.attack(e.voice,0,e.channel,e.pitch,e.velocity,physical):fullOutputs.release(e.voice,physical);});
 realtime=false;CHECK(attacks==256 && releases==256 && full.active()==0 && fullOutputs.active()==0 && allocations==0);
}
int main(){edgesAndOrdering();atomicAdmission();sourcesAndGenerations();capturedDownstreamOutputs();overlapAndProvenance();failuresAndRetries();sourceScopeCleanup();atomicFanoutAndPartialRelease();noAllocationStress();std::cout<<"PASS native delayed-note foundation: "<<checks<<" checks; no callback allocation\n";}
