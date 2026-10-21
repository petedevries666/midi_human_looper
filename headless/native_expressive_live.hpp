#pragma once
// Experimental native live-note bridge for the expressive pair foundation.
// It uses the ECHOCITY scheduler's source generation and captured output leases.
// Not connected to the production instrument chain or physical JACK graph.
#include "native_expressive_transformers.hpp"
namespace expressive {
template<size_t Voices=256,size_t Sources=512> class LiveRuntime {
  native_notes::Scheduler<Voices,Sources> queue;
  native_notes::Outputs<Voices*2> outputs;
  uint32_t rate;
  uint64_t ordinal=0;
public:
  uint64_t rejected=0,clamped=0,unmatched=0;
  bool recoveryNeeded=false;
  explicit LiveRuntime(uint32_t sampleRate):queue(sampleRate),rate(sampleRate){}
  size_t active()const{return queue.active();}
  size_t sounding()const{return outputs.active();}
  size_t heldSources()const{return queue.sources.active();}
  // Causality: negative jitter is clamped at arrival. Positive jitter may
  // cross audio blocks; releases use the SAME captured delay as their attack.
  bool noteOn(native_notes::SourceKey key,uint32_t module,uint64_t now,
              uint8_t velocity,const Identity& identity,
              const Humanizer& human,const VelocityCurve& curve){
    if(!key.instrument || key.channel>15 || key.pitch>127 || !module ||
       !velocity || velocity>127 || !human.valid() || !curve.valid() ||
       rate<8000 || rate>384000){++rejected;return false;}
    const int64_t shift=delay(human,identity,rate);
    const uint64_t d=shift>0?uint64_t(shift):0;
    if(shift<0)++clamped;
    if(d>queue.maxHorizon() || now>UINT64_MAX-queue.maxHorizon() ||
       ordinal==UINT64_MAX){++rejected;return false;}
    auto source=queue.sources.begin(key,now);
    if(!source){++rejected;return false;}
    native_notes::Pair p{};
    p.owner={key.instrument,module,0,key.origin,key.instance};
    p.start=now+d;
    p.end=now+queue.maxHorizon(); // watchdog until paired source release
    p.channel=key.channel;p.pitch=key.pitch;
    p.velocity=curve.apply(expressive::velocity(human,identity,velocity));
    p.followSource=true;p.durationScale=1;
    if(!queue.admit(source,&p,1,now)){
      queue.sources.close(source,now);queue.sources.retire(source);
      ++rejected;return false;
    }
    ++ordinal;
    return true;
  }
  bool noteOff(native_notes::SourceKey key,uint64_t now){
    auto source=queue.sources.oldestHeld(key);
    if(!source){++unmatched;return false;}
    if(!queue.sealSource(source,now,now)){++rejected;return false;}
    return true;
  }
  template<class Emit> void render(uint64_t start,uint32_t frames,Emit emit){
    queue.render(start,frames,[&](const native_notes::Event& e){
      if(e.on){
        const typename native_notes::Outputs<Voices*2>::Routed note{0,e.channel,e.pitch,e.velocity};
        return outputs.attackBatch(e.voice,&note,1,[&](const auto* batch,size_t count){
          return count==1 && emit(e.sample,true,batch[0].channel,batch[0].pitch,batch[0].velocity);
        });
      }
      return outputs.release(e.voice,[&](bool on,uint8_t ch,uint8_t pitch,uint8_t vel){
        return emit(e.sample,on,ch,pitch,vel);
      });
    });
    recoveryNeeded|=queue.needsRecovery;
  }
  template<class Emit> bool cancel(uint64_t now,uint32_t instrument,uint32_t module,Emit emit){
    bool ok=queue.cancel(now,[&](const native_notes::Owner& owner){
      return (!instrument || owner.instrument==instrument) && (!module || owner.module==module);
    },[&](const native_notes::Event& e){
      return outputs.release(e.voice,[&](bool on,uint8_t ch,uint8_t pitch,uint8_t vel){
        return emit(now,on,ch,pitch,vel);
      });
    });
    if(!module)queue.sources.closeMatching(now,[&](const native_notes::SourceKey& key){
      return !instrument || key.instrument==instrument;
    });
    recoveryNeeded|=!ok;
    return ok;
  }
  // Caller must actually transmit the global panic before resetting leases.
  void recovered(){queue.resetAfterPanic();outputs.resetAfterPanic();recoveryNeeded=false;}
};
}
