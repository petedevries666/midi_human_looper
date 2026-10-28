#pragma once
// Typed validation for the internal canonical configuration carrier, exclusively
// on the control worker. No JSON parsing/allocation occurs in the JACK callback.
#include "parameter_registry.hpp"
#include <algorithm>
#include <map>
#include <set>
#include <vector>
#include <string>
#include <cstdlib>
#include <cmath>
#include <stdexcept>
#include <initializer_list>
namespace conductor {
struct Value {
  char type=0;
  std::string text;
  double number=0;
  std::map<std::string,Value> object;
  std::vector<Value> array;
  const Value &at(const char *key) const {return object.at(key);}
};
struct Parser {
  const std::string &s; size_t pos=0;
  explicit Parser(const std::string &s):s(s){}
  void need(bool ok) {if(!ok) throw std::runtime_error("invalid CONDUCTOR");}
  char take(){need(pos<s.size());return s[pos++];}
  std::string string(){
    need(take()=='"');std::string v;
    while(pos<s.size() && s[pos]!='"') {
      char c=take();need(c>=32 && c<=126 && c!='\\');v+=c;
    }
    need(take()=='"');return v;
  }
  Value value(unsigned depth=0){
    need(depth<32 && pos<s.size());Value v;char c=s[pos];
    if(c=='{') {
      ++pos;v.type='o';
      if(pos<s.size() && s[pos]=='}'){++pos;return v;}
      for(;;){auto k=string();need(take()==':');need(!v.object.count(k));v.object.emplace(k,value(depth+1));c=take();if(c=='}')break;need(c==',');}
    } else if(c=='[') {
      ++pos;v.type='a';
      if(pos<s.size() && s[pos]==']'){++pos;return v;}
      for(;;){v.array.push_back(value(depth+1));c=take();if(c==']')break;need(c==',');}
    } else if(c=='"') {v.type='s';v.text=string();}
    else if(s.compare(pos,4,"null")==0){v.type='z';pos+=4;}
    else {
      v.type='n';size_t start=pos;
      if(s[pos]=='-')++pos;
      need(pos<s.size() && s[pos]>='0' && s[pos]<='9');
      if(s[pos]=='0')++pos;else while(pos<s.size() && s[pos]>='0' && s[pos]<='9')++pos;
      if(pos<s.size() && s[pos]=='.'){++pos;size_t first=pos;while(pos<s.size() && s[pos]>='0' && s[pos]<='9')++pos;need(pos>first);}
      if(pos<s.size() && (s[pos]=='e'||s[pos]=='E')){++pos;if(pos<s.size() && (s[pos]=='-'||s[pos]=='+'))++pos;size_t first=pos;while(pos<s.size() && s[pos]>='0' && s[pos]<='9')++pos;need(pos>first);}
      v.text=s.substr(start,pos-start);v.number=std::strtod(v.text.c_str(),nullptr);need(std::isfinite(v.number));
    }
    return v;
  }
};
inline void require(bool ok){if(!ok)throw std::runtime_error("invalid CONDUCTOR document");}
inline void fields(const Value &v,std::initializer_list<const char*> names){
  require(v.type=='o' && v.object.size()==names.size());for(auto key:names)require(v.object.count(key));
}
inline void fieldsOptional(const Value &v,std::initializer_list<const char*> required,std::initializer_list<const char*> optional){
  require(v.type=='o');for(auto key:required)require(v.object.count(key));
  for(const auto &item:v.object){bool known=false;for(auto key:required)known|=item.first==key;for(auto key:optional)known|=item.first==key;require(known);}
}
inline bool choice(const Value &v,std::initializer_list<const char*> names){
  if(v.type!='s')return false;for(auto n:names)if(v.text==n)return true;return false;
}
inline bool integer(const Value &v,double lo,double hi){return v.type=='n' && v.text.find_first_of(".eE")==std::string::npos && v.number>=lo && v.number<=hi && std::floor(v.number)==v.number;}
inline std::string uuid(const Value &v){
  require(v.type=='s' && v.text.size()==36);
  for(unsigned i=0;i<36;++i) {char c=v.text[i];require((i==8||i==13||i==18||i==23)?c=='-':((c>='0'&&c<='9')||(c>='a'&&c<='f')));}
  return v.text;
}
inline void destination(const Value &v){
  if(choice(v.at("type"),{"CC"})) {fields(v,{"type","channel","number"});require(integer(v.at("channel"),1,16)&&integer(v.at("number"),0,127));}
  else {
    fields(v,{"type","instrumentId","moduleId","kind"});require(choice(v.at("type"),{"PARAMETER"})&&integer(v.at("instrumentId"),1,16777215)&&integer(v.at("moduleId"),0,16777215)&&integer(v.at("kind"),0,26));
  }
}
inline bool validDocument(const std::vector<unsigned> &bytes){
  try {
    std::string s; s.reserve(bytes.size());for(auto c:bytes)s+=char(c);
    Parser p(s);auto root=p.value();require(p.pos==s.size());require(integer(root.at("version"),1,3));
    bool groupVersion=root.at("version").number==3;
    bool movementVersion=root.at("version").number>=2;
    if(movementVersion)fieldsOptional(root,{"version","sources","switches","movements","ccRate"},{"supercharge"});
    else fieldsOptional(root,{"version","sources","switches"},{"supercharge"});
    double chargeThreshold=600,chargeFull=2000;
    if(root.object.count("supercharge")){const auto &c=root.at("supercharge");fields(c,{"thresholdMs","fullMs"});require(integer(c.at("thresholdMs"),0,30000)&&integer(c.at("fullMs"),1,120000)&&c.at("fullMs").number>=c.at("thresholdMs").number);chargeThreshold=c.at("thresholdMs").number;chargeFull=c.at("fullMs").number;}
    std::set<std::string> ids,sources,movements;std::set<unsigned> slots,switchIds;
    auto unique=[&](const Value &v){require(ids.insert(uuid(v)).second);};
    const auto &src=root.at("sources");require(src.type=='a');
    for(const auto &v:src.array){if(groupVersion){fieldsOptional(v,{"id","type","slot","muteGroup"},{"tune","rate"});require(integer(v.at("muteGroup"),0,16777215));}else fieldsOptional(v,{"id","type","slot"},{"tune","rate"});if(v.object.count("tune"))require(integer(v.at("tune"),-24,24));if(v.object.count("rate"))require(v.at("rate").type=='n'&&v.at("rate").number>=.1&&v.at("rate").number<=16);unique(v.at("id"));require(choice(v.at("type"),{"PHRASE"})&&integer(v.at("slot"),1,128)&&slots.insert(unsigned(v.at("slot").number)).second);sources.insert(uuid(v.at("id")));}
    if(movementVersion){
      const auto &rate=root.at("ccRate");require(integer(rate,10,100)&&(rate.number==10||rate.number==25||rate.number==50||rate.number==100));
      const auto &library=root.at("movements");require(library.type=='a');
      for(const auto &m:library.array){
        if(m.object.count("playMode")||m.object.count("releaseSeconds")||m.object.count("restValue")){
          fieldsOptional(m,{"id","name","target","points","duration","interpolation","retrigger","glideSeconds","playMode","releaseSeconds","restValue"},{"cycleMode"});
          require(choice(m.at("playMode"),{"ONE_SHOT","GATED"}));
          require(m.at("releaseSeconds").type=='n'&&m.at("releaseSeconds").number>=0&&m.at("releaseSeconds").number<=60&&m.at("restValue").type=='n'&&m.at("restValue").number>=0&&m.at("restValue").number<=1);
        }else fieldsOptional(m,{"id","name","target","points","duration","interpolation","retrigger","glideSeconds"},{"cycleMode"});if(m.object.count("cycleMode"))require(choice(m.at("cycleMode"),{"ONCE","LOOP","PING_PONG"}));unique(m.at("id"));movements.insert(uuid(m.at("id")));
        require(m.at("name").type=='s'&&!m.at("name").text.empty());destination(m.at("target"));
        require(m.at("duration").type=='n'&&m.at("duration").number>0&&m.at("glideSeconds").type=='n'&&m.at("glideSeconds").number>0&&m.at("glideSeconds").number<=60);
        require(choice(m.at("interpolation"),{"LINEAR","HOLD"})&&choice(m.at("retrigger"),{"SOFT_RESTART","DIRECT"}));
        const auto &points=m.at("points");require(points.type=='a'&&points.array.size()>=2);double previous=-1;
        for(const auto &point:points.array){require(point.type=='a'&&(point.array.size()==2||point.array.size()==3));const auto &x=point.array[0],&y=point.array[1];require(x.type=='n'&&y.type=='n'&&x.number>previous&&x.number>=0&&x.number<=1&&y.number>=0&&y.number<=1);if(point.array.size()==3){const auto &bend=point.array[2];require(bend.type=='n'&&bend.number>=-.98&&bend.number<=.98);}previous=x.number;}
        require(points.array.front().array[0].number==0&&points.array.back().array[0].number==1);
      }
    }
    const auto &switches=root.at("switches");require(switches.type=='a');
    for(const auto &sw:switches.array){
      fieldsOptional(sw,{"switchId","traversal","transition","gesture","steps"},{"advance"});if(sw.object.count("advance"))require(choice(sw.at("advance"),{"PRESS","RELEASE"}));require(integer(sw.at("switchId"),1,16777215)&&switchIds.insert(unsigned(sw.at("switchId").number)).second);
      require(choice(sw.at("traversal"),{"SEQUENTIAL","BACKWARD","PING_PONG","RANDOM","SHUFFLE_BAG"})&&choice(sw.at("transition"),{"IMMEDIATE","END_OF_PHRASE"})&&choice(sw.at("gesture"),{"INSTANT","EXCLUSIVE"}));
      const auto &steps=sw.at("steps");require(steps.type=='a'&&!steps.array.empty());
      for(const auto &step:steps.array){
        fieldsOptional(step,{"id","transition","layers"},{"supercharge","repeat"});if(step.object.count("repeat"))require(integer(step.at("repeat"),1,999));unique(step.at("id"));require(choice(step.at("transition"),{"INHERIT","IMMEDIATE","END_OF_PHRASE"}));
        const auto &layers=step.at("layers");require(layers.type=='a'&&!layers.array.empty());
        if(step.object.count("supercharge")){
          const auto &c=step.at("supercharge");fieldsOptional(c,{"bindings"},{"thresholdMs","fullMs"});double threshold=c.object.count("thresholdMs")?c.at("thresholdMs").number:chargeThreshold,full=c.object.count("fullMs")?c.at("fullMs").number:chargeFull;require((!c.object.count("thresholdMs")||integer(c.at("thresholdMs"),0,30000))&&(!c.object.count("fullMs")||integer(c.at("fullMs"),1,120000))&&full>=threshold&&c.at("bindings").type=='a');
          std::set<std::pair<std::string,std::string>> seen;
          for(const auto &v:c.at("bindings").array){
            if(v.object.count("target")){
              fields(v,{"target","parameter","from","to","factor"});destination(v.at("target"));require(choice(v.at("target").at("type"),{"PARAMETER"})&&choice(v.at("parameter"),{"parameter"}));unsigned kind=v.at("target").at("kind").number;require(kind!=16&&kind<28);require(seen.insert({"target",std::to_string(unsigned(v.at("target").at("instrumentId").number))+":"+std::to_string(unsigned(v.at("target").at("moduleId").number))+":"+std::to_string(kind)}).second);const auto &d=performance::parameters[kind];require(v.at("from").type=='n'&&v.at("from").number>=d.low&&v.at("from").number<=d.high&&v.at("to").type=='n'&&v.at("to").number>=d.low&&v.at("to").number<=d.high&&v.at("factor").type=='n'&&v.at("factor").number>=0&&v.at("factor").number<=16);continue;
            }
            fields(v,{"blockId","parameter","from","to","factor"});auto id=uuid(v.at("blockId"));require(v.at("parameter").type=='s');auto key=v.at("parameter").text;
            const Value *b=nullptr;for(const auto &l:layers.array)if(l.at("block").type=='o'&&l.at("block").at("id").text==id)b=&l.at("block");require(b&&seen.insert({id,key}).second);
            bool mov=choice(b->at("type"),{"MOVEMENT"});unsigned kind=key=="phrase_time_decay"?14:key=="phrase_velocity_decay"?15:key=="phrase_base_velocity"?17:0;
            require(mov?(key=="movementDuration"||key=="movementAmplitude"):kind>0);
            double low=mov?(key=="movementDuration"?.001:0):performance::parameters[kind].low,high=mov?(key=="movementDuration"?86400:1):performance::parameters[kind].high;
            require(v.at("from").type=='n'&&v.at("to").type=='n'&&v.at("from").number>=low&&v.at("from").number<=high&&v.at("to").number>=low&&v.at("to").number<=high&&v.at("factor").type=='n'&&v.at("factor").number>=0&&v.at("factor").number<=16);
          }
        }
        for(unsigned i=0;i<layers.array.size();++i){
          const auto &layer=layers.array[i];fields(layer,{"id","block"});unique(layer.at("id"));const auto &b=layer.at("block");if(b.type=='z')continue;
          if(choice(b.at("type"),{"ACTION"})){
            fields(b,{"id","type","action","target","trigger"});unique(b.at("id"));require(i>0&&choice(b.at("action"),{"STOP","PAUSE","RESUME","RESET_CURSOR","RESET_SHUFFLE_BAG","STOP_RESET","PANIC"})&&choice(b.at("trigger"),{"PRESS","HOLD","LONG_HOLD","RELEASE","SUPERCHARGE_RELEASE"}));
            const auto &t=b.at("target");
            if(choice(t.at("type"),{"PHRASE"})){fields(t,{"type","sourceId"});uuid(t.at("sourceId"));}
            else if(choice(t.at("type"),{"MUTE_GROUP"})){fields(t,{"type","id"});require(integer(t.at("id"),1,16777215));}
            else if(choice(t.at("type"),{"ALL_PHRASES"})){fields(t,{"type"});}
            else {fields(t,{"type","switchId"});require(choice(t.at("type"),{"SWITCH"})&&integer(t.at("switchId"),1,16777215));}
            if(choice(b.at("action"),{"RESET_CURSOR","RESET_SHUFFLE_BAG"}))require(choice(t.at("type"),{"SWITCH"}));
            if(choice(b.at("action"),{"STOP","PAUSE","RESUME"}))require(!choice(t.at("type"),{"SWITCH"}));
            if(choice(b.at("action"),{"PANIC"}))require(choice(t.at("type"),{"ALL_PHRASES"}));
            continue;
          }
          fields(b,{"id","type","sourceId","overrides"});unique(b.at("id"));auto source=uuid(b.at("sourceId"));
          bool phrase=choice(b.at("type"),{"PHRASE"});require((phrase||choice(b.at("type"),{"MOVEMENT"}))&&(i>0||phrase)&&(!sources.count(source)||phrase)&&(!movements.count(source)||!phrase));
          const auto &overrides=b.at("overrides");require(overrides.type=='o');
          for(const auto &entry:overrides.object){
            const auto &key=entry.first;const auto &local=entry.second;
            std::map<std::string,std::vector<std::string>> opts={
              {"playMode",{"LOOP","ONCE","HOLD"}},{"trigger",{"PRESS","HOLD","LONG_HOLD","RELEASE","SUPERCHARGE_RELEASE"}},
              {"instancePolicy",{"JOIN_EXISTING","RESTART","NEW_INSTANCE"}},
              {"join",{"TRIGGER","JOIN_NOW","JOIN_AT_LOOP_START"}},{"referenceTime",{"CYCLE","ELAPSED"}},
              {"entry",{"TRIGGER","REVEAL"}},{"release",{"LATCH","GATE"}},
              {"movementCycle",{"ONCE","LOOP","PING_PONG"}},{"movementPlayMode",{"ONE_SHOT","GATED"}},{"retrigger",{"SOFT_RESTART","DIRECT"}}};
            bool tune=key=="phrase_tune",rate=key=="phrase_rate";bool parameter=tune||rate||key=="phrase_time_decay"||key=="phrase_velocity_decay"||key=="phrase_base_velocity";
            bool revealNumber=key=="revealCC"||key=="revealFadeSeconds";
            bool movementNumber=key=="releaseSeconds"||key=="restValue"||key=="movementDuration";
            require(opts.count(key)||key=="destination"||parameter||movementNumber||revealNumber);
            bool onlyPhrase=key=="playMode"||key=="instancePolicy"||key=="entry"||key=="release"||parameter||revealNumber;
            bool onlyMovement=key=="movementCycle"||key=="movementPlayMode"||key=="retrigger"||key=="destination"||movementNumber;
            require(!(onlyPhrase&&!phrase)&&!(onlyMovement&&phrase));
            if(choice(local.at("mode"),{"INHERIT"})){fields(local,{"mode"});continue;}
            fields(local,{"mode","value"});require(choice(local.at("mode"),{"OVERRIDE"}));auto &v=local.at("value");
            if(revealNumber)require(key=="revealCC"?(integer(v,0,119)&&v.number!=64):(v.type=='n'&&v.number>=0&&v.number<=60));
            else if(movementNumber)require(v.type=='n'&&v.number>=(key=="movementDuration"?.001:0)&&v.number<=(key=="movementDuration"?86400:key=="releaseSeconds"?60:1));
            else if(key=="destination")destination(v);
            else if(tune)require(integer(v,-24,24));
            else if(rate)require(v.type=='n'&&v.number>=.1&&v.number<=16);
            else if(parameter){unsigned kind=key=="phrase_time_decay"?14:key=="phrase_velocity_decay"?15:17;const auto &descriptor=performance::parameters[kind];require(v.type=='n'&&v.number>=descriptor.low&&v.number<=descriptor.high);}
            else {require(v.type=='s');auto &allowed=opts.at(key);require(std::find(allowed.begin(),allowed.end(),v.text)!=allowed.end());}
          }
        }
      }
    }
    return true;
  } catch(const std::exception &) {return false;}
}
}
