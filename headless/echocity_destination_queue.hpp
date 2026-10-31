#pragma once
#include "native_note_scheduler.hpp"
namespace echocity {
// A bounded handoff into the next DSP block. Every admitted attack reserves
// room for its release. Input identities never enter MIDI Learn or recording.
class DestinationQueue {
public:
  struct Entry {native_notes::Token voice{};uint32_t target=0,offset=0;uint8_t channel=0,pitch=0,velocity=0;bool on=false;uint64_t order=0;};
private:
  std::array<Entry,512> entries{};
  std::array<Entry,256> held{};
  size_t count=0,active=0;uint64_t order=0;
public:
  bool attack(const native_notes::Event&e,uint32_t target,uint32_t offset){
    if(!target || e.voice.generation>9007199254740991ULL || e.voice.slot>=held.size() || held[e.voice.slot].target || count+active+2>entries.size())return false;
    Entry row{e.voice,target,offset,e.channel,e.pitch,e.velocity,true,++order};
    held[e.voice.slot]=row;entries[count++]=row;++active;return true;
  }
  bool release(const native_notes::Event&e,uint32_t offset){
    if(e.voice.slot>=held.size())return false;
    auto &lease=held[e.voice.slot];if(!lease.target || !(lease.voice==e.voice))return true;
    if(count>=entries.size())return false;
    auto row=lease;row.on=false;row.velocity=0;row.offset=offset;row.order=++order;
    entries[count++]=row;lease={};--active;return true;
  }
  template<class Visit> void drain(Visit visit){
    std::sort(entries.begin(),entries.begin()+count,[](const Entry&a,const Entry&b){return a.offset!=b.offset?a.offset<b.offset:a.order<b.order;});
    for(size_t j=0;j<count;++j)visit(entries[j]);count=0;
  }
  void reset(){count=active=0;held={};}
  size_t pending()const{return count;}
  size_t leases()const{return active;}
};
}
