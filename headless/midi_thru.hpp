#pragma once
#include <array>
#include <cstdint>
#include <istream>
#include <sstream>
#include <string>

namespace midi_thru {
constexpr unsigned Slots=16, Channels=16, MaxIdentity=16777215;
enum class Mode:int8_t { Inherit=-1, Off=0, Unassigned=1, All=2 };
struct Rule {
  uint32_t source=0;
  std::array<int8_t,Channels> channels{};
  Rule(){channels.fill(int8_t(Mode::Inherit));}
};
using Configuration=std::array<Rule,Slots>;
struct Input {
  uint32_t source=0;
  bool connected=false;
  std::array<int8_t,Channels> channels{};
  Input(){channels.fill(int8_t(Mode::Unassigned));}
};
using Inputs=std::array<Input,Slots>;

inline bool read(std::istream&in,Configuration&out) {
  unsigned version=0,count=0;
  if(!(in>>version>>count)||version!=1||count>Slots)return false;
  Configuration next{};
  for(unsigned n=0;n<count;++n){
    unsigned id=0;if(!(in>>id)||!id||id>MaxIdentity)return false;
    for(unsigned p=0;p<n;++p)if(next[p].source==id)return false;
    next[n].source=id;
    for(auto&mode:next[n].channels){int value=0;if(!(in>>value)||value<-1||value>2)return false;mode=int8_t(value);}
  }
  out=next;return true;
}
inline std::string json(const Configuration&config) {
  unsigned count=0;for(const auto&r:config)if(r.source)++count;
  std::ostringstream out;out<<"{\"version\":1,\"configuration\":[1,"<<count;
  for(const auto&r:config)if(r.source){out<<','<<r.source;for(auto mode:r.channels)out<<','<<int(mode);}
  out<<"]}";return out.str();
}
inline int8_t effective(const Configuration&patch,const Input&input,unsigned channel) {
  if(channel>=Channels||!input.source||!input.connected)return int8_t(Mode::Off);
  for(const auto&r:patch)if(r.source==input.source && r.channels[channel]!=int8_t(Mode::Inherit))return r.channels[channel];
  return input.channels[channel];
}
inline bool readInputs(std::istream&in,Inputs&out) {
  unsigned version=0,count=0;if(!(in>>version>>count)||version!=1||count>=Slots)return false;
  Inputs next{};std::array<bool,Slots> seen{};
  for(unsigned n=0;n<count;++n){
    unsigned slot=0,source=0,connected=0;
    if(!(in>>slot>>source>>connected)||slot==0||slot>=Slots||seen[slot]||!source||source>MaxIdentity||connected>1)return false;
    for(const auto&r:next)if(r.source==source)return false;
    seen[slot]=true;auto&input=next[slot];input.source=source;input.connected=connected!=0;
    for(auto&mode:input.channels){int value=0;if(!(in>>value)||value<0||value>2)return false;mode=int8_t(value);}
  }
  out=next;return true;
}
inline bool empty(const Configuration&config){for(const auto&r:config)if(r.source)return false;return true;}
inline std::string inputsJson(const Inputs&inputs){
  unsigned count=0;for(unsigned slot=1;slot<Slots;++slot)if(inputs[slot].source)++count;
  std::ostringstream out;out<<"{\"version\":1,\"configuration\":[1,"<<count;
  for(unsigned slot=1;slot<Slots;++slot){const auto&input=inputs[slot];if(!input.source)continue;
    out<<','<<slot<<','<<input.source<<','<<(input.connected?1:0);
    for(auto mode:input.channels)out<<','<<int(mode);
  }
  out<<"]}";return out.str();
}

// Callback-owned state. A control-worker update is validated before reaching
// this object. The returned mask is consumed in DSP context, where releasing
// held notes is safe; no JACK graph access or heap allocation occurs here.
struct Update {
  std::array<int8_t,Slots*Channels> modes{};
  std::array<bool,Slots*Channels> close{};
  std::array<bool,Slots> fresh{};
};
class Runtime {
  Configuration patch_{};
  Inputs inputs_{};
public:
  Update configure(const Configuration&patch,const Inputs&inputs) {
    Update result{};
    for(unsigned slot=0;slot<Slots;++slot)
      result.fresh[slot]=inputs_[slot].source!=inputs[slot].source ||
                        (!inputs_[slot].connected && inputs[slot].connected);
    for(unsigned slot=0;slot<Slots;++slot)
      for(unsigned ch=0;ch<Channels;++ch){
        const unsigned at=slot*Channels+ch;
        const auto before=effective(patch_,inputs_[slot],ch);
        const auto after=effective(patch,inputs[slot],ch);
        result.modes[at]=after;
        result.close[at]=before!=after || inputs_[slot].source!=inputs[slot].source ||
                         inputs_[slot].connected!=inputs[slot].connected;
      }
    patch_=patch;inputs_=inputs;return result;
  }
};
} // namespace midi_thru
