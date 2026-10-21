#include "../headless/native_expressive_transformers.hpp"
#include <cassert>
#include <vector>
#include <iostream>
using namespace expressive;
struct Midi {uint64_t t;bool on;unsigned ch,pitch,vel;};
int main(){
  VelocityCurve c;
  assert(c.valid() && c.apply(0)==0);
  for(unsigned v=1;v<=127;++v)assert(c.apply(v)==v);
  c.points[0]={1,127};c.points[1]={127,1};
  assert(c.valid() && c.apply(1)==127 && c.apply(127)==1 && c.apply(64)==64);
  c.amount=0;assert(c.apply(1)==1);
  c.amount=50;assert(c.apply(1)==64);
  auto bad=c;bad.points[1].x=1;assert(!bad.valid());
  Humanizer h;h.enabled=true;h.timingMs=2000;h.biasMs=2000;
  Identity id;id.instrument=1;id.group=7;id.note=1;
  const auto first=delay(h,id,48000);assert(first>=0 && first<=192000);
  auto other=id;other.note=2;
  assert(delay(h,id,48000)==delay(h,other,48000)); // GROUP
  h.scope=Scope::Notes;
  assert(delay(h,id,48000)!=delay(h,other,48000));
  h.timingMs=0;h.biasMs=1700;
  VelocityCurve straight;
  native_notes::SourceKey key;
  key.instrument=1;key.origin=native_notes::Origin::Phrase;
  key.instance=123;key.channel=1;key.pitch=60;
  PairRuntime<> engine(48000);
  std::vector<Midi> got;
  auto receive=[&](uint64_t s,bool on,uint8_t ch,uint8_t p,uint8_t v){
    got.push_back({s,on,ch,p,v});return true;
  };
  assert(engine.schedule(key,44,10000,15000,0,100,id,h,straight));
  for(unsigned i=0;i<200;++i)engine.render(uint64_t(i)*512,512,receive);
  assert(got.size()==2);
  assert(got[0].on && got[0].t==91600 && got[0].vel==100);
  assert(!got[1].on && got[1].t==96600);
  assert(engine.active()==0 && engine.sounding()==0);
  got.clear();h.biasMs=-2000;
  assert(engine.schedule(key,44,70000,71000,60000,70,id,h,straight));
  assert(engine.clamped==1);
  engine.render(60000,2048,receive);
  assert(got.size()==2 && got[0].t==60000 && got[1].t==61000);
  got.clear();h.biasMs=0;
  assert(engine.schedule(key,44,100000,104000,95000,60,id,h,straight));
  assert(engine.schedule(key,44,101000,105000,95000,80,id,h,straight));
  for(unsigned i=0;i<25;++i)engine.render(95000+uint64_t(i)*512,512,receive);
  assert(got.size()==2 && got[0].on && !got[1].on && got[1].t==105000);
  assert(!engine.schedule(key,44,120000,121000,120000,0,id,h,straight));
  got.clear();
  assert(engine.schedule(key,44,130000,140000,125000,90,id,h,straight));
  engine.render(130000,512,receive);assert(got.size()==1);
  assert(engine.cancel(130100,1,44,receive));
  assert(got.size()==2 && !got.back().on);
  engine.render(139000,2000,receive);assert(got.size()==2);
  PairRuntime<2,3> bounded(48000);
  assert(bounded.schedule(key,44,500,600,0,80,id,h,straight));
  assert(bounded.schedule(key,44,700,800,0,80,id,h,straight));
  assert(!bounded.schedule(key,44,900,1000,0,80,id,h,straight));
  assert(bounded.rejected==1);
  std::cout << "native expressive pair test PASS\n";
}
