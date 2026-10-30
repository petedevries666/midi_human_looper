#pragma once
#include "native_note_scheduler.hpp"

namespace echocity {
enum class TimeUnit : uint8_t { Milliseconds, Beats };
enum class Traversal : uint8_t { Forward, ReverseAll, Alternate, RandomChaos };
// Configuration only. Runtime source/output leases belong to the one shared
// native scheduler, so adding another unit never adds another event queue.
struct Configuration {
  uint32_t id=0,instrument=0,continuation=0;
  bool enabled=true;
  TimeUnit unit=TimeUnit::Milliseconds;
  double interval=250,firstOffset=1,wet=.5,decay=.7,gate=1,gateDecay=1,dry=1;
  unsigned repeats=4;
  int pitchStep=0;
  bool pingPong=false;
  unsigned otherChannel=1;
  Traversal traversal=Traversal::Forward;
};
inline bool valid(const Configuration &c){
  return c.id && c.id<=16777215 && c.instrument && c.instrument<=16777215 && c.continuation<=16777215 &&
    (c.unit==TimeUnit::Milliseconds || c.unit==TimeUnit::Beats) &&
    std::isfinite(c.interval) && c.interval>0 && c.interval<=(c.unit==TimeUnit::Milliseconds?60000:64) &&
    std::isfinite(c.firstOffset) && c.firstOffset>=0 && c.firstOffset<=16 &&
    std::isfinite(c.wet) && c.wet>=0 && c.wet<=1 &&
    std::isfinite(c.dry) && c.dry>=0 && c.dry<=1 &&
    std::isfinite(c.decay) && c.decay>=0 && c.decay<=1 &&
    std::isfinite(c.gate) && c.gate>=0 && c.gate<=4 &&
    std::isfinite(c.gateDecay) && c.gateDecay>=0 && c.gateDecay<=1 &&
    c.repeats>=1 && c.repeats<=32 && c.pitchStep>=-48 && c.pitchStep<=48 && c.otherChannel<16 && unsigned(c.traversal)<=3;
}
struct Admission {
  unsigned dryVelocity=0,planned=0,admitted=0;
  bool ok=false;
};
class Unit {
  Configuration config{};
  unsigned sampleRate;
public:
  uint64_t rejected=0;
  explicit Unit(unsigned rate=48000):sampleRate(rate){}
  bool configure(const Configuration &candidate){
    if(!valid(candidate) || sampleRate<8000 || sampleRate>384000)return false;
    config=candidate;return true;
  }
  const Configuration &configuration()const{return config;}
  template<size_t Voices,size_t Sources>
  Admission plan(native_notes::Scheduler<Voices,Sources> &scheduler,native_notes::Token source,
                    unsigned channel,unsigned pitch,unsigned velocity,uint64_t now,std::array<native_notes::Pair,32>&pairs,double tempo=0,uint64_t anchor=UINT64_MAX){
    Admission result{};result.dryVelocity=velocity<=127?velocity:0;
    const auto *parent=scheduler.sources.get(source);
    auto reject=[&](){++rejected;result.dryVelocity=velocity<=127?velocity:0;return result;};
    if(!valid(config) || !parent || parent->key.instrument!=config.instrument || channel>15 || pitch>127 || !velocity || velocity>127 || scheduler.maxHorizon()!=uint64_t(sampleRate)*60)return reject();
    if(!config.enabled){result.dryVelocity=velocity;result.ok=true;return result;}
    result.dryVelocity=unsigned(std::floor(velocity*config.dry+.5));
    if(config.wet==0){result.ok=true;return result;}
    if(config.unit==TimeUnit::Beats && (!std::isfinite(tempo) || tempo<=0 || tempo>1000))return reject();
    const double step=config.unit==TimeUnit::Milliseconds?config.interval*sampleRate/1000.:config.interval*60.*sampleRate/tempo;
    const double first=step*config.firstOffset;
    if(!std::isfinite(step) || !std::isfinite(first) || step<1 || first>scheduler.maxHorizon() || parent->start>UINT64_MAX-scheduler.maxHorizon()){
      return reject();
    }
    const bool buffered=anchor!=UINT64_MAX;const uint64_t base=buffered?anchor:parent->start;
    if(base>UINT64_MAX-scheduler.maxHorizon() || now>UINT64_MAX-scheduler.maxHorizon())return reject();
    double amplitude=velocity*config.wet,gate=config.gate;
    for(unsigned repeat=0;repeat<config.repeats;++repeat){
      const int nextPitch=int(pitch)+int(repeat+1)*config.pitchStep;
      const unsigned nextVelocity=unsigned(std::floor(amplitude+.5));
      // Stop at MIDI bounds or inaudible decay. Never wrap pitch or emit
      // velocity-zero Note On as if it were another attack.
      if(nextPitch<0 || nextPitch>127 || !nextVelocity)break;
      const double relative=first+step*repeat;
      if(relative>scheduler.maxHorizon())return reject();
      auto &p=pairs[result.planned++];p.owner={config.instrument,config.id,config.continuation,parent->key.origin,parent->key.instance};
      p.start=base+uint64_t(std::floor(relative+.5));p.end=(buffered?now:parent->start)+scheduler.maxHorizon();
      if(p.start<now || p.start>p.end)return reject();
      p.channel=uint8_t(config.pingPong && repeat%2==0?config.otherChannel:channel);
      p.pitch=uint8_t(nextPitch);p.velocity=uint8_t(nextVelocity);p.followSource=true;p.durationScale=gate;
      if(!parent->held || gate==0){
        const double duration=gate==0?0:std::min(double(scheduler.maxHorizon()),double(parent->end-parent->start)*gate);
        const uint64_t length=uint64_t(std::floor(duration+.5));
        p.end=std::min(p.end,p.start>UINT64_MAX-length?UINT64_MAX:p.start+length);
      }
      amplitude*=config.decay;gate*=config.gateDecay;
    }
    if(!result.planned){result.ok=true;return result;}
    result.ok=true;return result;
  }
  template<size_t Voices,size_t Sources>
  Admission trigger(native_notes::Scheduler<Voices,Sources> &scheduler,native_notes::Token source,
                    unsigned channel,unsigned pitch,unsigned velocity,uint64_t now,double tempo=0){
    std::array<native_notes::Pair,32> pairs{};auto result=plan(scheduler,source,channel,pitch,velocity,now,pairs,tempo);
    if(result.ok && result.planned){result.ok=scheduler.admit(source,pairs.data(),result.planned,now);if(result.ok)result.admitted=result.planned;else{++rejected;result.dryVelocity=velocity<=127?velocity:0;}}
    return result;
  }
};
} // namespace echocity
