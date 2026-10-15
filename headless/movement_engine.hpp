#pragma once
#include "conductor_document.hpp"
#include "controller_host.hpp"
#include <functional>
#include <limits>
#include <memory>
// Immutable curves prepared on the paused control worker. Runtime uses existing
// Controller tokens and host sample position; it owns no note scheduler.
namespace movement {
struct Definition {
  std::string id;
  controller::Binding binding;
  std::shared_ptr<const std::vector<controller::Point>> points;
  void curve(std::initializer_list<controller::Point> p){points=std::make_shared<const std::vector<controller::Point>>(p);}
  bool cc=true, hold=false, soft=true;
  unsigned channel=0, number=0;
  double duration=1, glide=.2;
  double value(double x) const {
    x=controller::clamp(x);
    auto b=std::upper_bound(points->begin(),points->end(),x,[](double x,const controller::Point &p){return x<p.x;});
    if(b==points->begin())return b->y;
    if(b==points->end())return points->back().y;
    const auto &a=*(b-1);
    return hold?a.y:a.y+(b->y-a.y)*(x-a.x)/(b->x-a.x);
  }
};
struct Prepared {
  std::vector<Definition> definitions;
  std::map<std::string,unsigned> blocks;
  unsigned rate=25;
};
inline Prepared prepare(const std::vector<unsigned>& bytes) {
  Prepared out;if(bytes.empty())return out;
  std::string text;for(auto c:bytes)text+=char(c);conductor::Parser parser(text);auto root=parser.value();
  if(root.at("version").number<2)return out;
  out.rate=unsigned(root.at("ccRate").number);
  std::map<std::string,unsigned> sources;
  auto target=[](Definition& d,const conductor::Value& t){
    d.cc=conductor::choice(t.at("type"),{"CC"});
    if(d.cc){d.channel=unsigned(t.at("channel").number)-1;d.number=unsigned(t.at("number").number);}
    else{d.binding.instrument=t.at("instrumentId").number;d.binding.module=t.at("moduleId").number;d.binding.kind=int(t.at("kind").number);}
  };
  for(const auto &m:root.at("movements").array){
    Definition d;d.id=m.at("id").text;target(d,m.at("target"));d.duration=m.at("duration").number;d.glide=m.at("glideSeconds").number;
    d.hold=conductor::choice(m.at("interpolation"),{"HOLD"});d.soft=conductor::choice(m.at("retrigger"),{"SOFT_RESTART"});
    auto points=std::make_shared<std::vector<controller::Point>>();
    for(const auto &p:m.at("points").array)points->emplace_back(p.array[0].number,p.array[1].number,0);
    d.points=points;
    sources[d.id]=out.definitions.size();out.definitions.push_back(std::move(d));
  }
  // Local overrides become immutable execution views, never mutate source data.
  for(const auto &sw:root.at("switches").array)for(const auto &step:sw.at("steps").array)for(const auto &layer:step.at("layers").array){
    const auto &b=layer.at("block");if(b.type=='z'||!conductor::choice(b.at("type"),{"MOVEMENT"}))continue;
    auto src=sources.find(b.at("sourceId").text);if(src==sources.end())continue;
    Definition d=out.definitions[src->second];bool supported=true;
    for(const auto &o:b.at("overrides").object){
      if(conductor::choice(o.second.at("mode"),{"INHERIT"}))continue;
      const auto &v=o.second.at("value");
      if(o.first=="destination")target(d,v);
      else if(o.first=="retrigger")d.soft=conductor::choice(v,{"SOFT_RESTART"});
      else if((o.first=="trigger"&&conductor::choice(v,{"PRESS","HOLD"}))||(o.first=="join"&&conductor::choice(v,{"TRIGGER"}))||(o.first=="movementPlayMode"&&conductor::choice(v,{"ONE_SHOT"}))){}
      else supported=false;
    }
    if(supported){out.blocks[b.at("id").text]=out.definitions.size();out.definitions.push_back(std::move(d));}
  }
  return out;
}
class Runtime {
  struct Voice {const Definition* source=nullptr;uint32_t target=0;uint64_t token=0,start=0,end=0,next=0,tick=0;double from=0;bool initial=true;};
  std::array<Voice,controller::Engine::TargetCapacity> voices{};
  std::array<int,2048> last{};
  std::array<uint64_t,2048> physicalAt{};
  controller::Host &host;
  double sampleRate;
  unsigned rate=25,blockFrames=256;
public:
  Prepared plan; // mutated only while the process thread is paused
  unsigned rejected=0,active=0,emitted=0,cancelled=0;
  explicit Runtime(controller::Host& h,double sr):host(h),sampleRate(sr){last.fill(-1);physicalAt.fill(UINT64_MAX);}
  void cancel(Voice& v){if(!v.source)return;bool released=host.cancelPerformanceTarget(v.target,v.token);if(v.source->cc&&released)host.retirePerformanceTarget(v.target);v=Voice{};--active;++cancelled;}
  void panic(){for(auto &v:voices)cancel(v);}
  void stop(unsigned index){if(index>=plan.definitions.size())return;for(auto &v:voices)if(v.source&&v.source->id==plan.definitions[index].id)cancel(v);}
  void install(Prepared next){panic();plan=std::move(next);rate=plan.rate;last.fill(-1);physicalAt.fill(UINT64_MAX);}
  template<class Report> void observe(uint64_t sample,Report report) const{
    for(const auto &v:voices)if(v.source)report(v.source->id.c_str(),controller::clamp(double(sample-v.start)/(v.end-v.start)));
  }
  void block(unsigned frames){blockFrames=frames;}
  void physical(unsigned ch,unsigned cc,unsigned value,uint64_t sample=0){
    if(ch>=16||cc>=128||value>127)return;
    last[ch*128+cc]=int(value);physicalAt[ch*128+cc]=sample;
    for(auto &v:voices)if(v.source&&v.source->cc&&v.source->channel==ch&&v.source->number==cc)cancel(v);
  }
  template<class Resolve>
  bool start(unsigned index,uint64_t sample,Resolve resolve){
    if(index>=plan.definitions.size()){++rejected;return false;}
    auto &d=plan.definitions[index];uint32_t id=0;double effective=d.points->front().y;
    if(d.cc){
      // Sustain and channel-mode messages are safety events, never automation.
      if(d.number==64||d.number>=120){++rejected;return false;}
      unsigned key=d.channel*128+d.number;
      if(physicalAt[key]!=UINT64_MAX&&physicalAt[key]>=sample){++cancelled;return true;}
      id=0x80000000u+key;
      if(last[d.channel*128+d.number]>=0)effective=last[d.channel*128+d.number]/127.;
    } else if(!resolve(d.binding,id,effective)){++rejected;return false;}
    if(d.cc){
      unsigned claimed=0;for(const auto &v:voices)if(v.source&&v.source->cc&&v.target!=id)++claimed;
      unsigned cost=unsigned(std::ceil(blockFrames*double(rate)/sampleRate))+2;
      // The existing JACK output drain is 64 events per callback. Reserve a
      // worst-case cadence + initial/final budget before admitting this target.
      if((claimed+1)*cost>64){++rejected;return false;}
    }
    const double samples=d.duration*sampleRate;
    if(!std::isfinite(samples)||samples<1||samples>double(9007199254740991ULL-sample)){++rejected;return false;}
    auto existing=host.target(id);if(existing)effective=existing->effective;
    if(!existing&&!host.stagePerformanceTarget(id,effective)){++rejected;return false;}
    Voice *slot=nullptr;for(auto &v:voices)if(v.source&&v.target==id){slot=&v;break;}
    if(!slot)for(auto &v:voices)if(!v.source){slot=&v;break;}
    if(!slot){++rejected;return false;}
    // Acquire once, respecting physical priority. Losing tokens never reacquire.
    auto token=host.acquirePerformanceTarget(id,d.soft?effective:d.points->front().y);
    if(!token){++rejected;return false;}
    if(slot->source){*slot=Voice{};--active;}
    slot->source=&d;slot->target=id;slot->token=token;slot->start=slot->next=sample;slot->end=sample+uint64_t(std::ceil(samples));slot->from=effective;++active;return true;
  }
  template<class Emit,class Apply>
  void render(uint64_t until,Emit emit,Apply apply,bool ccOnly=false,bool parametersOnly=false){
    unsigned budget=8192; // existing host processing-block batch capacity
    for(auto &v:voices){
      if(!v.source||(ccOnly&&!v.source->cc)||(parametersOnly&&v.source->cc))continue;
      auto t=host.target(v.target);
      if(!t||t->owner!=UINT32_MAX||t->token!=v.token){cancel(v);continue;}
      const auto &d=*v.source;
      if(until<=v.start)continue;
      if(!d.cc){
        double x=controller::clamp(double(until-v.start)/(v.end-v.start));double goal=d.value(x);
        double value=d.soft?controller::glide(v.from,goal,double(until-v.start)/sampleRate,std::min(d.glide,d.duration)):goal;
        if(!host.updatePerformanceTarget(v.target,v.token,value)||!apply(d.binding,value)){cancel(v);continue;}
        if(until>=v.end)cancel(v);continue;
      }
      while(v.source&&v.next<until){
        if(!budget--){++rejected;panic();return;}
        auto sample=v.next;double x=double(sample-v.start)/(v.end-v.start),goal=d.value(x);
        double value=d.soft?controller::glide(v.from,goal,double(sample-v.start)/sampleRate,std::min(d.glide,d.duration)):goal;
        if(sample==v.end)value=d.points->back().y;
        if(!host.updatePerformanceTarget(v.target,v.token,value)){cancel(v);break;}
        unsigned rounded=unsigned(std::floor(controller::clamp(value)*127+.5)),key=d.channel*128+d.number;
        if(v.initial||last[key]!=int(rounded)){
          if(!emit(sample,d.channel,d.number,rounded)){++rejected;panic();return;}
          last[key]=rounded;++emitted;
        }
        v.initial=false;
        if(sample==v.end){cancel(v);break;}
        ++v.tick;v.next=std::min(v.end,v.start+uint64_t(std::ceil(v.tick*sampleRate/rate)));
      }
    }
  }
};
}
