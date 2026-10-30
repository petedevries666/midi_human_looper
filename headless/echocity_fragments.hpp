#pragma once
#include "echocity_core.hpp"
namespace echocity {
// WET-only bounded note-on fragments. Source leases preserve original durations
// across release and natural phrase completion; dry attacks are never buffered.
class Fragments {
  using Scheduler=native_notes::Scheduler<256,2048>;
  struct Entry {native_notes::Token source{};uint64_t on=0;uint8_t velocity=0;};
  struct Window {
    Configuration config{};std::array<Entry,64> notes{};unsigned count=0;
    uint64_t start=0,width=0;double tempo=0;
    uint32_t seed=0,nextSeed=0,reverseMask=0;bool seeded=false,open=false,overflow=false;
  };
  std::array<Window,8> windows{};
  std::array<native_notes::Pair,256> batch{};
  std::array<native_notes::Pair,32> scratch{};
  std::array<unsigned,64> counts{};
  std::array<uint64_t,32> anchors{};
  static uint32_t next(uint32_t seed){seed^=seed<<13;seed^=seed>>17;seed^=seed<<5;return seed;}
  static void drop(Window&w,Scheduler&s){for(unsigned i=0;i<w.count;++i)s.sources.drop(w.notes[i].source);w.count=0;w.open=false;w.overflow=false;}
  bool finish(Window&w,Scheduler&s){
    if(w.overflow){drop(w,s);return true;}
    const uint64_t boundary=w.start+w.width;size_t total=0;Unit unit(unsigned(s.maxHorizon()/60));unit.configure(w.config);
    bool ok=true;
    for(unsigned i=0;i<w.count && ok;++i){const auto &e=w.notes[i];const auto *parent=s.sources.get(e.source);if(!parent){ok=false;break;}
      const uint64_t relative=e.on-w.start;
      for(unsigned repeat=0;repeat<w.config.repeats;++repeat){
        const uint64_t offset=(w.reverseMask&(uint32_t(1)<<repeat))?w.width-1-relative:relative;
        if(boundary>UINT64_MAX-offset){ok=false;break;}anchors[repeat]=boundary+offset;
      }
      if(!ok)break;
      const auto result=unit.plan(s,e.source,parent->key.channel,parent->key.pitch,e.velocity,boundary,scratch,w.tempo,boundary,&anchors);
      if(!result.ok || total+result.planned>s.available() || total+result.planned>batch.size()){ok=false;break;}
      counts[i]=result.planned;std::copy_n(scratch.begin(),result.planned,batch.begin()+total);total+=result.planned;
    }
    if(ok){size_t offset=0;for(unsigned i=0;i<w.count;++i){if(counts[i]&&!s.admit(w.notes[i].source,batch.data()+offset,counts[i],boundary)){s.needsRecovery=true;ok=false;break;}offset+=counts[i];}}
    if(ok && total && w.config.traversal==Traversal::RandomChaos)w.seed=w.nextSeed;
    drop(w,s);return ok;
  }
public:
  size_t pending()const{size_t n=0;for(const auto&w:windows)n+=w.count;return n;}
  unsigned flush(uint64_t through,Scheduler&s){unsigned refused=0;for(auto&w:windows)if(w.open && w.start+w.width<=through)refused+=!finish(w,s);return refused;}
  bool add(unsigned index,const Configuration&c,native_notes::Token source,uint8_t velocity,uint64_t sample,double tempo,Scheduler&s){
    unsigned selected=unsigned(windows.size());
    for(unsigned i=0;i<windows.size();++i)if(windows[i].config.id==c.id){selected=i;break;}
    if(selected==windows.size()){if(index<windows.size()&&!windows[index].open)selected=index;else for(unsigned i=0;i<windows.size();++i)if(!windows[i].open){selected=i;break;}if(selected==windows.size())return false;windows[selected]=Window{};}
    auto&w=windows[selected];
    if(!w.open){
      if(c.unit==TimeUnit::Beats && (!std::isfinite(tempo)||tempo<=0||tempo>1000))return false;
      const double width=c.unit==TimeUnit::Milliseconds?c.interval*double(s.maxHorizon()/60)/1000.:c.interval*60.*double(s.maxHorizon()/60)/tempo;
      if(!std::isfinite(width)||width<1||width>double(s.maxHorizon())||sample>UINT64_MAX-uint64_t(std::floor(width+.5)))return false;
      w.config=c;w.start=sample;w.width=uint64_t(std::floor(width+.5));w.tempo=tempo;w.open=true;w.overflow=false;
      if(!w.seeded){w.seed=0x9e3779b9u^(c.instrument*0x85ebca6bu);if(!w.seed)w.seed=1;w.seeded=true;}
      // One decision per repetition, shared by every note in this fragment.
      w.nextSeed=w.seed;w.reverseMask=0;
      for(unsigned repeat=0;repeat<c.repeats;++repeat){
        if(c.traversal==Traversal::RandomChaos)w.nextSeed=next(w.nextSeed);
        if(c.traversal==Traversal::ReverseAll || (c.traversal==Traversal::Alternate && repeat%2) ||
           (c.traversal==Traversal::RandomChaos && (w.nextSeed&1)))w.reverseMask|=uint32_t(1)<<repeat;
      }
    }
    if(w.overflow)return true;
    if(w.count==w.notes.size()){for(unsigned i=0;i<w.count;++i)s.sources.drop(w.notes[i].source);w.count=0;w.overflow=true;return false;}
    if(!s.sources.retain(source))return false;
    w.notes[w.count++]={source,sample,velocity};return true;
  }
  template<class Match> void cancel(Match match,Scheduler&s){
    for(auto&w:windows){unsigned n=0;for(unsigned i=0;i<w.count;++i){const auto*p=s.sources.get(w.notes[i].source);if(!p || match(p->key)){if(p)s.sources.drop(w.notes[i].source);}else w.notes[n++]=w.notes[i];}w.count=n;if(!n){w.open=false;w.overflow=false;}}
  }
  void cancelModule(uint32_t module,Scheduler&s){for(auto&w:windows)if(w.config.id==module){if(w.open)drop(w,s);w=Window{};}}
  void reset(){for(auto&w:windows)w=Window{};}
};
}
