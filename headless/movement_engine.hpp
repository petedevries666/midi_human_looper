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
  bool cc=true, hold=false, soft=true, gated=false;
  double releaseSeconds=.2,restValue=.5;
  struct Charge {bool enabled=false;double from=0,to=1,factor=1;double value(double q)const{return from+(to-from)*controller::clamp(q*factor);}};
  Charge chargeDuration,chargeAmplitude,chargeValue;
  unsigned channel=0, number=0, cycle=0;
  double duration=1, glide=.2;
  double value(double x) const {
    x=controller::clamp(x);
    auto b=std::upper_bound(points->begin(),points->end(),x,[](double x,const controller::Point &p){return x<p.x;});
    if(b==points->begin())return b->y;
    if(b==points->end())return points->back().y;
    const auto &a=*(b-1);
    if(hold)return a.y;
    double t=(x-a.x)/(b->x-a.x),power=1+5*std::abs(a.bend);
    if(a.bend>0)t=std::pow(t,power);
    else if(a.bend<0)t=1-std::pow(1-t,power);
    return a.y+(b->y-a.y)*t;
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
    if(m.object.count("playMode")){d.gated=conductor::choice(m.at("playMode"),{"GATED"});d.releaseSeconds=m.at("releaseSeconds").number;d.restValue=m.at("restValue").number;}
    if(m.object.count("cycleMode"))d.cycle=conductor::choice(m.at("cycleMode"),{"LOOP"})?1:conductor::choice(m.at("cycleMode"),{"PING_PONG"})?2:0;
    d.hold=conductor::choice(m.at("interpolation"),{"HOLD"});d.soft=conductor::choice(m.at("retrigger"),{"SOFT_RESTART"});
    auto points=std::make_shared<std::vector<controller::Point>>();
    for(const auto &p:m.at("points").array)points->emplace_back(p.array[0].number,p.array[1].number,p.array.size()==3?p.array[2].number:0);
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
      else if(o.first=="movementPlayMode")d.gated=conductor::choice(v,{"GATED"});
      else if(o.first=="movementDuration")d.duration=v.number;
      else if(o.first=="movementCycle")d.cycle=conductor::choice(v,{"LOOP"})?1:conductor::choice(v,{"PING_PONG"})?2:0;
      else if(o.first=="releaseSeconds")d.releaseSeconds=v.number;
      else if(o.first=="restValue")d.restValue=v.number;
      else if((o.first=="trigger"&&conductor::choice(v,{"PRESS","HOLD","LONG_HOLD","RELEASE","SUPERCHARGE_RELEASE"}))||(o.first=="join"&&conductor::choice(v,{"TRIGGER"}))||(o.first=="movementPlayMode"&&conductor::choice(v,{"ONE_SHOT"}))){}
      else supported=false;
    }
    if(step.object.count("supercharge"))for(const auto &a:step.at("supercharge").at("bindings").array)if(!a.object.count("target")&&a.at("blockId").text==b.at("id").text){auto &axis=a.at("parameter").text=="movementDuration"?d.chargeDuration:d.chargeAmplitude;axis.enabled=true;axis.from=a.at("from").number;axis.to=a.at("to").number;axis.factor=a.at("factor").number;}
    if(supported){out.blocks[b.at("id").text]=out.definitions.size();out.definitions.push_back(std::move(d));}
  }
  for(const auto &sw:root.at("switches").array)for(const auto &step:sw.at("steps").array)if(step.object.count("supercharge")){
    unsigned i=0;for(const auto &a:step.at("supercharge").at("bindings").array){
      if(a.object.count("target")){Definition d;d.id="charge:"+step.at("id").text+":"+std::to_string(i);target(d,a.at("target"));d.soft=false;d.duration=.001;d.curve({{0,0,0},{1,0,0}});d.chargeValue.enabled=true;d.chargeValue.from=performance::normalized(d.binding.kind,a.at("from").number);d.chargeValue.to=performance::normalized(d.binding.kind,a.at("to").number);d.chargeValue.factor=a.at("factor").number;out.blocks[d.id]=out.definitions.size();out.definitions.push_back(std::move(d));}++i;
    }
  }
  return out;
}
class Runtime {
  struct Voice {const Definition* source=nullptr;uint32_t target=0;uint64_t token=0,start=0,end=0,next=0,tick=0;double from=0,amplitude=1,constant=-1;bool initial=true,releasing=false;unsigned owner=UINT32_MAX;uint64_t gesture=0;};
  static double phase(const Voice &v,uint64_t sample){
    double x=double(sample-v.start)/(v.end-v.start);
    if(!v.source->cycle||v.releasing)return controller::clamp(x);
    x-=std::floor(x);return v.source->cycle==2?1-std::abs(2*x-1):x;
  }
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
    for(const auto &v:voices)if(v.source)report(v.source->id.c_str(),phase(v,sample));
  }
  void block(unsigned frames){blockFrames=frames;}
  void physical(unsigned ch,unsigned cc,unsigned value,uint64_t sample=0){
    if(ch>=16||cc>=128||value>127)return;
    last[ch*128+cc]=int(value);physicalAt[ch*128+cc]=sample;
    for(auto &v:voices)if(v.source&&v.source->cc&&v.source->channel==ch&&v.source->number==cc)cancel(v);
  }
  template<class Resolve>
  bool start(unsigned index,uint64_t sample,Resolve resolve,unsigned owner=UINT32_MAX,uint64_t gesture=0,double charge=-1){
    if(index>=plan.definitions.size()){++rejected;return false;}
    auto &d=plan.definitions[index];uint32_t id=0;
    const double amplitude=charge>=0&&d.chargeAmplitude.enabled?controller::clamp(d.chargeAmplitude.value(charge)):1;
    const double constant=charge>=0&&d.chargeValue.enabled?controller::clamp(d.chargeValue.value(charge)):-1;
    const double initial=constant>=0?constant:controller::clamp(d.restValue+(d.points->front().y-d.restValue)*amplitude);double effective=initial;
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
    const double duration=charge>=0&&d.chargeDuration.enabled?std::max(.001,std::min(86400.,d.chargeDuration.value(charge))):d.duration;
    const double samples=duration*sampleRate;
    if(!std::isfinite(samples)||samples<1||samples>double(9007199254740991ULL-sample)){++rejected;return false;}
    auto existing=host.target(id);if(existing)effective=existing->effective;
    if(!existing&&!host.stagePerformanceTarget(id,effective)){++rejected;return false;}
    Voice *slot=nullptr;for(auto &v:voices)if(v.source&&v.target==id){slot=&v;break;}
    if(!slot)for(auto &v:voices)if(!v.source){slot=&v;break;}
    if(!slot){++rejected;return false;}
    // Acquire once, respecting physical priority. Losing tokens never reacquire.
    auto token=host.acquirePerformanceTarget(id,d.soft?effective:initial);
    if(!token){++rejected;return false;}
    if(slot->source){*slot=Voice{};--active;}
    slot->source=&d;slot->target=id;slot->token=token;slot->start=slot->next=sample;slot->end=sample+uint64_t(std::ceil(samples));slot->from=effective;slot->constant=constant;slot->amplitude=amplitude;slot->owner=owner;slot->gesture=gesture;++active;return true;
  }
  void release(unsigned owner,uint64_t gesture,uint64_t sample,bool all=false){
    for(auto &v:voices)if(v.source&&v.source->gated&&!v.releasing&&v.owner==owner&&(all||v.gesture==gesture)){
      auto t=host.target(v.target);
      if(!t||t->owner!=UINT32_MAX||t->token!=v.token){cancel(v);continue;}
      v.from=t->effective;v.releasing=true;v.start=v.next=sample;v.tick=0;v.initial=true;
      v.end=sample+std::max<uint64_t>(1,uint64_t(std::ceil(v.source->releaseSeconds*sampleRate)));
    }
  }
  void releasePreview(unsigned index,uint64_t sample){if(index>=plan.definitions.size())return;for(auto &v:voices)if(v.source&&v.source->id==plan.definitions[index].id&&v.owner==UINT32_MAX)release(UINT32_MAX,v.gesture,sample);}
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
        double x=phase(v,until);double goal=v.constant>=0?v.constant:controller::clamp(d.restValue+(d.value(x)-d.restValue)*v.amplitude);
        double value=v.releasing?v.from+(d.restValue-v.from)*x:d.soft?controller::glide(v.from,goal,double(until-v.start)/sampleRate,std::min(d.glide,double(v.end-v.start)/sampleRate)):goal;
        if(!host.updatePerformanceTarget(v.target,v.token,value)||!apply(d.binding,value)){cancel(v);continue;}
        if(until>=v.end&&(!d.gated||v.releasing)&&(!d.cycle||v.releasing))cancel(v);continue;
      }
      while(v.source&&v.next<until){
        if(!budget--){++rejected;panic();return;}
        auto sample=v.next;double x=phase(v,sample),goal=v.constant>=0?v.constant:controller::clamp(d.restValue+(d.value(x)-d.restValue)*v.amplitude);
        double value=v.releasing?v.from+(d.restValue-v.from)*x:d.soft?controller::glide(v.from,goal,double(sample-v.start)/sampleRate,std::min(d.glide,double(v.end-v.start)/sampleRate)):goal;
        if(sample==v.end&&(!d.cycle||v.releasing))value=v.releasing?d.restValue:controller::clamp(d.restValue+(d.points->back().y-d.restValue)*v.amplitude);
        if(!host.updatePerformanceTarget(v.target,v.token,value)){cancel(v);break;}
        unsigned rounded=unsigned(std::floor(controller::clamp(value)*127+.5)),key=d.channel*128+d.number;
        if(v.initial||last[key]!=int(rounded)){
          if(!emit(sample,d.channel,d.number,rounded)){++rejected;panic();return;}
          last[key]=rounded;++emitted;
        }
        v.initial=false;
        if(sample==v.end&&(!d.cycle||v.releasing)){if(d.gated&&!v.releasing)v.next=UINT64_MAX;else cancel(v);break;}
        ++v.tick;v.next=v.start+uint64_t(std::ceil(v.tick*sampleRate/rate));if(!d.cycle||v.releasing)v.next=std::min(v.end,v.next);
      }
    }
  }
};
}
