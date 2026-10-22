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
  c.amount=100;assert(c.apply(1)==127);
  c.amount=50;assert(c.apply(1)==64);
  assert(c.apply(127)==64);
  auto bad=c;bad.points[1].x=1;assert(!bad.valid());
  Humanizer h;h.enabled=true;h.timingMs=2000;h.biasMs=2000;
  Identity id;id.instrument=1;id.group=7;id.note=1;
  const auto first=delay(h,id,48000);assert(first>=0 && first<=192000);
  auto other=id;other.note=2;
  assert(delay(h,id,48000)==delay(h,other,48000)); // GROUP
  h.scope=Scope::Notes;
  assert(delay(h,id,48000)!=delay(h,other,48000));
  // FIXED is reproducible across repeated calls and ignores iteration;
  // EVOLVING changes the deterministic stream per phrase iteration.
  Humanizer reproducible=h;
  reproducible.timingMs=500;
  reproducible.biasMs=0;
  reproducible.variation=Variation::Fixed;
  auto later=id;later.iteration=99;
  assert(delay(reproducible,id,48000)==delay(reproducible,id,48000));
  assert(delay(reproducible,id,48000)==delay(reproducible,later,48000));
  reproducible.variation=Variation::Evolving;
  bool iterationChanged=false;
  for(uint32_t iteration=1;iteration<64;++iteration){
    later.iteration=iteration;
    iterationChanged|=delay(reproducible,id,48000)!=delay(reproducible,later,48000);
  }
  assert(iterationChanged);
  // The same independent variation rules apply to velocity.
  reproducible.velocityPercent=100;
  reproducible.variation=Variation::Fixed;
  assert(velocity(reproducible,id,64)==velocity(reproducible,later,64));
  reproducible.variation=Variation::Evolving;
  bool velocityChanged=false;
  for(uint32_t iteration=1;iteration<64;++iteration){
    later.iteration=iteration;
    velocityChanged|=velocity(reproducible,id,64)!=velocity(reproducible,later,64);
  }
  assert(velocityChanged);
  auto invalidHumanizer=h;invalidHumanizer.biasMs=2001;
  assert(!invalidHumanizer.valid() && delay(invalidHumanizer,id,48000)==0);
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
  // Module-scoped cancellation releases only the matching captured voice.
  PairRuntime<> scoped(48000);
  std::vector<Midi> scopedMidi;
  auto scopedReceive=[&](uint64_t s,bool on,uint8_t ch,uint8_t p,uint8_t v){
    scopedMidi.push_back({s,on,ch,p,v});return true;
  };
  native_notes::SourceKey secondKey=key;
  secondKey.instrument=2;secondKey.instance=456;secondKey.pitch=61;
  h.enabled=false;
  assert(scoped.schedule(key,44,1000,5000,0,90,id,h,straight));
  assert(scoped.schedule(secondKey,45,1100,6000,0,80,id,h,straight));
  scoped.render(1000,512,scopedReceive);
  assert(scopedMidi.size()==2 && scopedMidi[0].on && scopedMidi[1].on);
  assert(scoped.cancel(2000,1,44,scopedReceive));
  assert(scopedMidi.size()==3 && !scopedMidi.back().on);
  assert(scopedMidi.back().pitch==60);
  scoped.render(5000,1024,scopedReceive);
  assert(scopedMidi.size()==4 && !scopedMidi.back().on && scopedMidi.back().pitch==61);
  assert(scoped.active()==0 && scoped.sounding()==0);
  // Streaming live adapter accepts On before Off, applies one captured
  // lookahead+bias shift to both events, and preserves release velocity.
  StreamRuntime<4> stream(48000);
  Humanizer live;live.enabled=true;live.biasMs=25;live.liveLookaheadMs=10;
  std::vector<Midi> streamMidi;
  auto streamReceive=[&](uint64_t s,bool on,uint8_t ch,uint8_t p,uint8_t v){
    streamMidi.push_back({s,on,ch,p,v});return true;
  };
  assert(stream.attack(key,44,1000,100,id,live,straight,streamReceive));
  assert(stream.release(key,2000,37,streamReceive));
  assert(streamMidi.empty() && stream.pending()==2);
  stream.render(1000,512,streamReceive);assert(streamMidi.empty());
  stream.render(2680,512,streamReceive);
  assert(streamMidi.size()==1 && streamMidi[0].on && streamMidi[0].t==2680 && streamMidi[0].vel==100);
  stream.render(3680,512,streamReceive);
  assert(streamMidi.size()==2 && !streamMidi[1].on && streamMidi[1].t==3680 && streamMidi[1].vel==37);
  assert(stream.active()==0 && stream.sounding()==0);
  // Overlapping identical pitches retain ownership until the final release.
  StreamRuntime<4> overlap(48000);live.enabled=false;streamMidi.clear();
  assert(overlap.attack(key,44,100,90,id,live,straight,streamReceive));
  assert(overlap.attack(key,44,150,80,id,live,straight,streamReceive));
  overlap.render(100,128,streamReceive);
  assert(overlap.release(key,200,11,streamReceive));
  assert(overlap.release(key,250,22,streamReceive));
  overlap.render(200,512,streamReceive);
  assert(streamMidi.size()==2 && streamMidi[0].on && !streamMidi[1].on && streamMidi[1].vel==22);
  // Instrument+module cancellation releases only the selected sounding voice.
  StreamRuntime<4> scopedStream(48000);streamMidi.clear();
  native_notes::SourceKey otherInstrument=key;otherInstrument.instrument=2;otherInstrument.pitch=61;
  assert(scopedStream.attack(key,44,1000,90,id,live,straight,streamReceive));
  assert(scopedStream.attack(otherInstrument,45,1000,80,id,live,straight,streamReceive));
  scopedStream.render(1000,512,streamReceive);assert(streamMidi.size()==2);
  assert(scopedStream.cancel(1600,1,44,streamReceive));
  scopedStream.render(1600,1,streamReceive);
  assert(streamMidi.size()==3 && !streamMidi.back().on && streamMidi.back().pitch==60);
  assert(scopedStream.active()==1 && scopedStream.sounding()==1);
  scopedStream.recovered();assert(scopedStream.active()==0 && scopedStream.pending()==0);
  PairRuntime<2,3> bounded(48000);
  assert(bounded.schedule(key,44,500,600,0,80,id,h,straight));
  assert(bounded.schedule(key,44,700,800,0,80,id,h,straight));
  assert(!bounded.schedule(key,44,900,1000,0,80,id,h,straight));
  assert(bounded.rejected==1);
  std::cout << "native expressive pair test PASS\n";
}
