#pragma once
#include "controller_host.hpp"
namespace reveal {
inline uint32_t target(unsigned channel,unsigned cc=7){return 0x80000000u+channel*128+cc;}
class Runtime {
  struct Ramp {bool active=false;uint64_t start=0,end=0,next=0,tick=0;double from=0,to=0;};
  struct Voice {bool hidden=true;uint64_t id=0;unsigned cc=7;double fade=0;std::array<uint64_t,16> tokens{};std::array<unsigned,16> volume{};std::array<Ramp,16> ramps{};};
  std::array<Voice,12> voices{};
  std::array<unsigned,12> configCC{};std::array<double,12> configFade{};
  std::array<int,2048> observed{},pending{};
  std::array<uint64_t,2048> physicalAt{};
  std::array<bool,2048> used{};
  controller::Host &host;double sampleRate;
  bool owns(const Voice &v,unsigned ch)const{if(!v.tokens[ch])return false;auto t=host.target(target(ch,v.cc));return t&&t->owner==UINT32_MAX&&t->token==v.tokens[ch];}
public:
  unsigned rejected=0;
  explicit Runtime(controller::Host& h,double sr=48000):host(h),sampleRate(sr){configCC.fill(7);observed.fill(-1);pending.fill(-1);physicalAt.fill(UINT64_MAX);}
  void configure(unsigned slot,unsigned cc,double seconds){if(slot>=12||cc>=120||cc==64||!std::isfinite(seconds)||seconds<0||seconds>60){++rejected;return;}configCC[slot]=cc;configFade[slot]=seconds;}
  unsigned existingMask()const{unsigned mask=0;for(unsigned ch=0;ch<16;++ch)if(host.target(target(ch)))mask|=1u<<ch;return mask;}
  bool reserve(unsigned mask,unsigned cc=7){
    unsigned need=0;for(unsigned ch=0;ch<16;++ch)if((mask&(1u<<ch))&&!host.target(target(ch,cc)))++need;
    if(need>host.freeTargets()){++rejected;return false;}
    for(unsigned ch=0;ch<16;++ch)if(mask&(1u<<ch)){unsigned key=ch*128+cc;used[key]=true;if(!host.target(target(ch,cc)))host.stagePerformanceTarget(target(ch,cc),(observed[key]<0?127:observed[key])/127.);}
    return true;
  }
  void physical(unsigned ch,unsigned cc,unsigned value,uint64_t sample){
    if(ch>=16||cc>=120||cc==64||value>127)return;
    unsigned key=ch*128+cc;observed[key]=value;physicalAt[key]=sample;pending[key]=-1;
    for(auto &v:voices)if(v.cc==cc&&owns(v,ch)){v.ramps[ch].active=false;host.cancelPerformanceTarget(target(ch,cc),v.tokens[ch]);host.stagePerformanceTarget(target(ch,cc),value/127.);}
  }
  void observe(unsigned ch,unsigned cc,unsigned value){
    if(ch>=16||cc>=120||cc==64||value>127)return;observed[ch*128+cc]=value;
    for(auto &v:voices)if(v.cc==cc&&owns(v,ch)){v.ramps[ch].active=false;host.cancelPerformanceTarget(target(ch,cc),v.tokens[ch]);host.stagePerformanceTarget(target(ch,cc),value/127.);}
  }
  template<class Emit> bool start(unsigned slot,uint64_t id,unsigned mask,uint64_t sample,Emit emit){
    if(slot>=voices.size()||!id){++rejected;return false;}
    unsigned cc=configCC[slot];if(!reserve(mask,cc))return false;
    auto &v=voices[slot];if(v.id)close(slot,v.id,sample,emit);v=Voice{};v.id=id;v.cc=cc;v.fade=configFade[slot];
    for(unsigned ch=0;ch<16;++ch)if(mask&(1u<<ch)){
      auto t=host.target(target(ch,cc));unsigned key=ch*128+cc;
      unsigned volume=t?unsigned(std::floor(t->effective*127+.5)):(observed[key]<0?127:unsigned(observed[key]));
      if(t)for(const auto &old:voices)if(old.id&&old.cc==cc&&owns(old,ch))volume=old.volume[ch];
      v.volume[ch]=volume;if(physicalAt[key]!=UINT64_MAX&&physicalAt[key]>=sample)continue;
      v.tokens[ch]=host.acquirePerformanceTarget(target(ch,cc),0);
      if(!v.tokens[ch]||!emit(sample,ch,cc,0)){++rejected;return false;}
    }return true;
  }
  template<class Emit> void mask(unsigned slot,uint64_t id,bool hidden,uint64_t sample,Emit emit){
    if(slot>=voices.size()||voices[slot].id!=id)return;auto &v=voices[slot];v.hidden=hidden;
    for(unsigned ch=0;ch<16;++ch)if(owns(v,ch)){
      auto &r=v.ramps[ch];double goal=(hidden?0:v.volume[ch])/127.;
      if(v.fade>0){r=Ramp{};r.active=true;r.start=r.next=sample;r.end=sample+std::max<uint64_t>(1,uint64_t(std::ceil(v.fade*sampleRate)));r.from=host.target(target(ch,v.cc))->effective;r.to=goal;}
      else{r.active=false;host.updatePerformanceTarget(target(ch,v.cc),v.tokens[ch],goal);if(!emit(sample,ch,v.cc,unsigned(std::floor(goal*127+.5))))++rejected;}
    }
  }
  template<class Emit> void render(uint64_t until,Emit emit){
    for(auto &v:voices)if(v.id)for(unsigned ch=0;ch<16;++ch){auto &r=v.ramps[ch];if(!r.active)continue;if(!owns(v,ch)){r.active=false;continue;}
      while(r.active&&r.next<until){
        double x=controller::clamp(double(r.next-r.start)/(r.end-r.start)),value=r.from+(r.to-r.from)*x;
        if(!host.updatePerformanceTarget(target(ch,v.cc),v.tokens[ch],value)){r.active=false;break;}
        unsigned key=ch*128+v.cc,rounded=unsigned(std::floor(value*127+.5));
        if(observed[key]!=int(rounded)){if(!emit(r.next,ch,v.cc,rounded)){++rejected;r.active=false;break;}observed[key]=rounded;}
        if(r.next==r.end){r.active=false;break;}++r.tick;r.next=std::min(r.end,r.start+uint64_t(std::ceil(r.tick*sampleRate/25.)));
      }
    }
  }
  template<class Emit> void close(unsigned slot,uint64_t id,uint64_t sample,Emit emit){
    if(slot>=voices.size()||voices[slot].id!=id)return;auto &v=voices[slot];
    for(unsigned ch=0;ch<16;++ch)if(owns(v,ch)){unsigned value=v.volume[ch];host.updatePerformanceTarget(target(ch,v.cc),v.tokens[ch],value/127.);if(!emit(sample,ch,v.cc,value))++rejected;observed[ch*128+v.cc]=value;host.cancelPerformanceTarget(target(ch,v.cc),v.tokens[ch]);host.retirePerformanceTarget(target(ch,v.cc));}v=Voice{};
  }
  template<class Report> void observeState(Report report)const{for(const auto &v:voices)if(v.id){unsigned mask=0;for(unsigned ch=0;ch<16;++ch)if(owns(v,ch))mask|=1u<<ch;report(v.id,v.hidden,mask,v.volume);}}
  void collectIdle(){for(unsigned key=0;key<2048;++key)if(used[key]){auto t=host.target(0x80000000u+key);if(!t){used[key]=false;continue;}if(!t->owner&&!t->morphing){host.retirePerformanceTarget(0x80000000u+key);used[key]=false;}}}
  void panic(){for(auto &v:voices){for(unsigned ch=0;ch<16;++ch)if(owns(v,ch)){pending[ch*128+v.cc]=int(v.volume[ch]);host.cancelPerformanceTarget(target(ch,v.cc),v.tokens[ch]);host.retirePerformanceTarget(target(ch,v.cc));}v=Voice{};}}
  template<class Emit> void flush(uint64_t sample,Emit emit){for(unsigned key=0;key<2048;++key)if(pending[key]>=0){if(!emit(sample,key/128,key%128,unsigned(pending[key]))){++rejected;continue;}observed[key]=pending[key];pending[key]=-1;}}
};
}
