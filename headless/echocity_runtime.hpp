#pragma once
#include "echocity_source_journal.hpp"
#include "echocity_wire.hpp"
#include "echocity_fragments.hpp"
namespace echocity {
// Terminal instrument effect. Logical dry notes and delayed voices share one
// output ledger. Phrase dry attacks remain audible as repeated Note Ons;
// delayed attacks retain their existing explicit Off/On retrigger policy.
class Runtime {
  using Scheduler=native_notes::Scheduler<256,2048>;
  using Outputs=native_notes::Outputs<4096>;
  Scheduler scheduler;
  Outputs outputs;
  Configurations config{};
  Fragments fragments;
  struct Dry {native_notes::Token token{};uint64_t off=0;bool leased=false,pending=false;};
  std::array<Dry,2048> dry{};
  std::array<uint32_t,8> cancelled{};
  unsigned rate;
  bool clear=false;
  template<class Emit> bool releaseDry(native_notes::Token token,uint64_t sample,Emit emit){
    auto &d=dry[token.slot];if(!d.leased || !(d.token==token))return true;
    if(!outputs.release(token,[&](bool on,uint8_t ch,uint8_t pitch,uint8_t velocity){return emit(sample,on,ch,pitch,velocity,false);})){d.pending=true;d.off=sample;failed=true;return false;}
    d.leased=d.pending=false;scheduler.sources.drop(token);return true;
  }
  template<class Emit> bool voice(const native_notes::Event &e,Emit emit){
    if(!e.on)return outputs.release(e.voice,[&](bool on,uint8_t ch,uint8_t pitch,uint8_t vel){return emit(e.sample,on,ch,pitch,vel,false);});
    const Outputs::Routed note{0,e.channel,e.pitch,e.velocity};
    const bool ok=outputs.attackBatch(e.voice,&note,1,[&](const Outputs::Routed *batch,size_t count){return count==1 && emit(e.sample,true,batch[0].channel,batch[0].pitch,batch[0].velocity,batch[0].retrigger);},true);
    if(!ok){failed=true;++rejected;}return ok;
  }
public:
  uint64_t rejected=0,unmatched=0;
  bool failed=false;
  explicit Runtime(unsigned sampleRate):scheduler(sampleRate),rate(sampleRate){}
  const Configurations &configuration()const{return config;}
  bool hasConfiguration()const{for(const auto &c:config)if(c.id)return true;return false;}
  size_t pending()const{return scheduler.active()+fragments.pending();}
  size_t sources()const{return scheduler.sources.active();}
  void configure(const Configurations &next,bool reset=false){
    for(unsigned j=0;j<config.size();++j)if(config[j].id){bool kept=false;
      for(const auto &c:next)kept|=c.id==config[j].id && c.enabled;
      if(!kept)cancelled[j]=config[j].id;
    }
    config=next;clear|=reset;
  }
  template<class Match,class Emit> bool cancel(uint64_t sample,Match match,Emit emit){
    bool ok=true;
    scheduler.sources.visit(match,[&](native_notes::Token t){if(!releaseDry(t,sample,emit))ok=false;});
    fragments.cancel(match,scheduler);
    if(!scheduler.cancelSources(sample,match,[&](const native_notes::Event&e){return voice(e,emit);}))ok=false;
    failed|=!ok;return ok;
  }
  template<class Emit> void begin(uint64_t sample,Emit emit){
    if(clear){cancel(sample,[](const native_notes::SourceKey&){return true;},emit);fragments.reset();clear=false;}
    for(auto &id:cancelled)if(id){fragments.cancelModule(id,scheduler);scheduler.cancel(sample,[&](const native_notes::Owner&o){return o.module==id;},[&](const native_notes::Event&e){return voice(e,emit);});id=0;}
    for(auto &d:dry)if(d.pending){const auto t=d.token;const auto off=d.off;if(releaseDry(t,sample,emit)){if(const auto *p=scheduler.sources.get(t)){if(p->held)scheduler.sealSource(t,off,sample);}}}
    failed|=scheduler.needsRecovery;
  }
  template<class Emit> bool source(const SourceEvent &e,uint64_t sample,double tempo,Emit emit){
    using namespace native_notes;
    rejected+=fragments.flush(sample,scheduler);
    if(e.action==SourceAction::ChannelClear){outputs.channelCleared(e.key.channel);return true;}
    if(e.action==SourceAction::On){
      auto token=scheduler.sources.begin(e.key,sample);if(!token){++rejected;failed=true;return false;}
      scheduler.sources.retain(token);dry[token.slot]={token,0,true,false};
      unsigned velocity=e.velocity;
      for(unsigned index=0;index<config.size();++index){const auto &c=config[index];if(c.id && c.instrument==e.key.instrument){
        if(c.enabled && c.wet>0 && c.traversal!=Traversal::Forward){
          velocity=unsigned(std::floor(e.velocity*c.dry+.5));
          if(!fragments.add(index,c,token,e.velocity,sample,tempo,scheduler)){++rejected;velocity=e.velocity;}
        }else{Unit unit(rate);unit.configure(c);const auto result=unit.trigger(scheduler,token,e.key.channel,e.key.pitch,e.velocity,sample,tempo);velocity=result.dryVelocity;if(!result.ok)++rejected;}break;
      }}
      const Outputs::Routed note{0,e.key.channel,e.key.pitch,uint8_t(velocity)};
      if(velocity && !outputs.attackBatch(token,&note,1,[&](const Outputs::Routed *batch,size_t count){return count==1 && emit(sample,true,batch[0].channel,batch[0].pitch,batch[0].velocity,false);},false,e.key.origin==Origin::Live || (e.key.origin==Origin::Phrase && e.key.instance!=0))){failed=true;scheduler.cancelSource(token,sample,[&](const Event&v){return voice(v,emit);});releaseDry(token,sample,emit);return false;}
      return true;
    }
    if(e.action==SourceAction::Off){
      auto token=scheduler.sources.oldestHeld(e.key);
      if(!token && !e.key.instance){auto alternate=e.key;alternate.origin=e.key.origin==Origin::Live?Origin::Phrase:Origin::Live;token=scheduler.sources.oldestHeld(alternate);}
      if(!token){++unmatched;return true;}
      if(!releaseDry(token,sample,emit))return false;
      return scheduler.sealSource(token,sample,sample);
    }
    if(e.action==SourceAction::EndInstance){
      scheduler.sources.visitHeld([&](const SourceKey&k){return k.origin==Origin::Phrase && k.instance==e.key.instance;},[&](Token t){if(releaseDry(t,sample,emit))scheduler.sealSource(t,sample,sample);});return !failed;
    }
    if(e.action==SourceAction::StopPhrases){
      // Preserve shared aggregate MONO/ARP dry notes; their native gate owns
      // their actual release. Only their phrase-derived echo tails are stopped.
      fragments.cancel([](const SourceKey&key){return key.origin==Origin::Phrase && !key.instance;},scheduler);
      scheduler.cancel(sample,[](const Owner&o){return o.origin==Origin::Phrase && !o.instance;},[&](const Event&v){return voice(v,emit);});
    }
    const bool cancelled=cancel(sample,[&](const SourceKey &key){
      if(e.action==SourceAction::StopInstance)return key.origin==Origin::Phrase && key.instance==e.key.instance;
      if(e.action==SourceAction::RemoveInstrument)return key.instrument==e.key.instrument;
      if(e.action==SourceAction::StopPhrases)return key.origin==Origin::Phrase && key.instance;
      return e.action==SourceAction::Reset;
    },emit);
    if(e.action==SourceAction::Reset){fragments.reset();}
    return cancelled;
  }
  template<class Emit> void render(uint64_t start,unsigned frames,Emit emit){
    if(frames && start<=UINT64_MAX-frames)rejected+=fragments.flush(start+frames-1,scheduler);
    if(frames)scheduler.render(start,frames,[&](const native_notes::Event&e){return voice(e,emit);});
    failed|=scheduler.needsRecovery;
  }
  // A host has already queued its exhaustive physical panic before calling this.
  void recovered(){scheduler.resetAfterPanic();outputs.resetAfterPanic();fragments.reset();for(auto &d:dry)d=Dry{};failed=false;clear=false;cancelled.fill(0);}
};
}
