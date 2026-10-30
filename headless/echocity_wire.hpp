#pragma once
#include "echocity_core.hpp"
#include <istream>
#include <sstream>
#include <iomanip>
namespace echocity {
using Configurations=std::array<Configuration,8>;
inline bool read(std::istream &in,Configurations &out){
  unsigned version=0,count=0;if(!(in>>version>>count)||version<1||version>4||count>8)return false;
  Configurations next{};
  for(unsigned j=0;j<count;++j){auto &c=next[j];unsigned enabled=0,unit=0,ping=0;
    if(!(in>>c.instrument>>enabled>>unit>>c.interval>>c.firstOffset>>c.wet>>c.decay>>c.gate>>c.gateDecay>>c.repeats>>c.pitchStep>>ping>>c.otherChannel)||enabled>1||unit>1||ping>1)return false;
    if(version>=2){if(!(in>>c.dry))return false;}else c.dry=1-c.wet;
    if(version>=3){unsigned traversal;if(!(in>>traversal)||traversal>3)return false;c.traversal=Traversal(traversal);}
    if(version>=4){unsigned routing,noRepeat;
      if(!(in>>routing>>c.channelMask>>noRepeat>>c.patternLength)||routing>3||noRepeat>1||c.patternLength>16)return false;
      c.routing=Routing(routing);c.noRepeat=noRepeat;
      for(auto&ch:c.pattern){unsigned value;if(!(in>>value)||value>15)return false;ch=uint8_t(value);}
    }
    c.id=c.instrument;c.enabled=enabled;c.unit=TimeUnit(unit);c.pingPong=ping;
    if(!valid(c))return false;
    for(unsigned k=0;k<j;++k)if(next[k].instrument==c.instrument)return false;
  }
  out=next;return true;
}
inline std::string json(const Configurations &all){
  unsigned version=2;for(const auto &c:all)if(c.id){if(c.traversal!=Traversal::Forward)version=std::max(version,3u);if(c.routing!=Routing::Legacy)version=4;}
  std::ostringstream out;out<<std::setprecision(17)<<"{\"version\":"<<version<<",\"configuration\":["<<version<<',';
  unsigned count=0;for(const auto &c:all)count+=bool(c.id);out<<count;
  for(const auto &c:all)if(c.id){out<<','<<c.instrument<<','<<c.enabled<<','<<unsigned(c.unit)<<','<<c.interval<<','<<c.firstOffset<<','<<c.wet<<','<<c.decay<<','<<c.gate<<','<<c.gateDecay<<','<<c.repeats<<','<<c.pitchStep<<','<<c.pingPong<<','<<c.otherChannel<<','<<c.dry;if(version>=3)out<<','<<unsigned(c.traversal);if(version>=4){out<<','<<unsigned(c.routing)<<','<<c.channelMask<<','<<c.noRepeat<<','<<c.patternLength;for(auto ch:c.pattern)out<<','<<unsigned(ch);}}
  out<<"]}";return out.str();
}
}
