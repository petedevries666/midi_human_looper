#include "../headless/native_expressive_live.hpp"
#include <cassert>
#include <vector>
#include <iostream>
struct Midi {uint64_t sample;bool on;unsigned channel,pitch,velocity;};
int main(){
  using namespace expressive;
  Humanizer h;h.enabled=true;h.timingMs=0;h.biasMs=1500;
  VelocityCurve curve;
  native_notes::SourceKey key{1,native_notes::Origin::Live,0,0,60};
  Identity id;id.instrument=1;id.note=1;
  LiveRuntime<> live(48000);
  std::vector<Midi> events;
  auto emit=[&](uint64_t t,bool on,uint8_t ch,uint8_t p,uint8_t v){
    events.push_back({t,on,ch,p,v});return true;
  };
  // Release arrives before delayed attack. The pair must remain valid.
  assert(live.noteOn(key,9,1000,100,id,h,curve));
  assert(live.noteOff(key,3400));
  for(uint64_t s=0;s<80000;s+=256)live.render(s,256,emit);
  assert(events.size()==2);
  assert(events[0].on && events[0].sample==73000);
  assert(!events[1].on && events[1].sample==75400);
  assert(live.active()==0 && live.sounding()==0 && live.heldSources()==0);
  events.clear();
  // Overlapping identical pitches must have FIFO pairing and last-off lease.
  h.biasMs=0;
  assert(live.noteOn(key,9,100000,90,id,h,curve));
  assert(live.noteOn(key,9,100200,70,id,h,curve));
  assert(live.noteOff(key,100500));
  assert(live.noteOff(key,100700));
  for(uint64_t s=99840;s<101000;s+=128)live.render(s,128,emit);
  assert(events.size()==2);
  assert(events[0].on && events[0].sample==100000);
  assert(!events[1].on && events[1].sample==100700);
  assert(live.active()==0 && live.sounding()==0);
  events.clear();
  // Negative shift cannot be emitted in the past on live input.
  h.biasMs=-2000;
  assert(live.noteOn(key,9,120000,80,id,h,curve));
  assert(live.clamped==1);
  assert(live.noteOff(key,120400));
  live.render(120000,512,emit);
  assert(events.size()==2 && events[0].sample==120000 && events[1].sample==120400);
  assert(!live.noteOff(key,120500) && live.unmatched==1);
  events.clear();
  // Cancel a sounding note and ensure no later release duplicates.
  h.biasMs=0;
  assert(live.noteOn(key,9,130000,80,id,h,curve));
  live.render(130000,128,emit);
  assert(events.size()==1);
  assert(live.cancel(130100,1,9,emit));
  assert(events.size()==2 && !events.back().on);
  assert(live.noteOff(key,130500)); // Retire held source even if voice cancelled.
  live.render(130128,1024,emit);
  assert(events.size()==2);
  // Failed downstream attack must not leave a phantom release.
  events.clear();
  assert(live.noteOn(key,9,140000,80,id,h,curve));
  assert(live.noteOff(key,140300));
  auto reject=[](uint64_t,bool,uint8_t,uint8_t,uint8_t){return false;};
  live.render(140000,512,reject);
  assert(live.active()==0 && live.sounding()==0);
  std::cout<<"native expressive live bridge PASS\n";
}
