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
    fields(v,{"type","instrumentId","moduleId","kind"});require(choice(v.at("type"),{"PARAMETER"})&&integer(v.at("instrumentId"),1,16777215)&&integer(v.at("moduleId"),0,16777215)&&integer(v.at("kind"),0,24));
  }
}
inline bool validDocument(const std::vector<unsigned> &bytes){
  try {
    std::string s; s.reserve(bytes.size());for(auto c:bytes)s+=char(c);
    Parser p(s);auto root=p.value();require(p.pos==s.size());require(integer(root.at("version"),1,3));
    bool groupVersion=root.at("version").number==3;
    bool movementVersion=root.at("version").number>=2;
    if(movementVersion)fields(root,{"version","sources","switches","movements","ccRate"});
    else fields(root,{"version","sources","switches"});
    std::set<std::string> ids,sources,movements;std::set<unsigned> slots,switchIds;
    auto unique=[&](const Value &v){require(ids.insert(uuid(v)).second);};
    const auto &src=root.at("sources");require(src.type=='a');
    for(const auto &v:src.array){if(groupVersion){fields(v,{"id","type","slot","muteGroup"});require(integer(v.at("muteGroup"),0,16777215));}else fields(v,{"id","type","slot"});unique(v.at("id"));require(choice(v.at("type"),{"PHRASE"})&&integer(v.at("slot"),1,16)&&slots.insert(unsigned(v.at("slot").number)).second);sources.insert(uuid(v.at("id")));}
    if(movementVersion){
      const auto &rate=root.at("ccRate");require(integer(rate,10,100)&&(rate.number==10||rate.number==25||rate.number==50||rate.number==100));
      const auto &library=root.at("movements");require(library.type=='a');
      for(const auto &m:library.array){
        fields(m,{"id","name","target","points","duration","interpolation","retrigger","glideSeconds"});unique(m.at("id"));movements.insert(uuid(m.at("id")));
        require(m.at("name").type=='s'&&!m.at("name").text.empty());destination(m.at("target"));
        require(m.at("duration").type=='n'&&m.at("duration").number>0&&m.at("glideSeconds").type=='n'&&m.at("glideSeconds").number>0&&m.at("glideSeconds").number<=60);
        require(choice(m.at("interpolation"),{"LINEAR","HOLD"})&&choice(m.at("retrigger"),{"SOFT_RESTART","DIRECT"}));
        const auto &points=m.at("points");require(points.type=='a'&&points.array.size()>=2);double previous=-1;
        for(const auto &point:points.array){require(point.type=='a'&&point.array.size()==2);const auto &x=point.array[0],&y=point.array[1];require(x.type=='n'&&y.type=='n'&&x.number>previous&&x.number>=0&&x.number<=1&&y.number>=0&&y.number<=1);previous=x.number;}
        require(points.array.front().array[0].number==0&&points.array.back().array[0].number==1);
      }
    }
    const auto &switches=root.at("switches");require(switches.type=='a');
    for(const auto &sw:switches.array){
      fields(sw,{"switchId","traversal","transition","gesture","steps"});require(integer(sw.at("switchId"),1,16777215)&&switchIds.insert(unsigned(sw.at("switchId").number)).second);
      require(choice(sw.at("traversal"),{"SEQUENTIAL","BACKWARD","PING_PONG","RANDOM","SHUFFLE_BAG"})&&choice(sw.at("transition"),{"IMMEDIATE","END_OF_PHRASE"})&&choice(sw.at("gesture"),{"INSTANT","EXCLUSIVE"}));
      const auto &steps=sw.at("steps");require(steps.type=='a'&&!steps.array.empty());
      for(const auto &step:steps.array){
        fields(step,{"id","transition","layers"});unique(step.at("id"));require(choice(step.at("transition"),{"INHERIT","IMMEDIATE","END_OF_PHRASE"}));
        const auto &layers=step.at("layers");require(layers.type=='a'&&!layers.array.empty());
        for(unsigned i=0;i<layers.array.size();++i){
          const auto &layer=layers.array[i];fields(layer,{"id","block"});unique(layer.at("id"));const auto &b=layer.at("block");if(b.type=='z')continue;
          if(choice(b.at("type"),{"ACTION"})){
            fields(b,{"id","type","action","target","trigger"});unique(b.at("id"));require(i>0&&choice(b.at("action"),{"STOP","PAUSE","RESUME","RESET_CURSOR","RESET_SHUFFLE_BAG","STOP_RESET"})&&choice(b.at("trigger"),{"PRESS","HOLD"}));
            const auto &t=b.at("target");
            if(choice(t.at("type"),{"PHRASE"})){fields(t,{"type","sourceId"});uuid(t.at("sourceId"));}
            else if(choice(t.at("type"),{"MUTE_GROUP"})){fields(t,{"type","id"});require(integer(t.at("id"),1,16777215));}
            else if(choice(t.at("type"),{"ALL_PHRASES"})){fields(t,{"type"});}
            else {fields(t,{"type","switchId"});require(choice(t.at("type"),{"SWITCH"})&&integer(t.at("switchId"),1,16777215));}
            if(choice(b.at("action"),{"RESET_CURSOR","RESET_SHUFFLE_BAG"}))require(choice(t.at("type"),{"SWITCH"}));
            if(choice(b.at("action"),{"STOP","PAUSE","RESUME"}))require(!choice(t.at("type"),{"SWITCH"}));
            continue;
          }
          fields(b,{"id","type","sourceId","overrides"});unique(b.at("id"));auto source=uuid(b.at("sourceId"));
          bool phrase=choice(b.at("type"),{"PHRASE"});require((phrase||choice(b.at("type"),{"MOVEMENT"}))&&(i>0||phrase)&&(!sources.count(source)||phrase)&&(!movements.count(source)||!phrase));
          const auto &overrides=b.at("overrides");require(overrides.type=='o');
          for(const auto &entry:overrides.object){
            const auto &key=entry.first;const auto &local=entry.second;
            std::map<std::string,std::vector<std::string>> opts={
              {"playMode",{"LOOP","ONCE","HOLD"}},{"trigger",{"PRESS","HOLD"}},
              {"instancePolicy",{"JOIN_EXISTING","RESTART","NEW_INSTANCE"}},
              {"join",{"TRIGGER","JOIN_NOW","JOIN_AT_LOOP_START"}},{"referenceTime",{"CYCLE","ELAPSED"}},
              {"entry",{"TRIGGER","REVEAL"}},{"release",{"LATCH","GATE"}},
              {"movementPlayMode",{"ONE_SHOT","GATED"}},{"retrigger",{"SOFT_RESTART","DIRECT"}}};
            bool parameter=key=="phrase_time_decay"||key=="phrase_velocity_decay"||key=="phrase_base_velocity";
            require(opts.count(key)||key=="destination"||parameter);
            bool onlyPhrase=key=="playMode"||key=="instancePolicy"||key=="entry"||key=="release"||parameter;
            bool onlyMovement=key=="movementPlayMode"||key=="retrigger"||key=="destination";
            require(!(onlyPhrase&&!phrase)&&!(onlyMovement&&phrase));
            if(choice(local.at("mode"),{"INHERIT"})){fields(local,{"mode"});continue;}
            fields(local,{"mode","value"});require(choice(local.at("mode"),{"OVERRIDE"}));auto &v=local.at("value");
            if(key=="destination")destination(v);
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
