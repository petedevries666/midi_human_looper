#pragma once
#include "echocity_core.hpp"
#include <istream>
#include <sstream>
#include <iomanip>
namespace echocity {
using Configurations=std::array<Configuration,8>;
inline bool read(std::istream &in,Configurations &out){
  unsigned version=0,count=0;if(!(in>>version>>count)||version!=1||count>8)return false;
  Configurations next{};
  for(unsigned j=0;j<count;++j){auto &c=next[j];unsigned enabled=0,unit=0,ping=0;
    if(!(in>>c.instrument>>enabled>>unit>>c.interval>>c.firstOffset>>c.wet>>c.decay>>c.gate>>c.gateDecay>>c.repeats>>c.pitchStep>>ping>>c.otherChannel)||enabled>1||unit>1||ping>1)return false;
    c.id=c.instrument;c.enabled=enabled;c.unit=TimeUnit(unit);c.pingPong=ping;
    if(!valid(c))return false;
    for(unsigned k=0;k<j;++k)if(next[k].instrument==c.instrument)return false;
  }
  out=next;return true;
}
inline std::string json(const Configurations &all){
  std::ostringstream out;out<<std::setprecision(17)<<"{\"version\":1,\"configuration\":[1,";
  unsigned count=0;for(const auto &c:all)count+=bool(c.id);out<<count;
  for(const auto &c:all)if(c.id)out<<','<<c.instrument<<','<<c.enabled<<','<<unsigned(c.unit)<<','<<c.interval<<','<<c.firstOffset<<','<<c.wet<<','<<c.decay<<','<<c.gate<<','<<c.gateDecay<<','<<c.repeats<<','<<c.pitchStep<<','<<c.pingPong<<','<<c.otherChannel;
  out<<"]}";return out.str();
}
}
