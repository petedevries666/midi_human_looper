#pragma once
// Native experimental pair-based HUMANIZER and VELOCITY CURVES foundation.
// NOT installed in a Zynthian chain until an instrument bridge is qualified.
#include "native_note_scheduler.hpp"
#include <array>
#include <algorithm>
#include <cmath>
#include <cstdint>
namespace expressive {
enum class Feel:uint8_t {Uniform,Gaussian};
enum class Variation:uint8_t {Fixed,Evolving};
enum class Scope:uint8_t {Group,Notes};
struct Identity {
  uint32_t instrument=0,phrase=0,iteration=0,group=0,note=0;
  uint64_t instance=0;
};
struct Humanizer {
  bool enabled=false;
  double timingMs=0,biasMs=0,velocityPercent=0,liveLookaheadMs=0;
  Feel feel=Feel::Gaussian;
  Variation variation=Variation::Fixed;
  Scope scope=Scope::Group;
  uint32_t seed=1;
  bool valid()const {
    return std::isfinite(timingMs) && timingMs>=0 && timingMs<=2000 &&
      std::isfinite(biasMs) && biasMs>=-2000 && biasMs<=2000 &&
      std::isfinite(velocityPercent) && velocityPercent>=0 && velocityPercent<=100 &&
      std::isfinite(liveLookaheadMs) && liveLookaheadMs>=0 && liveLookaheadMs<=2000 &&
      unsigned(feel)<=1 && unsigned(variation)<=1 && unsigned(scope)<=1;
  }
};
inline uint32_t mix(uint32_t a,uint32_t b){return a*1664525u+1013904223u+b;}
inline uint32_t hash(const Humanizer& c,const Identity& id,unsigned stream,bool group){
  uint32_t h=c.seed;
  h=mix(h,id.instrument);h=mix(h,id.phrase);
  h=mix(h,uint32_t(id.instance));h=mix(h,uint32_t(id.instance>>32));
  h=mix(h,c.variation==Variation::Evolving?id.iteration:0);
  h=mix(h,group?id.group:id.note);h=mix(h,stream);
  h^=h>>16;h*=0x85ebca6bu;h^=h>>13;h*=0xc2b2ae35u;h^=h>>16;
  return h;
}
inline double draw(const Humanizer& c,const Identity& id,unsigned stream,bool group){
  const unsigned n=c.feel==Feel::Gaussian?6:1;
  double sum=0;
  for(unsigned i=0;i<n;++i)sum+=2.*hash(c,id,stream+i*7919u,group)/4294967295.-1.;
  return sum/n; // Gaussian is bounded [-1,1], not unbounded normal.
}
inline int64_t delay(const Humanizer& c,const Identity& id,unsigned rate){
  if(!c.enabled || !c.valid() || !rate)return 0;
  return int64_t(std::llround((c.biasMs+c.timingMs*draw(c,id,17,c.scope==Scope::Group))*rate/1000.));
}
inline uint8_t velocity(const Humanizer& c,const Identity& id,uint8_t v){
  if(!v || !c.enabled || !c.valid() || c.velocityPercent==0)return v;
  const double add=126.*c.velocityPercent*draw(c,id,104729,false)/100.;
  return uint8_t(std::clamp(int(std::lround(double(v)+add)),1,127));
}
struct Point {uint8_t x=1,y=1;};
struct VelocityCurve {
  bool enabled=true;
  double amount=100;
  unsigned count=2;
  std::array<Point,16> points{{{1,1},{127,127}}};
  bool valid()const {
    if(!std::isfinite(amount) || amount<0 || amount>100 ||
       count<2 || count>points.size() || points[0].x!=1 || points[count-1].x!=127)return false;
    for(unsigned i=0;i<count;++i){
      if(points[i].x<1 || points[i].y<1 || points[i].y>127)return false;
      if(i && points[i].x<=points[i-1].x)return false;
    }
    return true;
  }
  uint8_t apply(uint8_t v)const {
    if(!v || !enabled || !amount || !valid())return v;
    unsigned i=1;
    while(i<count-1 && v>points[i].x)++i;
    const auto a=points[i-1],b=points[i];
    const double target=a.y+(double(b.y)-a.y)*(double(v)-a.x)/(b.x-a.x);
    return uint8_t(std::clamp(int(std::lround(double(v)+(target-v)*amount/100.)),1,127));
  }
};
// This adapter accepts complete recorded Note On/Off PAIRS only.
// Future live integration must retain identity from On until the actual Off.
// Negative shifts are allowed only with sufficient ahead-of-time source data;
// never emit an event in the past. No arbitrary downstream-chain bridge here.
template<size_t N=256,size_t S=512> class PairRuntime {
  native_notes::Scheduler<N,S> queue;
  native_notes::Outputs<N*2> outputs;
  unsigned rate;
public:
  uint64_t rejected=0,clamped=0;
  bool recoveryNeeded=false;
  explicit PairRuntime(unsigned sampleRate):queue(sampleRate),rate(sampleRate){}
  size_t active()const{return queue.active();}
  size_t sounding()const{return outputs.active();}
  native_notes::Refusal lastRefusal()const{return queue.lastRefusal;}
  bool schedule(const native_notes::SourceKey& key,uint32_t module,
                uint64_t on,uint64_t off,uint64_t now,uint8_t vel,
                const Identity& id,const Humanizer& h,const VelocityCurve& curve,
                bool protectOrigin=true) {
    if(rate<8000 || rate>384000 || !module || !h.valid() || !curve.valid() ||
       !vel || vel>127 || on<now || off<on || !key.instrument || key.channel>15 || key.pitch>127){
      ++rejected;return false;
    }
    const int64_t shift=protectOrigin && on==0 ? 0:delay(h,id,rate);
    uint64_t start=on;
    if(shift<0){
      const uint64_t n=uint64_t(-(shift+1))+1;
      start=n>on?0:on-n;
    }else if(shift>0){
      if(uint64_t(shift)>UINT64_MAX-on){++rejected;return false;}
      start+=uint64_t(shift);
    }
    if(start<now){start=now;++clamped;}
    const auto duration=off-on;
    if(start>UINT64_MAX-duration){++rejected;return false;}
    const auto source=queue.sources.begin(key,now);
    if(!source){++rejected;return false;}
    native_notes::Pair p{};
    p.owner={key.instrument,module,0,key.origin,key.instance};
    p.start=start;p.end=start+duration;p.channel=key.channel;p.pitch=key.pitch;
    p.velocity=curve.apply(velocity(h,id,vel));
    const bool ok=queue.admit(source,&p,1,now);
    queue.sources.close(source,now);
    queue.sources.retire(source);
    if(!ok)++rejected;
    return ok;
  }
  template<class Emit> void render(uint64_t start,uint32_t frames,Emit emit){
    queue.render(start,frames,[&](const native_notes::Event& e){
      if(e.on){
        const typename native_notes::Outputs<N*2>::Routed note{0,e.channel,e.pitch,e.velocity};
        return outputs.attackBatch(e.voice,&note,1,[&](const auto* batch,size_t count){
          return count==1 && emit(e.sample,true,batch[0].channel,batch[0].pitch,batch[0].velocity);
        });
      }
      return outputs.release(e.voice,[&](bool on,uint8_t ch,uint8_t pitch,uint8_t v){
        return emit(e.sample,on,ch,pitch,v);
      });
    });
    recoveryNeeded|=queue.needsRecovery;
  }
  template<class Emit> bool cancel(uint64_t now,uint32_t instrument,uint32_t module,Emit emit){
    const bool ok=queue.cancel(now,[&](const native_notes::Owner& o){
      return (!instrument || o.instrument==instrument) && (!module || o.module==module);
    },[&](const native_notes::Event& e){
      return outputs.release(e.voice,[&](bool on,uint8_t ch,uint8_t pitch,uint8_t v){
        return emit(now,on,ch,pitch,v);
      });
    });
    recoveryNeeded|=!ok;return ok;
  }
  // Only after the host successfully transmitted global physical PANIC.
  void recovered(){queue.resetAfterPanic();outputs.resetAfterPanic();recoveryNeeded=false;}
};
/*
 * Live source adapter. Unlike PairRuntime, this accepts the Note On before its
 * Note Off exists and captures one deterministic shift for the whole voice.
 * A fixed lookahead is an explicit live-latency choice; without enough lookahead
 * negative timing is clamped at arrival, never emitted into the past.
 */
template<size_t N=256> class StreamRuntime {
  static_assert(N>0,"Nonempty live voice table required");
  struct Voice {
    native_notes::SourceKey key{};
    Identity identity{};
    native_notes::Token token{};
    uint32_t module=0;
    uint64_t order=0,onDue=0;
    int64_t shift=0;
    uint8_t outputVelocity=0,offVelocity=0;
    unsigned reservations=0;
    bool used=false,held=false,sounding=false,offQueued=false;
  };
  struct Due {uint64_t sample=0,order=0;uint32_t slot=0;uint64_t generation=0;bool on=false;};
  std::array<Voice,N> voices{};
  std::array<Due,N*2> due{};
  std::array<uint32_t,16*128> physicalOwners{};
  size_t dueCount=0;
  uint64_t generation=0,ordinal=0;
  unsigned rate=0;
  size_t reserved=0;
  static bool before(const Due&a,const Due&b){return a.sample!=b.sample?a.sample<b.sample:a.order<b.order;}
  int findFree()const{for(size_t i=0;i<N;++i)if(!voices[i].used)return int(i);return -1;}
  bool push(const Due&e){
    if(dueCount>=due.size())return false;
    size_t i=dueCount++;while(i&&before(e,due[i-1])){due[i]=due[i-1];--i;}due[i]=e;return true;
  }
  Due pop(){Due e=due[0];for(size_t i=1;i<dueCount;++i)due[i-1]=due[i];--dueCount;return e;}
  bool remove(uint32_t slot,uint64_t gen,bool onOnly=false,bool offOnly=false){
    bool found=false;size_t n=0;
    for(size_t i=0;i<dueCount;++i){
      const auto&e=due[i];const bool match=e.slot==slot&&e.generation==gen&&(!onOnly||e.on)&&(!offOnly||!e.on);
      if(match)found=true;else due[n++]=e;
    }
    dueCount=n;return found;
  }
  Voice* get(const Due&e){if(e.slot>=N)return nullptr;auto&v=voices[e.slot];return v.used&&v.token.generation==e.generation?&v:nullptr;}
  template<class Emit> bool queueOff(uint32_t slot,Voice&v,uint64_t sample,Emit){
    if(v.offQueued)return false;
    if(!v.reservations)return false;
    Due e{sample,++ordinal,slot,v.token.generation,false};
    --v.reservations;--reserved;v.offQueued=true;v.held=false;
    if(!push(e)){++v.reservations;++reserved;v.offQueued=false;v.held=true;return false;}
    return true;
  }
public:
  uint64_t rejected=0,unmatchedOffs=0,clamped=0,emitted=0;
  bool recoveryNeeded=false;
  explicit StreamRuntime(unsigned sampleRate):rate(sampleRate){}
  size_t active()const{size_t n=0;for(const auto&v:voices)n+=v.used;return n;}
  size_t sounding()const{size_t n=0;for(const auto&v:voices)n+=v.used&&v.sounding;return n;}
  size_t pending()const{return dueCount;}
  template<class Emit> bool attack(const native_notes::SourceKey&key,uint32_t module,uint64_t sample,uint8_t input,
      const Identity&id,const Humanizer&h,const VelocityCurve&curve,Emit){
    if(rate<8000||rate>384000||!module||!key.instrument||key.channel>15||key.pitch>127||
       !input||input>127||!h.valid()||!curve.valid()||reserved+2>due.size()||
       generation==UINT64_MAX||ordinal>UINT64_MAX-2){++rejected;return false;}
    const int slot=findFree();if(slot<0){++rejected;return false;}
    const int64_t shift=h.enabled?delay(h,id,rate):0;
    const int64_t look=int64_t(std::llround((h.enabled?h.liveLookaheadMs:0)*rate/1000.));
    int64_t effective=shift;
    if(look>0 && effective>INT64_MAX-look){++rejected;return false;}
    effective+=look;
    if(effective<0){effective=0;++clamped;}
    if(uint64_t(effective)>UINT64_MAX-sample){++rejected;return false;}
    const auto token=native_notes::Token{uint32_t(slot),++generation,native_notes::TokenDomain::Voice};
    auto&v=voices[size_t(slot)];v=Voice{};v.key=key;v.identity=id;v.token=token;v.module=module;v.order=++ordinal;
    v.shift=int64_t(effective);v.onDue=sample+uint64_t(effective);v.outputVelocity=curve.apply(velocity(h,id,input));
    v.held=true;v.used=true;v.reservations=2;reserved+=2;
    Due e{v.onDue,++ordinal,uint32_t(slot),token.generation,true};--v.reservations;--reserved;
    if(!push(e)){reserved-=v.reservations;v=Voice{};++rejected;return false;}
    return true;
  }
  template<class Emit> bool release(const native_notes::SourceKey&key,uint64_t sample,uint8_t offVelocity,Emit){
    int match=-1;uint64_t first=UINT64_MAX;
    for(size_t i=0;i<N;++i){const auto&v=voices[i];if(v.used&&v.held&&v.key==key&&v.order<first){match=int(i);first=v.order;}}
    if(match<0){++unmatchedOffs;return false;}
    if(offVelocity>127){++rejected;return false;}
    auto&v=voices[size_t(match)];
    uint64_t dueSample=sample;
    if(v.shift>0){if(uint64_t(v.shift)>UINT64_MAX-sample){++rejected;return false;}dueSample+=uint64_t(v.shift);}
    if(dueSample<v.onDue){dueSample=v.onDue;++clamped;}
    if(ordinal==UINT64_MAX){++rejected;return false;}
    v.offVelocity=std::min<uint8_t>(offVelocity,127);
    if(!v.reservations){++rejected;recoveryNeeded=true;return false;}
    Due e{dueSample,++ordinal,uint32_t(match),v.token.generation,false};
    --v.reservations;--reserved;v.offQueued=true;v.held=false;
    if(!push(e)){++v.reservations;++reserved;v.offQueued=false;v.held=true;++rejected;return false;}
    return true;
  }
  template<class Emit> void render(uint64_t start,uint32_t frames,Emit emit){
    if(!frames)return;if(uint64_t(frames)>UINT64_MAX-start){recoveryNeeded=true;return;}const uint64_t end=start+frames;
    while(dueCount&&due[0].sample<end){
      const Due event=due[0];Voice*v=get(event);if(!v){pop();continue;}
      const uint64_t at=std::max(start,event.sample);
      const unsigned channel=v->key.channel,pitch=v->key.pitch,key=channel*128+pitch;
      if(event.on){
        if(!v->outputVelocity){pop();v->used=false;continue;}
        if(!physicalOwners[key]&&!emit(at,true,uint8_t(channel),uint8_t(pitch),v->outputVelocity)){
          recoveryNeeded=true;break;
        }
        ++physicalOwners[key];v->sounding=true;++emitted;pop();
      }else{
        if(v->sounding&&physicalOwners[key]==1&&!emit(at,false,uint8_t(channel),uint8_t(pitch),v->offVelocity)){
          recoveryNeeded=true;break;
        }
        if(v->sounding&&physicalOwners[key])--physicalOwners[key];
        ++emitted;pop();v->sounding=false;v->used=false;
        if(v->reservations){reserved-=v->reservations;v->reservations=0;}
      }
    }
  }
  template<class Match,class Emit> bool cancel(uint64_t now,Match match,Emit emit){
    bool ok=true;
    for(size_t i=0;i<N;++i){auto&v=voices[i];if(!v.used||!match(v.key,v.identity,v.module))continue;
      const auto gen=v.token.generation;remove(uint32_t(i),gen);
      if(v.sounding){
        v.offQueued=false;v.held=false;
        // Reuse a removed queued Note Off or the still-reserved release slot.
        if(!v.reservations){++v.reservations;++reserved;}
        if(!queueOff(uint32_t(i),v,now,emit)){ok=false;recoveryNeeded=true;}
      }else{
        if(reserved>=v.reservations)reserved-=v.reservations;
        v=Voice{};
      }
    }
    (void)now;return ok;
  }
  template<class Emit> bool cancel(uint64_t now,uint32_t instrument,uint32_t module,Emit emit){
    return cancel(now,[&](const native_notes::SourceKey&k,const Identity&,uint32_t ownerModule){
      return (!instrument||k.instrument==instrument)&&(!module||ownerModule==module);
    },emit);
  }
  // Only after successful physical all-notes-off recovery.
  void recovered(){voices.fill(Voice{});dueCount=0;physicalOwners.fill(0);reserved=0;recoveryNeeded=false;}
};

}
