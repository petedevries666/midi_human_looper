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
inline bool onLongHold(const Value& b){auto it=b.at("overrides").object.find("trigger");return it!=b.at("overrides").object.end()&&choice(it->second.at("mode"),{"OVERRIDE"})&&choice(it->second.at("value"),{"LONG_HOLD"});}
inline bool releaseBlock(const Value& b){auto it=b.at("overrides").object.find("trigger");return it!=b.at("overrides").object.end()&&choice(it->second.at("mode"),{"OVERRIDE"})&&choice(it->second.at("value"),{"RELEASE"});}
inline bool chargeBlock(const Value& b){auto it=b.at("overrides").object.find("trigger");return it!=b.at("overrides").object.end()&&choice(it->second.at("mode"),{"OVERRIDE"})&&choice(it->second.at("value"),{"SUPERCHARGE_RELEASE"});}
inline bool revealBlock(const Value& b) {
  auto it=b.at("overrides").object.find("entry");
  return it!=b.at("overrides").object.end() && choice(it->second.at("mode"),{"OVERRIDE"}) && choice(it->second.at("value"),{"REVEAL"});
}
inline bool gatedBlock(const Value& b) {
  auto it=b.at("overrides").object.find("release");
  return it!=b.at("overrides").object.end() && choice(it->second.at("mode"),{"OVERRIDE"}) && choice(it->second.at("value"),{"GATE"});
}
inline bool supportedBlock(const Value& b) {
  if(!choice(b.at("type"),{"PHRASE"}) || (revealBlock(b)&&!onHold(b)&&!onLongHold(b)&&!releaseBlock(b)&&!chargeBlock(b)) || (gatedBlock(b)&&(!revealBlock(b)||releaseBlock(b)||chargeBlock(b))))return false;
  for(const auto& item:b.at("overrides").object) {
    if(choice(item.second.at("mode"),{"INHERIT"}))continue;
    const auto& k=item.first;const auto& v=item.second.at("value");
    if(k=="phrase_tune" || k=="playMode" || k=="phrase_base_velocity" || k=="phrase_velocity_decay" || k=="phrase_time_decay")continue;
    if(k=="revealCC" || k=="revealFadeSeconds")continue;
    if(k=="entry" && choice(v,{"TRIGGER","REVEAL"}))continue;
    if(k=="release" && choice(v,{"LATCH","GATE"}))continue;
    if(k=="trigger" && choice(v,{"PRESS","HOLD","LONG_HOLD","RELEASE","SUPERCHARGE_RELEASE"}))continue;
    if(k=="instancePolicy" && choice(v,{"NEW_INSTANCE"}))continue;
    if(k=="join" && choice(v,{"TRIGGER"}))continue;
    return false;
  }
  return true;
}
template<std::size_t SwitchCapacity>
inline std::vector<double> compile(const std::vector<unsigned>& bytes,double base,
                                  const std::array<unsigned,SwitchCapacity>& owners,
                                  const std::map<std::string,unsigned>& movements = {}) {
  std::vector<double> out(SwitchCapacity*8,0);
  if(bytes.empty())return out;
  auto root=document(bytes);std::map<std::string,unsigned> slots;
  std::array<unsigned,128> groups{};std::array<double,128> tunes{};
  for(const auto& s:root.at("sources").array)if(s.object.count("tune"))tunes[unsigned(s.at("slot").number)-1]=s.at("tune").number;
  for(const auto& s:root.at("sources").array)if(s.object.count("muteGroup"))groups[unsigned(s.at("slot").number)-1]=unsigned(s.at("muteGroup").number);
  for(const auto& s:root.at("sources").array)slots[s.at("id").text]=unsigned(s.at("slot").number)-1;
  for(const auto& sw:root.at("switches").array) {
    unsigned si=SwitchCapacity;for(unsigned j=0;j<SwitchCapacity;++j)if(owners[j]==sw.at("switchId").number)si=j;
    if(si==SwitchCapacity)continue;unsigned h=si*8;
    out[h]=owners[si];out[h+1]=sw.at("steps").array.size();out[h+2]=base+out.size();out[h+3]=-1;
    out[h+7]=choice(sw.at("traversal"),{"SEQUENTIAL"})&&choice(sw.at("transition"),{"IMMEDIATE","END_OF_PHRASE"})&&choice(sw.at("gesture"),{"INSTANT"});
    if(out[h+7]&&sw.object.count("advance")&&choice(sw.at("advance"),{"RELEASE"}))out[h+7]=2;
    unsigned stepStart=out.size();out.resize(out.size()+sw.at("steps").array.size()*80,0);unsigned stepIndex=0;
    for(const auto& step:sw.at("steps").array) {
      std::array<double,80> record{};std::vector<double> admissions,heldAdmissions,longAdmissions,releaseAdmissions,chargeAdmissions,revealOptions,actions,phraseTunes;unsigned longMask=0;bool chargeAction=false;
      record[0]=choice(step.at("transition"),{"INHERIT","IMMEDIATE","END_OF_PHRASE"});
      record[71]=choice(step.at("transition"),{"END_OF_PHRASE"})||(choice(step.at("transition"),{"INHERIT"})&&choice(sw.at("transition"),{"END_OF_PHRASE"}));
      unsigned n=0;
      std::map<unsigned,unsigned> winners;
      for(const auto& layer:step.at("layers").array){
        const auto& b=layer.at("block");if(b.type=='z'||!choice(b.at("type"),{"PHRASE"})||!supportedBlock(b))continue;
        auto source=slots.find(b.at("sourceId").text);if(source==slots.end())continue;
        unsigned slot=source->second,g=groups[slot];if(g && (!winners.count(g)||slot<winners[g]))winners[g]=slot;
      }
      for(const auto& layer:step.at("layers").array) {
        const auto& b=layer.at("block");if(b.type=='z')continue;
        if(choice(b.at("type"),{"ACTION"})){
          const auto& target=b.at("target");unsigned op=0,kind=0,id=0;
          if(choice(b.at("action"),{"STOP"}))op=1;
          else if(choice(b.at("action"),{"RESET_CURSOR"}))op=3;
          else if(choice(b.at("action"),{"RESET_SHUFFLE_BAG"}))op=4;
          else if(choice(b.at("action"),{"STOP_RESET"}))op=5;
          else if(choice(b.at("action"),{"PANIC"}))op=6;
          if(choice(target.at("type"),{"PHRASE"})){
            auto it=slots.find(target.at("sourceId").text);if(it==slots.end()){record[0]=0;++record[1];continue;}id=it->second;
          }else if(choice(target.at("type"),{"MUTE_GROUP"})){kind=1;id=unsigned(target.at("id").number);}
          else if(choice(target.at("type"),{"ALL_PHRASES"}))kind=2;
          else{kind=3;id=SwitchCapacity;for(unsigned j=0;j<SwitchCapacity;++j)if(owners[j]==target.at("switchId").number)id=j;if(id==SwitchCapacity){record[0]=0;++record[1];continue;}}
          if(!op||(op==5&&kind!=3)||(op==6&&kind!=2)||actions.size()>=128){record[0]=0;continue;}
          const auto &trigger=b.at("trigger");
          unsigned phase=choice(trigger,{"HOLD"})?1:choice(trigger,{"LONG_HOLD"})?2:choice(trigger,{"RELEASE"})?3:choice(trigger,{"SUPERCHARGE_RELEASE"})?4:0;
          if(phase==4)chargeAction=true;
          // Destructive global actions are barriers; self-reset may not leave
          // pending phrase/MOVEMENT admissions in this step.
          bool barrier=(op==1&&kind==2)||op==5||op==6||(kind==3&&id==si);
          if(barrier)for(const auto& other:step.at("layers").array){const auto& x=other.at("block");if(x.type=='z'||&x==&b)continue;
            // STOP-all/PANIC clear pending gestures too; reject cross-phase
            // companions instead of silently losing their later HOLD action.
            record[0]=0;
          }
          actions.insert(actions.end(),{double(phase),double(op),double(kind),double(id)});continue;
        }
        if(choice(b.at("type"),{"MOVEMENT"})){
          auto it=movements.find(b.at("id").text);
          if(it==movements.end()){
            bool exists=false;if(root.object.count("movements"))for(const auto &m:root.at("movements").array)exists|=m.at("id").text==b.at("sourceId").text;
            if(exists)record[0]=0;else ++record[1];
          }else (chargeBlock(b)?chargeAdmissions:releaseBlock(b)?releaseAdmissions:onLongHold(b)?longAdmissions:onHold(b)?heldAdmissions:admissions).push_back(it->second);
          continue;
        }
        if(!supportedBlock(b)){record[0]=0;continue;}
        auto it=slots.find(b.at("sourceId").text);
        if(it==slots.end()){++record[1];continue;}
        if(groups[it->second] && winners[groups[it->second]]!=it->second)continue;
        if(n>=12){record[0]=0;record[3]=2;continue;}
        if(releaseBlock(b))record[72]+=1u<<n;if(chargeBlock(b))record[73]+=1u<<n;
        if(onHold(b))record[66]+=1u<<n;if(onLongHold(b))longMask+=1u<<n;
        if(revealBlock(b))record[68]+=1u<<n;
        if(gatedBlock(b))record[69]+=1u<<n;
        if(&layer==&step.at("layers").array.front())record[70]=n+1;
        double cc=localNumber(b,"revealCC"),fade=localNumber(b,"revealFadeSeconds");revealOptions.push_back(cc<0?7:cc);revealOptions.push_back(fade<0?0:fade);
        auto tune=b.at("overrides").object.find("phrase_tune");phraseTunes.push_back(tune!=b.at("overrides").object.end()&&choice(tune->second.at("mode"),{"OVERRIDE"})?tune->second.at("value").number:tunes[it->second]);
        unsigned row=4+n*5;record[row]=it->second;record[row+1]=-1;
        auto mode=b.at("overrides").object.find("playMode");
        if(mode!=b.at("overrides").object.end() && choice(mode->second.at("mode"),{"OVERRIDE"}))
          record[row+1]=choice(mode->second.at("value"),{"LOOP"})?0:choice(mode->second.at("value"),{"ONCE"})?1:2;
        record[row+2]=localNumber(b,"phrase_base_velocity");record[row+3]=localNumber(b,"phrase_velocity_decay");record[row+4]=localNumber(b,"phrase_time_decay");++n;
      }
      record[2]=n;record[64]=admissions.size();record[65]=base+out.size();record[67]=heldAdmissions.size();
      admissions.insert(admissions.end(),heldAdmissions.begin(),heldAdmissions.end());
      std::copy(record.begin(),record.end(),out.begin()+stepStart+stepIndex++*80);out.insert(out.end(),admissions.begin(),admissions.end());out.insert(out.end(),revealOptions.begin(),revealOptions.end());out.push_back(longMask);out.push_back(longAdmissions.size());out.insert(out.end(),longAdmissions.begin(),longAdmissions.end());
      record[74]=releaseAdmissions.size();record[75]=chargeAdmissions.size();record[76]=base+out.size();out.insert(out.end(),releaseAdmissions.begin(),releaseAdmissions.end());record[77]=base+out.size();out.insert(out.end(),chargeAdmissions.begin(),chargeAdmissions.end());
      record[78]=base+out.size();std::vector<double> binding;
      double patchThreshold=root.object.count("supercharge")?root.at("supercharge").at("thresholdMs").number:600,patchFull=root.object.count("supercharge")?root.at("supercharge").at("fullMs").number:2000;
      double threshold=(record[73]>0||!chargeAdmissions.empty()||chargeAction)?patchThreshold:-1,full=patchFull;
      if(step.object.count("supercharge")){
        const auto &c=step.at("supercharge");threshold=c.object.count("thresholdMs")?c.at("thresholdMs").number:patchThreshold;full=c.object.count("fullMs")?c.at("fullMs").number:patchFull;
        unsigned chargeIndex=0;for(const auto &a:c.at("bindings").array){if(a.object.count("target")){auto it=movements.find("charge:"+step.at("id").text+":"+std::to_string(chargeIndex));if(it!=movements.end())chargeAdmissions.push_back(it->second);++chargeIndex;continue;}++chargeIndex;unsigned row=0;for(const auto &l:step.at("layers").array){const auto &b=l.at("block");if(b.type=='z'||!choice(b.at("type"),{"PHRASE"})||!supportedBlock(b))continue;auto it=slots.find(b.at("sourceId").text);if(it==slots.end()||(groups[it->second]&&winners[groups[it->second]]!=it->second))continue;
          if(b.at("id").text==a.at("blockId").text){auto key=a.at("parameter").text;unsigned kind=key=="phrase_time_decay"?14:key=="phrase_velocity_decay"?15:17;const auto &d=performance::parameters[kind];binding.insert(binding.end(),{double(row),double(kind),a.at("from").number,a.at("to").number,a.at("factor").number,d.low,d.high});}++row;
        }}
      }
      record[75]=chargeAdmissions.size();record[77]=base+out.size();out.insert(out.end(),chargeAdmissions.begin(),chargeAdmissions.end());record[78]=base+out.size();
      out.insert(out.end(),{threshold,full,double(binding.size()/7)});out.insert(out.end(),binding.begin(),binding.end());
      record[79]=base+out.size();out.push_back(actions.size()/4);out.insert(out.end(),actions.begin(),actions.end());out.insert(out.end(),phraseTunes.begin(),phraseTunes.end());
      std::copy(record.begin(),record.end(),out.begin()+stepStart+(stepIndex-1)*80);

    }
  }
  return out;
}
}
