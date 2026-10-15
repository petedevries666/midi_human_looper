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
inline bool onHold(const Value& b) {
  auto it=b.at("overrides").object.find("trigger");
  return it!=b.at("overrides").object.end() && choice(it->second.at("mode"),{"OVERRIDE"}) && choice(it->second.at("value"),{"HOLD"});
}
inline bool revealBlock(const Value& b) {
  auto it=b.at("overrides").object.find("entry");
  return it!=b.at("overrides").object.end() && choice(it->second.at("mode"),{"OVERRIDE"}) && choice(it->second.at("value"),{"REVEAL"});
}
inline bool gatedBlock(const Value& b) {
  auto it=b.at("overrides").object.find("release");
  return it!=b.at("overrides").object.end() && choice(it->second.at("mode"),{"OVERRIDE"}) && choice(it->second.at("value"),{"GATE"});
}
inline bool supportedBlock(const Value& b) {
  if(!choice(b.at("type"),{"PHRASE"}) || (revealBlock(b)&&!onHold(b)) || (gatedBlock(b)&&!revealBlock(b)))return false;
  for(const auto& item:b.at("overrides").object) {
    if(choice(item.second.at("mode"),{"INHERIT"}))continue;
    const auto& k=item.first;const auto& v=item.second.at("value");
    if(k=="playMode" || k=="phrase_base_velocity" || k=="phrase_velocity_decay" || k=="phrase_time_decay")continue;
    if(k=="entry" && choice(v,{"TRIGGER","REVEAL"}))continue;
    if(k=="release" && choice(v,{"LATCH","GATE"}))continue;
    if(k=="trigger" && choice(v,{"PRESS","HOLD"}))continue;
    if(k=="instancePolicy" && choice(v,{"NEW_INSTANCE"}))continue;
    if(k=="join" && choice(v,{"TRIGGER"}))continue;
    return false;
  }
  return true;
}
inline std::vector<double> compile(const std::vector<unsigned>& bytes,double base,
                                  const std::array<unsigned,16>& owners,
                                  const std::map<std::string,unsigned>& movements = {}) {
  std::vector<double> out(16*8,0);
  if(bytes.empty())return out;
  auto root=document(bytes);std::map<std::string,unsigned> slots;
  std::array<unsigned,16> groups{};
  for(const auto& s:root.at("sources").array)if(s.object.count("muteGroup"))groups[unsigned(s.at("slot").number)-1]=unsigned(s.at("muteGroup").number);
  for(const auto& s:root.at("sources").array)slots[s.at("id").text]=unsigned(s.at("slot").number)-1;
  for(const auto& sw:root.at("switches").array) {
    unsigned si=16;for(unsigned j=0;j<16;++j)if(owners[j]==sw.at("switchId").number)si=j;
    if(si==16)continue;unsigned h=si*8;
    out[h]=owners[si];out[h+1]=sw.at("steps").array.size();out[h+2]=base+out.size();out[h+3]=-1;
    out[h+7]=choice(sw.at("traversal"),{"SEQUENTIAL"})&&choice(sw.at("transition"),{"IMMEDIATE"})&&choice(sw.at("gesture"),{"INSTANT"});
    unsigned stepStart=out.size();out.resize(out.size()+sw.at("steps").array.size()*72,0);unsigned stepIndex=0;
    for(const auto& step:sw.at("steps").array) {
      std::array<double,72> record{};std::vector<double> admissions,heldAdmissions;
      record[0]=choice(step.at("transition"),{"INHERIT","IMMEDIATE"});
      unsigned n=0;
      std::map<unsigned,unsigned> winners;
      for(const auto& layer:step.at("layers").array){
        const auto& b=layer.at("block");if(b.type=='z'||!choice(b.at("type"),{"PHRASE"})||!supportedBlock(b))continue;
        auto source=slots.find(b.at("sourceId").text);if(source==slots.end())continue;
        unsigned slot=source->second,g=groups[slot];if(g && (!winners.count(g)||slot<winners[g]))winners[g]=slot;
      }
      for(const auto& layer:step.at("layers").array) {
        const auto& b=layer.at("block");if(b.type=='z')continue;
        if(choice(b.at("type"),{"MOVEMENT"})){
          auto it=movements.find(b.at("id").text);
          if(it==movements.end()){
            bool exists=false;if(root.object.count("movements"))for(const auto &m:root.at("movements").array)exists|=m.at("id").text==b.at("sourceId").text;
            if(exists)record[0]=0;else ++record[1];
          }else (onHold(b)?heldAdmissions:admissions).push_back(it->second);
          continue;
        }
        if(!supportedBlock(b)){record[0]=0;continue;}
        auto it=slots.find(b.at("sourceId").text);
        if(it==slots.end()){++record[1];continue;}
        if(groups[it->second] && winners[groups[it->second]]!=it->second)continue;
        if(n>=12){record[0]=0;record[3]=2;continue;}
        if(onHold(b))record[66]+=1u<<n;
        if(revealBlock(b))record[68]+=1u<<n;
        if(gatedBlock(b))record[69]+=1u<<n;
        unsigned row=4+n*5;record[row]=it->second;record[row+1]=-1;
        auto mode=b.at("overrides").object.find("playMode");
        if(mode!=b.at("overrides").object.end() && choice(mode->second.at("mode"),{"OVERRIDE"}))
          record[row+1]=choice(mode->second.at("value"),{"LOOP"})?0:choice(mode->second.at("value"),{"ONCE"})?1:2;
        record[row+2]=localNumber(b,"phrase_base_velocity");record[row+3]=localNumber(b,"phrase_velocity_decay");record[row+4]=localNumber(b,"phrase_time_decay");++n;
      }
      record[2]=n;record[64]=admissions.size();record[65]=base+out.size();record[67]=heldAdmissions.size();
      admissions.insert(admissions.end(),heldAdmissions.begin(),heldAdmissions.end());
      std::copy(record.begin(),record.end(),out.begin()+stepStart+stepIndex++*72);out.insert(out.end(),admissions.begin(),admissions.end());
    }
  }
  return out;
}
}
