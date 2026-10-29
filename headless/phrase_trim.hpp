#pragma once
#include <array>
#include <cmath>
#include <vector>

namespace phrase_trim {
using Event = std::array<double,4>; // sample offset, status, data1, data2
struct Result { bool valid=false; unsigned count=0; double length=0; };
// Control-worker only. Never invent Note Offs or truncate an unfinished take.
inline Result endpoint(const std::vector<Event>& events) {
  std::array<unsigned,2048> held{};
  std::array<bool,16> sustain{}, sounding{};
  bool notes=false; double end=-1, previous=-1;
  for(const auto& e:events) {
    if(!std::isfinite(e[0]) || e[0]<0 || e[0]<previous) return {};
    previous=e[0];
    for(unsigned k=1;k<4;++k)
      if(!std::isfinite(e[k]) || e[k]!=std::floor(e[k]) || e[k]<0 || e[k]>(k==1?239:127)) return {};
    if(e[1]<128) return {};
    const unsigned status=unsigned(e[1]), channel=status&15, kind=status&240;
    const unsigned key=channel*128+unsigned(e[2]);
    if(kind==144 && e[3]>0) { ++held[key]; notes=true; }
    else if(kind==128 || (kind==144 && e[3]==0)) {
      if(!held[key]) return {};
      --held[key]; end=e[0];
      if(sustain[channel]) sounding[channel]=true;
    } else if(kind==176 && e[2]==64) {
      if(e[3]<64) { if(sounding[channel]) end=e[0]; sounding[channel]=false; }
      sustain[channel]=e[3]>=64;
    }
  }
  if(!notes || end<0) return {};
  for(auto n:held) if(n) return {};
  for(auto n:sounding) if(n) return {};
  unsigned count=0;
  for(const auto& e:events) if(e[0]<=end) ++count;
  // One sample includes the final release in the renderer's half-open span.
  return {true,count,end+1};
}
}
