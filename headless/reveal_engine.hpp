#pragma once
#include "controller_host.hpp"

// Native PHRASE instance CC7 leases. Ownership is exclusively Controller Host
// tokens, in the same raw-CC namespace as MOVEMENT. No scheduler or MIDI queue.
namespace reveal {
inline uint32_t target(unsigned channel){return 0x80000000u+channel*128+7;}
class Runtime {
  struct Voice {bool hidden=true;uint64_t id=0;std::array<uint64_t,16> tokens{};std::array<unsigned,16> volume{};};
  std::array<Voice,12> voices{}; // existing independent PHRASE admission budget
  std::array<int,16> observed{},pending{};
  std::array<uint64_t,16> physicalAt{};
  controller::Host &host;
  bool owns(const Voice &v,unsigned ch)const{
    auto t=host.target(target(ch));return v.tokens[ch]&&t&&t->owner==UINT32_MAX&&t->token==v.tokens[ch];
  }
public:
  unsigned rejected=0;
  explicit Runtime(controller::Host& h):host(h){observed.fill(-1);pending.fill(-1);physicalAt.fill(UINT64_MAX);}
  unsigned existingMask()const{unsigned mask=0;for(unsigned ch=0;ch<16;++ch)if(host.target(target(ch)))mask|=1u<<ch;return mask;}
  // Stage the worker/DSP preflight reservation before any post-DSP automation
  // can consume the available Controller targets. No partial capacity mutation.
  bool reserve(unsigned mask){
    unsigned need=0;for(unsigned ch=0;ch<16;++ch)if((mask&(1u<<ch))&&!host.target(target(ch)))++need;
    if(need>host.freeTargets()){++rejected;return false;}
    for(unsigned ch=0;ch<16;++ch)if((mask&(1u<<ch))&&!host.target(target(ch)))host.stagePerformanceTarget(target(ch),(observed[ch]<0?127:observed[ch])/127.);
    return true;
  }
  // Physical input is passed intact by the host. Invalidate only matching leases;
  // a superseded instance never reacquires on HOLD, RELEASE, or cleanup.
  void physical(unsigned ch,unsigned cc,unsigned value,uint64_t sample){
    if(ch>=16||cc!=7||value>127)return;
    observed[ch]=value;physicalAt[ch]=sample;pending[ch]=-1;
    for(auto &v:voices)if(owns(v,ch)){host.cancelPerformanceTarget(target(ch),v.tokens[ch]);host.stagePerformanceTarget(target(ch),value/127.);}
  }
  // Ordinary emitted CC7 (manual/Controller/PHRASE) updates the audible baseline
  // and takes precedence over an earlier hidden lease, without changing notes.
  void observe(unsigned ch,unsigned cc,unsigned value){
    if(ch>=16||cc!=7||value>127)return;
    observed[ch]=value;
    for(auto &v:voices)if(owns(v,ch)){host.cancelPerformanceTarget(target(ch),v.tokens[ch]);host.stagePerformanceTarget(target(ch),value/127.);}
  }
  template<class Emit> bool start(unsigned slot,uint64_t id,unsigned mask,uint64_t sample,Emit emit){
    if(slot>=voices.size()||!id){++rejected;return false;}
    if(!reserve(mask))return false;
    auto &v=voices[slot];if(v.id)close(slot,v.id,sample,emit);v=Voice{};v.id=id;
    for(unsigned ch=0;ch<16;++ch)if(mask&(1u<<ch)){
      auto t=host.target(target(ch));unsigned volume=t?unsigned(std::floor(t->effective*127+.5)):(observed[ch]<0?127:unsigned(observed[ch]));
      // A replacement hidden owner retains the audible restore value, never 0.
      if(t)for(const auto &old:voices)if(old.id&&owns(old,ch))volume=old.volume[ch];
      v.volume[ch]=volume;
      if(physicalAt[ch]!=UINT64_MAX&&physicalAt[ch]>=sample)continue;
      v.tokens[ch]=host.acquirePerformanceTarget(target(ch),0);
      if(!v.tokens[ch]||!emit(sample,ch,7,0)){++rejected;return false;}
    }return true;
  }
  template<class Emit> void mask(unsigned slot,uint64_t id,bool hidden,uint64_t sample,Emit emit){
    if(slot>=voices.size()||voices[slot].id!=id)return;
    auto &v=voices[slot];v.hidden=hidden;
    for(unsigned ch=0;ch<16;++ch)if(owns(v,ch)){
      unsigned value=hidden?0:v.volume[ch];host.updatePerformanceTarget(target(ch),v.tokens[ch],value/127.);
      if(!emit(sample,ch,7,value))++rejected;
    }
  }
  template<class Emit> void close(unsigned slot,uint64_t id,uint64_t sample,Emit emit){
    if(slot>=voices.size()||voices[slot].id!=id)return;
    auto &v=voices[slot];
    for(unsigned ch=0;ch<16;++ch)if(owns(v,ch)){
      unsigned value=v.volume[ch];host.updatePerformanceTarget(target(ch),v.tokens[ch],value/127.);
      if(!emit(sample,ch,7,value))++rejected;
      observed[ch]=value;host.cancelPerformanceTarget(target(ch),v.tokens[ch]);
      host.retirePerformanceTarget(target(ch));
    }v=Voice{};
  }
  template<class Report> void observeState(Report report)const{
    for(const auto &v:voices)if(v.id){unsigned mask=0;for(unsigned ch=0;ch<16;++ch)if(owns(v,ch))mask|=1u<<ch;report(v.id,v.hidden,mask,v.volume);}
  }
  // Run after the chronological control batch, never between reservations and
  // admissions. An unowned raw CC7 target cannot resume a superseded instance.
  void collectIdle(){for(unsigned ch=0;ch<16;++ch){auto t=host.target(target(ch));if(t&&!t->owner&&!t->morphing)host.retirePerformanceTarget(target(ch));}}
  void panic(){
    for(auto &v:voices){for(unsigned ch=0;ch<16;++ch)if(owns(v,ch)){
      pending[ch]=int(v.volume[ch]);host.cancelPerformanceTarget(target(ch),v.tokens[ch]);host.retirePerformanceTarget(target(ch));
    }v=Voice{};}
  }
  template<class Emit> void flush(uint64_t sample,Emit emit){
    for(unsigned ch=0;ch<16;++ch)if(pending[ch]>=0){if(!emit(sample,ch,7,unsigned(pending[ch]))){++rejected;continue;}observed[ch]=pending[ch];pending[ch]=-1;}
  }
};
}
