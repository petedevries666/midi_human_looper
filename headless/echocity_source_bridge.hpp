#pragma once
#include "echocity_core.hpp"

namespace echocity {
enum class SourceAction : unsigned { On=1, Off=2, StopInstance=3, RemoveInstrument=4, Reset=5, StopPhrases=6, EndInstance=7, ChannelClear=8 };
struct SourceEvent {
  SourceAction action=SourceAction::Reset;
  native_notes::SourceKey key{};
  unsigned velocity=0,offset=0;
  unsigned journalIndex=0,order=0,sequence=0;
};
// Decodes one native VM journal row, without truncating malformed doubles into
// plausible MIDI or identities. No VM dependency or allocation in the decoder.
inline bool decodeSource(const double *row,SourceEvent &out,unsigned frames){
  if(!row || !frames)return false;
  const double maxima[]={7,16777215,9007199254740991.,262143,2,double(frames-1)};
  for(unsigned j=0;j<6;++j)if(!std::isfinite(row[j]) || row[j]<0 || row[j]>maxima[j] || std::floor(row[j])!=row[j])return false;
  if(row[0]<1)return false;
  SourceEvent e{};e.action=SourceAction(unsigned(row[0]));e.key.instrument=uint32_t(row[1]);
  e.key.instance=uint64_t(row[2]);e.key.origin=native_notes::Origin(unsigned(row[4]));
  const unsigned packed=unsigned(row[3]);e.key.channel=packed&15;e.key.pitch=(packed>>4)&127;
  e.velocity=(packed>>11)&127;e.offset=unsigned(row[5]);
  switch(e.action){
    case SourceAction::On:case SourceAction::Off:
      if(!e.key.instrument || (e.action==SourceAction::On && !e.velocity) ||
         (e.action==SourceAction::Off && e.velocity) ||
         (e.key.origin!=native_notes::Origin::Phrase && e.key.instance))return false;
      break;
    case SourceAction::StopInstance:case SourceAction::EndInstance:if(e.key.instrument || !e.key.instance || row[4]!=1 || packed)return false;break;
    case SourceAction::RemoveInstrument:if(!e.key.instrument || e.key.instance || row[4] || packed)return false;break;
    case SourceAction::Reset:if(e.key.instrument || e.key.instance || row[4] || packed)return false;break;
    case SourceAction::StopPhrases:if(e.key.instrument || e.key.instance || row[4]!=1 || packed)return false;break;
    case SourceAction::ChannelClear:return false; // Host-only: actual output CC reservation required.
  }
  out=e;return true;
}

// Real source lifetimes, independent of the eventual ordered-stage dispatcher.
// The caller admits its configured units in `attack`; it must not reenter from
// the scheduler's emit callback. Dry MIDI is deliberately not intercepted here.
template<size_t Voices=256,size_t Sources=256> class SourceBridge {
public:
  native_notes::Scheduler<Voices,Sources> scheduler;
  uint64_t unmatchedOffs=0,rejectedSources=0;
  bool needsRecovery=false;
  explicit SourceBridge(unsigned rate):scheduler(rate){}
  template<class Attack,class Emit>
  bool apply(const SourceEvent &e,uint64_t sample,Attack attack,Emit emit){
    using namespace native_notes;
    if(e.action==SourceAction::On){
      Token token=scheduler.sources.begin(e.key,sample);
      if(!token){++rejectedSources;needsRecovery=true;return false;}
      attack(token,e,sample);
      return true;
    }
    if(e.action==SourceAction::Off){
      Token token=scheduler.sources.oldestHeld(e.key);
      if(!token){++unmatchedOffs;return false;}
      return scheduler.sealSource(token,sample,sample);
    }
    if(e.action==SourceAction::EndInstance){
      scheduler.sources.visitHeld([&](const SourceKey &key){return key.origin==Origin::Phrase && key.instance==e.key.instance;},
        [&](Token token){scheduler.sealSource(token,sample,sample);});
      return true;
    }
    auto matches=[&](const SourceKey &key){
      if(e.action==SourceAction::StopInstance)return key.origin==Origin::Phrase && key.instance==e.key.instance;
      if(e.action==SourceAction::RemoveInstrument)return key.instrument==e.key.instrument;
      if(e.action==SourceAction::StopPhrases)return key.origin==Origin::Phrase;
      return e.action==SourceAction::Reset;
    };
    if(!scheduler.cancelSources(sample,matches,emit)){needsRecovery=true;return false;}
    return true;
  }
};
} // namespace echocity
