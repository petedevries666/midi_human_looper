#pragma once
#include "conductor_document.hpp"
// Resolve/compile outside processing. Runtime records contain no UUID/JSON.
// One STEP can admit at most the existing 12 voices, not a new Q3 storage limit.
namespace conductor {
inline Value document(const std::vector<unsigned>& bytes) {
  std::string text;for(auto c:bytes)text+=char(c);Parser p(text);return p.value();
}
inline double localNumber(const Value& b,const char* key) {
  const auto& o=b.at("overrides").object;auto it=o.find(key);
  return it==o.end() || choice(it->second.at("mode"),{"INHERIT"})?-1:it->second.at("value").number;
}
inline bool supportedBlock(const Value& b) {
  if(!choice(b.at("type"),{"PHRASE"}))return false;
  for(const auto& item:b.at("overrides").object) {
    if(choice(item.second.at("mode"),{"INHERIT"}))continue;
    const auto& k=item.first;const auto& v=item.second.at("value");
    if(k=="playMode" || k=="phrase_base_velocity" || k=="phrase_velocity_decay" || k=="phrase_time_decay")continue;
    if(k=="trigger" && choice(v,{"PRESS"}))continue;
    if(k=="instancePolicy" && choice(v,{"NEW_INSTANCE"}))continue;
    if(k=="join" && choice(v,{"TRIGGER"}))continue;
    return false;
  }
  return true;
}
inline std::vector<double> compile(const std::vector<unsigned>& bytes,double base,
                                  const std::array<unsigned,16>& owners) {
  std::vector<double> out(16*8,0);
  if(bytes.empty())return out;
  auto root=document(bytes);std::map<std::string,unsigned> slots;
  for(const auto& s:root.at("sources").array)slots[s.at("id").text]=unsigned(s.at("slot").number)-1;
  for(const auto& sw:root.at("switches").array) {
    unsigned si=16;for(unsigned j=0;j<16;++j)if(owners[j]==sw.at("switchId").number)si=j;
    if(si==16)continue;unsigned h=si*8;
    out[h]=owners[si];out[h+1]=sw.at("steps").array.size();out[h+2]=base+out.size();out[h+3]=-1;
    out[h+7]=choice(sw.at("traversal"),{"SEQUENTIAL"})&&choice(sw.at("transition"),{"IMMEDIATE"})&&choice(sw.at("gesture"),{"INSTANT"});
    for(const auto& step:sw.at("steps").array) {
      std::array<double,64> record{};
      record[0]=choice(step.at("transition"),{"INHERIT","IMMEDIATE"});
      unsigned n=0;
      for(const auto& layer:step.at("layers").array) {
        const auto& b=layer.at("block");if(b.type=='z')continue;
        if(!supportedBlock(b)){record[0]=0;continue;}
        auto it=slots.find(b.at("sourceId").text);
        if(it==slots.end()){++record[1];continue;}
        if(n>=12){record[0]=0;record[3]=2;continue;}
        unsigned row=4+n*5;record[row]=it->second;record[row+1]=-1;
        auto mode=b.at("overrides").object.find("playMode");
        if(mode!=b.at("overrides").object.end() && choice(mode->second.at("mode"),{"OVERRIDE"}))
          record[row+1]=choice(mode->second.at("value"),{"LOOP"})?0:choice(mode->second.at("value"),{"ONCE"})?1:2;
        record[row+2]=localNumber(b,"phrase_base_velocity");record[row+3]=localNumber(b,"phrase_velocity_decay");record[row+4]=localNumber(b,"phrase_time_decay");++n;
      }
      record[2]=n;out.insert(out.end(),record.begin(),record.end());
    }
  }
  return out;
}
}
