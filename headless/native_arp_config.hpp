#pragma once
#include "snapshot_wire.hpp"
#include <array>
#include <istream>
#include <sstream>
// Worker-side versioned carrier. Stable Instrument IDs, no runtime cursor/voices.
namespace native_arp {
struct Settings { unsigned instrument=0,step=2,playback=0; };
using Configuration=std::array<Settings,8>;
inline bool read(std::istream &in,Configuration &out){
 unsigned version,n;if(!performance::integer(in,version,1)||version!=1||!performance::integer(in,n,8))return false;
 for(unsigned j=0;j<n;++j){auto &s=out[j];
  if(!performance::integer(in,s.instrument,16777215)||!s.instrument||!performance::integer(in,s.step,4)||!s.step||!performance::integer(in,s.playback,1))return false;
  for(unsigned k=0;k<j;++k)if(out[k].instrument==s.instrument)return false;
 }return true;
}
inline std::string json(const Configuration &c){std::ostringstream o;unsigned n=0;for(const auto &s:c)if(s.instrument)++n;
 o<<"{\"version\":1,\"configuration\":[1,"<<n;for(const auto &s:c)if(s.instrument)o<<','<<s.instrument<<','<<s.step<<','<<s.playback;o<<"]}";return o.str();}
}
