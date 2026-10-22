#pragma once
// Native delayed-note foundation. No VM/schema changes and no callback allocation.
// A successful attack must be paired with a release of the SAME voice token;
// downstream transforms must release their captured outputs, never recompute them.
#include <array>
#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>

namespace native_notes {
enum class Origin : uint8_t { Live, Phrase };
struct SourceKey {
  uint32_t instrument = 0;
  Origin origin = Origin::Live;
  uint64_t instance = 0;
  uint8_t channel = 0, pitch = 0;
  bool operator==(const SourceKey &b) const {
    return instrument==b.instrument && origin==b.origin && instance==b.instance &&
           channel==b.channel && pitch==b.pitch;
  }
};
enum class TokenDomain : uint8_t { External, Source, Voice };
struct Token {
  uint32_t slot = UINT32_MAX;
  uint64_t generation = 0;
  TokenDomain domain=TokenDomain::External;
  explicit operator bool() const { return generation!=0; }
  bool operator==(const Token &b) const { return slot==b.slot && generation==b.generation && domain==b.domain; }
};

template<size_t Capacity> class Sources {
public:
  struct Record {
    SourceKey key{};
    uint64_t generation=0, start=0, end=0, order=0;
    uint32_t children=0;
    bool used=false, held=false;
  };
private:
  std::array<Record,Capacity> rows{};
  uint64_t generation=0;
public:
  const Record *get(Token t) const {
    return t.domain==TokenDomain::Source && t.slot<Capacity && rows[t.slot].used && rows[t.slot].generation==t.generation ? &rows[t.slot] : nullptr;
  }
  Token begin(SourceKey key, uint64_t sample) {
    if(!key.instrument || key.channel>15 || key.pitch>127 ||
       (key.origin!=Origin::Live && key.origin!=Origin::Phrase) || generation==UINT64_MAX)return {};
    for(size_t i=0;i<Capacity;++i)if(!rows[i].used){
      auto &r=rows[i];r=Record{};r.key=key;r.start=sample;r.order=r.generation=++generation;r.used=r.held=true;
      return {uint32_t(i),r.generation,TokenDomain::Source};
    }
    return {};
  }
  bool retain(Token t) {
    if(!get(t) || rows[t.slot].children==UINT32_MAX)return false;
    ++rows[t.slot].children;return true;
  }
  bool retire(Token t) {
    if(!get(t) || rows[t.slot].held || rows[t.slot].children)return false;
    rows[t.slot].used=false;return true;
  }
  bool drop(Token t) {
    if(!get(t) || !rows[t.slot].children)return false;
    auto &r=rows[t.slot];--r.children;if(!r.held && !r.children)r.used=false;return true;
  }
  bool close(Token t,uint64_t sample) {
    if(!get(t) || !rows[t.slot].held || sample<rows[t.slot].start)return false;
    auto &r=rows[t.slot];r.held=false;r.end=sample;return true;
  }
  Token oldestHeld(SourceKey key) const {
    Token result{};uint64_t first=UINT64_MAX;
    for(size_t i=0;i<Capacity;++i)if(rows[i].used && rows[i].held && rows[i].key==key && rows[i].order<first){
      first=rows[i].order;result={uint32_t(i),rows[i].generation,TokenDomain::Source};
    }
    return result;
  }
  size_t active() const {size_t n=0;for(const auto &r:rows)n+=r.used;return n;}
  template<class Match,class Visit> void visitHeld(Match match,Visit visit){
    for(size_t i=0;i<Capacity;++i)if(rows[i].used && rows[i].held && match(rows[i].key)){
      Token token{uint32_t(i),rows[i].generation,TokenDomain::Source};visit(token);
    }
  }
  template<class Match,class Visit> void visit(Match match,Visit visit){
    for(size_t i=0;i<Capacity;++i)if(rows[i].used && match(rows[i].key))
      visit(Token{uint32_t(i),rows[i].generation,TokenDomain::Source});
  }
  template<class Match> void closeMatching(uint64_t sample,Match match){
    for(auto &r:rows)if(r.used && match(r.key)){
      r.held=false;r.end=std::max(sample,r.start);if(!r.children)r.used=false;
    }
  }
  // Only after the caller has completed a global panic. Generations never reset.
  void resetAfterPanic(){for(auto &r:rows)r.used=false;}
};

struct Owner {
  uint32_t instrument=0, module=0, continuation=0;
  Origin origin=Origin::Live;
  uint64_t instance=0;
};
struct Pair {
  Owner owner{};
  uint64_t start=0, end=0;
  uint8_t channel=0,pitch=0,velocity=0;
  bool followSource=false;
  double durationScale=1;
};
struct Event {
  Owner owner{};
  Token voice{},source{};
  uint64_t sample=0;
  uint32_t offset=0;
  uint8_t channel=0,pitch=0,velocity=0;
  bool on=false;
};
enum class Refusal { None, InvalidSource, InvalidPair, Horizon, Capacity, Generation };

template<size_t VoiceCapacity=256,size_t SourceCapacity=256> class Scheduler {
  static_assert(VoiceCapacity>0 && SourceCapacity>0,"Nonempty bounded scheduler required");
  struct Voice {Pair pair{};Token source{};uint64_t generation=0,deadline=0;bool used=false,sounding=false,cancelled=false;};
  struct Due {uint64_t sample=0,order=0;Token voice{};bool on=false;};
  std::array<Voice,VoiceCapacity> voices{};
  std::array<Due,VoiceCapacity*2> heap{};
  size_t count=0;
  uint64_t generation=0,ordinal=0;
  uint64_t horizon;
  static bool earlier(const Due &a,const Due &b){return a.sample!=b.sample?a.sample<b.sample:a.order<b.order;}
  Voice *get(Token t){return t.domain==TokenDomain::Voice && t.slot<VoiceCapacity && voices[t.slot].used && voices[t.slot].generation==t.generation?&voices[t.slot]:nullptr;}
  void push(Due d){
    size_t i=count++;heap[i]=d;
    while(i){size_t p=(i-1)/2;if(!earlier(heap[i],heap[p]))break;std::swap(heap[i],heap[p]);i=p;}
  }
  void down(size_t i){
    for(;;){size_t child=i*2+1;if(child>=count)return;if(child+1<count && earlier(heap[child+1],heap[child]))++child;
      if(!earlier(heap[child],heap[i]))return;
      std::swap(heap[child],heap[i]);i=child;}
  }
  Due pop(){Due d=heap[0];heap[0]=heap[--count];if(count)down(0);return d;}
  void rebuild(){for(size_t i=count/2;i>0;--i)down(i-1);}
  void remove(Token token){
    size_t n=0;for(size_t i=0;i<count;++i)if(!(heap[i].voice==token))heap[n++]=heap[i];count=n;rebuild();
  }
  void finish(Token token){
    auto *v=get(token);if(!v)return;
    Token parent=v->source;v->used=false;remove(token);sources.drop(parent);
  }
  Event event(Token token,uint64_t sample,uint64_t blockStart,bool on) {
    const auto &v=*get(token);const auto &p=v.pair;
    return {p.owner,token,v.source,sample,uint32_t(sample-blockStart),p.channel,p.pitch,uint8_t(on?p.velocity:0),on};
  }
  template<class Emit> bool cancelOne(size_t i,uint64_t sample,Emit emit){
    auto &v=voices[i];Token token{uint32_t(i),v.generation,TokenDomain::Voice};v.cancelled=true;
    if(v.sounding && !emit(event(token,sample,sample,false))){
      ++failedReleases;needsRecovery=true;remove(token);push({sample,++ordinal,token,false});return false;
    }
    finish(token);return true;
  }
  bool reject(Refusal reason){lastRefusal=reason;++rejected;return false;}
public:
  Sources<SourceCapacity> sources;
  uint64_t rejected=0,failedAttacks=0,failedReleases=0,lateGateReleases=0;
  bool needsRecovery=false;
  Refusal lastRefusal=Refusal::None;
  explicit Scheduler(unsigned sampleRate=48000):horizon(uint64_t(sampleRate)*60){}
  size_t pending()const{return count;}
  uint64_t maxHorizon()const{return horizon;}
  size_t active()const{size_t n=0;for(const auto &v:voices)n+=v.used;return n;}
  // A batch represents one musical generation. Both edges of EVERY pair are
  // reserved before any state changes; overload never admits a partial batch.
  bool admit(Token source,const Pair *pairs,size_t length,uint64_t now) {
    const auto *parent=sources.get(source);
    if(!parent)return reject(Refusal::InvalidSource);
    if(!pairs || !length || length>VoiceCapacity)return reject(Refusal::InvalidPair);
    if(length>VoiceCapacity-active() || length*2>heap.size()-count)return reject(Refusal::Capacity);
    if(length>UINT64_MAX-generation || length*2>UINT64_MAX-ordinal)return reject(Refusal::Generation);
    for(size_t i=0;i<length;++i){const auto &p=pairs[i];
      if(!p.owner.instrument || p.owner.instrument!=parent->key.instrument || p.owner.origin!=parent->key.origin ||
         p.owner.instance!=parent->key.instance || p.channel>15 || p.pitch>127 || !p.velocity || p.velocity>127 || p.end<p.start ||
         !std::isfinite(p.durationScale) || p.durationScale<0 || p.durationScale>4)
        return reject(Refusal::InvalidPair);
      if(p.start<now || p.end-now>horizon)return reject(Refusal::Horizon);
    }
    size_t next=0;
    for(size_t i=0;i<length;++i){while(voices[next].used)++next;auto &v=voices[next];v=Voice{};
      v.used=true;v.pair=pairs[i];v.deadline=pairs[i].end;v.source=source;v.generation=++generation;sources.retain(source);
      Token token{uint32_t(next),v.generation,TokenDomain::Voice};push({v.pair.start,++ordinal,token,true});push({v.pair.end,++ordinal,token,false});
    }
    lastRefusal=Refusal::None;return true;
  }
  // Unknown live duration retains a watchdog off. Once its source releases,
  // seal each child's captured gate. A shortened gate already in the past is
  // released now, never backdated; this unavoidable live limit is observable.
  bool sealSource(Token source,uint64_t sourceOff,uint64_t now){
    const auto *parent=sources.get(source);
    if(!parent || !parent->held || sourceOff<parent->start || sourceOff>now)return false;
    const uint64_t duration=sourceOff-parent->start;
    if(!sources.close(source,sourceOff))return false;
    for(size_t i=0;i<VoiceCapacity;++i){auto &v=voices[i];if(!v.used || !(v.source==source) || !v.pair.followSource)continue;
      double scaled=std::min(double(horizon),double(duration)*v.pair.durationScale);
      uint64_t delta=uint64_t(std::floor(scaled+.5));
      uint64_t wanted=v.pair.start>UINT64_MAX-delta?UINT64_MAX:v.pair.start+delta;
      wanted=std::min(wanted,v.deadline);
      if(wanted<now){++lateGateReleases;wanted=now;}
      v.pair.end=wanted;
      const Token token{uint32_t(i),v.generation,TokenDomain::Voice};
      for(size_t j=0;j<count;++j)if(!heap[j].on && heap[j].voice==token)heap[j].sample=wanted;
    }
    rebuild();sources.retire(source);return true;
  }
  // Render [blockStart,blockEnd). Attack callback false MUST mean that no event
  // nor output ownership was committed. Release callbacks may complete part of
  // a fanout but must retain all unfinished output leases. A failed release
  // keeps its reserved slot
  // and retries at the next block, while requesting the host's emergency path.
  template<class Emit,class Valid> void render(uint64_t blockStart,uint32_t frames,Emit emit,Valid valid) {
    if(!frames || blockStart>UINT64_MAX-frames){needsRecovery=true;return;}
    const uint64_t end=blockStart+frames;
    while(count && heap[0].sample<end){
      Due d=pop();auto *v=get(d.voice);if(!v)continue;
      const uint64_t sample=std::max(blockStart,d.sample);
      if(d.on){
        if(v->cancelled || !valid(v->pair.owner)){finish(d.voice);continue;}
        if(!emit(event(d.voice,sample,blockStart,true))){++failedAttacks;finish(d.voice);continue;}
        v->sounding=true;
      }else{
        if(!v->sounding){finish(d.voice);continue;}
        if(!emit(event(d.voice,sample,blockStart,false))){++failedReleases;needsRecovery=true;d.sample=end;push(d);continue;}
        finish(d.voice);
      }
    }
  }
  template<class Emit> void render(uint64_t start,uint32_t frames,Emit emit){render(start,frames,emit,[](const Owner&){return true;});}
  // Match may select an instrument, module or source provenance. Already
  // sounding releases bypass owner-validity checks and use captured routing.
  template<class Match,class Emit> bool cancel(uint64_t sample,Match match,Emit emit) {
    bool ok=true;
    for(size_t i=0;i<VoiceCapacity;++i){auto &v=voices[i];if(!v.used || !match(v.pair.owner))continue;
      if(!cancelOne(i,sample,emit))ok=false;
    }
    return ok;
  }
  // Instrument deletion, phrase-instance stop or input disconnection also
  // retire held source records. Module-only bypass must use cancel() instead,
  // because other units may still share those source lifetimes.
  template<class Match,class Emit> bool cancelSources(uint64_t sample,Match match,Emit emit){
    bool ok=true;
    for(size_t i=0;i<VoiceCapacity;++i)if(voices[i].used){
      const auto *source=sources.get(voices[i].source);
      if(source && match(source->key) && !cancelOne(i,sample,emit))ok=false;
    }
    sources.closeMatching(sample,match);return ok;
  }
  template<class Emit> bool cancelSource(Token source,uint64_t sample,Emit emit){
    bool ok=true;
    for(size_t i=0;i<VoiceCapacity;++i)if(voices[i].used && voices[i].source==source && !cancelOne(i,sample,emit))ok=false;
    if(sources.get(source) && sources.get(source)->held)sources.close(source,sample);
    sources.retire(source);return ok;
  }
  // Use only after actual global panic delivery, never to hide a failed release.
  void resetAfterPanic(){for(auto &v:voices)v.used=false;count=0;sources.resetAfterPanic();needsRecovery=false;}
};

// Stable downstream-output ledger. Transform attack once, capture its outputs,
// then release those exact outputs even if pitch/channel/stage parameters change.
// Multiple owners of one channel/pitch share one physical note and its last off.
template<size_t Capacity=512> class Outputs {
  struct Lease {Token voice{};uint32_t branch=0;uint8_t channel=0,pitch=0;bool used=false;};
  std::array<Lease,Capacity> leases{};
  std::array<uint32_t,2048> held{};
public:
  struct Routed {uint32_t branch=0;uint8_t channel=0,pitch=0,velocity=0;bool retrigger=false;};
  // The emitter reserves the whole physical batch atomically before committing.
  // No first-half chord may escape if the downstream queue cannot accept it.
  // repeatAttack emits another On without an Off, retaining earlier leases.
  // retrigger keeps the explicit Off/On policy used by delayed echo voices.
  template<class EmitBatch> bool attackBatch(Token voice,const Routed *notes,size_t length,EmitBatch emit,bool retrigger=false,bool repeatAttack=false){
    constexpr size_t maxFanout=16;
    if(!voice || !notes || !length || length>maxFanout || length>Capacity)return false;
    std::array<size_t,maxFanout> free{};size_t available=0;
    std::array<Routed,maxFanout> physical{};size_t attacks=0;
    for(size_t j=0;j<length;++j){const auto &n=notes[j];
      if(n.channel>15 || n.pitch>127 || !n.velocity || n.velocity>127)return false;
      for(size_t k=0;k<j;++k)if(notes[k].branch==n.branch)return false;
      for(const auto &v:leases)if(v.used && v.voice==voice && v.branch==n.branch)return false;
      if(!held[n.channel*128+n.pitch] || retrigger || repeatAttack){
        bool duplicate=false;for(size_t k=0;k<attacks;++k)if(physical[k].channel==n.channel && physical[k].pitch==n.pitch)duplicate=true;
        if(!duplicate){physical[attacks]=n;physical[attacks++].retrigger=retrigger && held[n.channel*128+n.pitch]>0;}
      }
    }
    for(size_t j=0;j<Capacity && available<length;++j)if(!leases[j].used)free[available++]=j;
    if(available<length || (attacks && !emit(physical.data(),attacks)))return false;
    for(size_t j=0;j<length;++j){const auto &n=notes[j];leases[free[j]]={voice,n.branch,n.channel,n.pitch,true};++held[n.channel*128+n.pitch];}
    return true;
  }
  template<class Emit> bool attack(Token voice,uint32_t branch,uint8_t ch,uint8_t pitch,uint8_t velocity,Emit emit){
    const Routed note{branch,ch,pitch,velocity};
    return attackBatch(voice,&note,1,[&](const Routed *batch,size_t count){return count==1 && emit(true,batch[0].channel,batch[0].pitch,batch[0].velocity);});
  }
  template<class Emit> bool release(Token voice,Emit emit){
    bool ok=true;
    for(auto &v:leases)if(v.used && v.voice==voice){
      const unsigned key=v.channel*128+v.pitch;
      if(held[key]==1 && !emit(false,v.channel,v.pitch,0)){ok=false;continue;}
      --held[key];v.used=false;
    }
    return ok;
  }
  size_t active()const{size_t n=0;for(const auto &v:leases)n+=v.used;return n;}
  uint32_t owners(uint8_t ch,uint8_t pitch)const{return ch<16 && pitch<128?held[ch*128+pitch]:0;}
  // Called only for a CC120/123 already reserved in the host's output batch.
  void channelCleared(uint8_t channel){
    if(channel>15)return;
    for(auto &v:leases)if(v.used && v.channel==channel)v.used=false;
    for(unsigned pitch=0;pitch<128;++pitch)held[channel*128+pitch]=0;
  }
  void resetAfterPanic(){for(auto &v:leases)v.used=false;held.fill(0);}
};
} // namespace native_notes
