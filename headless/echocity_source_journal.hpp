#pragma once
#include "echocity_source_bridge.hpp"

namespace echocity {
// Storage is owned/pre-bound by the native host at startup. Reading or sorting
// a block needs no VM lookup, allocation or lock. Full block validation precedes
// every callback: a missing release must never leave a partially admitted block.
template<size_t Capacity=1024> class SourceJournal {
  static_assert(Capacity>0,"Nonempty source journal required");
  struct Entry {SourceEvent event{};size_t order=0;};
  std::array<Entry,Capacity> entries{};
public:
  uint64_t rejectedBlocks=0;
  bool needsRecovery=false;
  // readCell(index) returns a pre-bound double. The caller acknowledges the VM
  // cursors only after success; a rejected block requires its emergency path.
  template<class Read,class Visit>
  bool consume(double read,double write,double overflow,unsigned frames,Read readCell,Visit visit){
    auto reject=[&](){++rejectedBlocks;needsRecovery=true;return false;};
    if(!frames || !std::isfinite(read) || !std::isfinite(write) || !std::isfinite(overflow) ||
       overflow!=0 || read<0 || write<read || write>9007199254740991. ||
       std::floor(read)!=read || std::floor(write)!=write || write-read>Capacity)return reject();
    const size_t count=size_t(write-read);const uint64_t first=uint64_t(read);
    for(size_t j=0;j<count;++j){
      double row[6];for(unsigned k=0;k<6;++k)row[k]=readCell(((first+j)%Capacity)*6+k);
      auto &entry=entries[j];entry.order=j;
      if(!decodeSource(row,entry.event,frames))return reject();
    }
    std::sort(entries.begin(),entries.begin()+count,[](const Entry&a,const Entry&b){
      return a.event.offset!=b.event.offset?a.event.offset<b.event.offset:a.order<b.order;
    });
    for(size_t j=0;j<count;++j)visit(entries[j].event);
    return true;
  }
};
} // namespace echocity
