#pragma once
#include "native_expressive_transformers.hpp"
#include <array>
#include <iomanip>
#include <istream>
#include <sstream>

namespace expressive {
struct InstrumentSettings {
  uint32_t instrument=0,humanizerModule=0,curveModule=0;
  Humanizer humanizer{};
  VelocityCurve curve{};
};
using Configuration=std::array<InstrumentSettings,8>;

inline bool finiteNumber(std::istream&in,double&value,double low,double high){
  return bool(in>>value)&&std::isfinite(value)&&value>=low&&value<=high;
}
// Versioned worker-side patch carrier; stable instrument/module identities,
// no live voice cursors or scheduler scratch are serialized.
inline bool readConfiguration(std::istream&in,Configuration&out){
  unsigned version=0,count=0;
  if(!(in>>version)||version!=1||!(in>>count)||count>out.size())return false;
  Configuration next{};
  for(unsigned j=0;j<count;++j){
    auto&s=next[j];unsigned humanizerEnabled=0,curveEnabled=0,feel=0,variation=0,scope=0,points=0;
    if(!(in>>s.instrument>>s.humanizerModule)||!s.instrument||s.instrument>16777215||
       s.humanizerModule>16777215||!(in>>humanizerEnabled)||humanizerEnabled>1||
       !finiteNumber(in,s.humanizer.timingMs,0,2000)||
       !finiteNumber(in,s.humanizer.biasMs,-2000,2000)||
       !finiteNumber(in,s.humanizer.velocityPercent,0,100)||
       !(in>>feel>>variation>>scope>>s.humanizer.seed)||
       feel>1||variation>1||scope>1||
       !finiteNumber(in,s.humanizer.liveLookaheadMs,0,2000)||
       !(in>>s.curveModule)||s.curveModule>16777215||
       !(in>>curveEnabled)||curveEnabled>1||
       !finiteNumber(in,s.curve.amount,0,100)||
       !(in>>points)||points<2||points>s.curve.points.size())return false;
    s.humanizer.enabled=humanizerEnabled;s.humanizer.feel=Feel(feel);
    s.humanizer.variation=Variation(variation);s.humanizer.scope=Scope(scope);
    s.curve.enabled=curveEnabled;s.curve.count=points;
    for(unsigned k=0;k<points;++k){
      unsigned x=0,y=0;if(!(in>>x>>y)||x<1||x>127||y<1||y>127)return false;
      s.curve.points[k]={uint8_t(x),uint8_t(y)};
    }
    if(!s.humanizer.valid()||!s.curve.valid())return false;
    for(unsigned k=0;k<j;++k)if(next[k].instrument==s.instrument)return false;
  }
  out=next;return true;
}
inline std::string configurationJson(const Configuration&c){
  std::ostringstream o;o<<std::setprecision(17);unsigned count=0;
  for(const auto&s:c)if(s.instrument)++count;
  o<<"{\"version\":1,\"configuration\":[1,"<<count;
  for(const auto&s:c)if(s.instrument){
    o<<','<<s.instrument<<','<<s.humanizerModule<<','<<unsigned(s.humanizer.enabled)
     <<','<<s.humanizer.timingMs<<','<<s.humanizer.biasMs<<','<<s.humanizer.velocityPercent
     <<','<<unsigned(s.humanizer.feel)<<','<<unsigned(s.humanizer.variation)
     <<','<<unsigned(s.humanizer.scope)<<','<<s.humanizer.seed<<','<<s.humanizer.liveLookaheadMs
     <<','<<s.curveModule<<','<<unsigned(s.curve.enabled)<<','<<s.curve.amount<<','<<s.curve.count;
    for(unsigned k=0;k<s.curve.count;++k)o<<','<<unsigned(s.curve.points[k].x)<<','<<unsigned(s.curve.points[k].y);
  }
  o<<"]}";return o.str();
}
} // namespace expressive
