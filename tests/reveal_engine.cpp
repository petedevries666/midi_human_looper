#include "../headless/reveal_engine.hpp"
#include "../headless/movement_engine.hpp"
#include <cassert>
#include <vector>
#include <iostream>
struct Event {uint64_t sample;unsigned channel,value;};
int main(){
 controller::Host host;reveal::Runtime r(host);std::vector<Event> out;
 auto emit=[&](uint64_t t,unsigned ch,unsigned cc,unsigned value){assert(cc==7);out.push_back({t,ch,value});return true;};
 assert(r.reserve(2));assert(r.start(0,1,2,10,emit));assert(out.back().value==0);
 r.mask(0,1,false,20,emit);assert(out.back().value==127);
 r.mask(0,1,true,30,emit);assert(out.back().value==0);
 auto size=out.size();r.mask(0,9,false,35,emit);assert(size==out.size());
 assert(r.start(1,2,2,40,emit));r.close(0,1,50,emit);assert(out.back().value==0);
 r.mask(1,2,false,60,emit);assert(out.back().value==127);
 r.physical(1,7,77,70);size=out.size();r.mask(1,2,true,80,emit);r.close(1,2,80,emit);assert(size==out.size());
 assert(r.start(0,3,2,90,emit));r.mask(0,3,false,100,emit);assert(out.back().value==77);
 r.panic();r.flush(101,emit);assert(out.back().value==77);
 // Losing MOVEMENT cleanup must not retire the target now leased by REVEAL.
 movement::Runtime movements(host,48000);movement::Prepared p;movement::Definition d;d.number=7;d.channel=1;d.soft=false;d.curve({{0,.8,0},{1,.4,0}});p.definitions={d};movements.install(std::move(p));
 auto resolve=[](const controller::Binding&,uint32_t&,double&){return false;};auto apply=[](const controller::Binding&,double){return true;};
 assert(movements.start(0,200,resolve));movements.render(201,emit,apply);
 assert(r.start(0,4,2,202,emit));auto token=host.target(reveal::target(1))->token;
 movements.render(300,emit,apply);assert(!movements.active);
 assert(host.target(reveal::target(1))&&host.target(reveal::target(1))->token==token);
 r.mask(0,4,false,301,emit);assert(out.back().value==102);
 // New MOVEMENT takes the same namespace; old REVEAL cannot later restore.
 assert(movements.start(0,400,resolve));size=out.size();r.close(0,4,401,emit);assert(out.size()==size);
 movements.render(402,emit,apply);assert(movements.active==1);
 // Physical event at PRESS timestamp wins even if processed before START.
 r.physical(2,7,81,500);assert(r.start(0,5,4,500,emit));size=out.size();r.mask(0,5,false,501,emit);assert(out.size()==size);
 r.close(0,5,502,emit);r.collectIdle();assert(!host.target(reveal::target(2)));
 {
  controller::Host full;for(unsigned i=0;i<controller::Engine::TargetCapacity;++i)assert(full.stagePerformanceTarget(i+1,.5));
  reveal::Runtime bounded(full);assert(!bounded.reserve(65535));assert(full.freeTargets()==0);assert(!full.target(reveal::target(0)));
 }
 {
  controller::Host allHost;reveal::Runtime all(allHost);unsigned events=0;
  auto count=[&](uint64_t,unsigned ch,unsigned cc,unsigned value){assert(ch<16&&cc==7&&value<=127);++events;return true;};
  assert(all.start(0,9007199254740989ULL,65535,1000,count));assert(events==16);
  all.mask(0,9007199254740989ULL,false,1010,count);assert(events==32);
  all.mask(0,9007199254740988ULL,true,1011,count);assert(events==32);
  all.close(0,9007199254740989ULL,1020,count);assert(events==48);all.collectIdle();assert(allHost.freeTargets()==controller::Engine::TargetCapacity);
 }
 std::cout<<"PASS production REVEAL Controller-token ownership, default/observed volume, GATE, replacement, physical takeover and MOVEMENT stale-retirement regression\n";
}
