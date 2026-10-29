// Native chain lifecycle. Free-time shared capture is the default; the legacy
// synchronized two-bar adapter remains an explicit opt-in.
#pragma once
#include "ysfx.hpp"
#include <cmath>
#include <stdexcept>
struct ChainMode {
  bool enabled, run = false, armed = false, recording = false, error = false;
  int phrase = 0;
  const unsigned timingVersion;
  const bool gridCapture;
  uint64_t length = 0, end = 0, previous = 0, previousClock = 0;
  double bpm = 120;
  int64_t lastFrameGap = 0, lastClockGap = 0;
  EEL_F *phase, *duration, *target, *tempoVar, *runVar, *bad, *overdub,
      *overdubPos, *captureActive, *captureStart, *captureEnd;
  NSEEL_CODEHANDLE align, begin, finish, play, holdPress, holdRelease;
  NSEEL_CODEHANDLE freeArm, freeFinish, freePlay, freeStop, independentPlay, instanceStop;
  EEL_F *instanceId,*instanceGeneration;
  EEL_F *instanceAccepted;
  EEL_F *musicalState, *recordPosition, *overdubArmed, *captureNormalize, *loopLength;
  EEL_F* voiceActive[12]{};EEL_F* directionVoices[12]{};EEL_F* directionVoiceLayers[12]{};
  EEL_F *switchStopPending,*switchStopPosition;
  EEL_F *freeReady,*freeActive,*overflow,*freeOldCount,*freeOldLength,*freeOldTrigger;
  NSEEL_CODEHANDLE rollbackCapture;
  bool freeCaptureSession=false;
  enum class CaptureError { None=0, RecordOverflow=1, ReleaseCapacity=2,
                            InvalidCapture=3, AudioClockGap=4, GridTempoChanged=5 };
  CaptureError errorReason=CaptureError::None;
  uint64_t captureRejected=0, captureOverflows=0;
  bool haveAudioClock=false;
  int errorPhrase=-1;
  NSEEL_CODEHANDLE validateCapture;
  static const char* errorName(CaptureError reason) {
    switch(reason){
      case CaptureError::RecordOverflow:return "record_overflow";
      case CaptureError::ReleaseCapacity:return "release_capacity";
      case CaptureError::InvalidCapture:return "invalid_capture";
      case CaptureError::AudioClockGap:return "audio_clock_discontinuity";
      case CaptureError::GridTempoChanged:return "grid_tempo_changed";
      default:return "none";
    }
  }
  void clearError(){error=false;errorPhrase=-1;errorReason=CaptureError::None;}

  unsigned phraseCapacity=16;
  EEL_F* phraseTriggers[128]{};
  EEL_F* holdAccepted;
  EEL_F* phraseModes[128]{};
  EEL_F* phraseCounts[128]{};EEL_F* phraseDirections[128]{};
  ysfx_t *fx;
  ChainMode(ysfx_t *f, bool active, unsigned version=1, bool grid=false)
      : enabled(active), timingVersion(version), gridCapture(grid), fx(f) {
    phraseCapacity=unsigned(*ysfx_find_var(f,"LAYERS"));
    if (version!=1 && version!=2) throw std::runtime_error("unsupported chain timing version");
    if (active)
      for (unsigned i = 0; i < 4096; ++i)
        *NSEEL_VM_getramptr(f->vm.get(), (phraseCapacity>16?6000000:3000000) + i, nullptr) = 0;
    const auto modeBase=unsigned(*ysfx_find_var(f,"MODE_BASE"));
    for(unsigned i=0;i<phraseCapacity;++i)
      phraseModes[i]=NSEEL_VM_getramptr(f->vm.get(),modeBase+i,nullptr);
    for(unsigned i=0;i<phraseCapacity;++i)phraseCounts[i]=NSEEL_VM_getramptr(f->vm.get(),unsigned(*ysfx_find_var(f,"COUNT_BASE"))+i,nullptr);
    if(auto directions=ysfx_find_var(f,"NATIVE_DIRECTION_SOURCE"))for(unsigned i=0;i<phraseCapacity;++i)phraseDirections[i]=NSEEL_VM_getramptr(f->vm.get(),unsigned(*directions)+i,nullptr);
    if(auto directions=ysfx_find_var(f,"NATIVE_DIRECTION_VOICE"))for(unsigned i=0;i<12;++i){directionVoices[i]=NSEEL_VM_getramptr(f->vm.get(),unsigned(*directions)+i,nullptr);directionVoiceLayers[i]=NSEEL_VM_getramptr(f->vm.get(),unsigned(*ysfx_find_var(f,"VOICE_LAYER_BASE"))+i,nullptr);}
    for(unsigned i=0;i<phraseCapacity;++i)phraseTriggers[i]=NSEEL_VM_getramptr(f->vm.get(),unsigned(*ysfx_find_var(f,"TRIG_BASE"))+i,nullptr);
    if(active && !grid)for(unsigned i=0;i<phraseCapacity*2064;++i)*NSEEL_VM_getramptr(f->vm.get(),(phraseCapacity>16?6200000:3008000)+i,nullptr)=0;
    captureActive = NSEEL_VM_regvar(f->vm.get(), "chain_capture_active");
    captureStart = NSEEL_VM_regvar(f->vm.get(), "chain_capture_start");
    captureEnd = NSEEL_VM_regvar(f->vm.get(), "chain_capture_end");
    *NSEEL_VM_regvar(f->vm.get(),"native_hold_enabled")=active?1:0;
    *NSEEL_VM_regvar(f->vm.get(),"native_phrase_contract")=active?2:0;
    holdAccepted=NSEEL_VM_regvar(f->vm.get(),"chain_hold_accepted");
    *captureActive=0;
    phase = NSEEL_VM_regvar(f->vm.get(), "chain_phase");
    duration = NSEEL_VM_regvar(f->vm.get(), "chain_duration");
    target = NSEEL_VM_regvar(f->vm.get(), "chain_target");
    tempoVar = NSEEL_VM_regvar(f->vm.get(), "chain_bpm");
    runVar = NSEEL_VM_regvar(f->vm.get(), "chain_running");
    bad = NSEEL_VM_regvar(f->vm.get(), "chain_bad");
    overdub = ysfx_find_var(f, "overdub_active");
    overdubPos = ysfx_find_var(f, "overdub_pos");
    musicalState=ysfx_find_var(f,"state");
    recordPosition=ysfx_find_var(f,"record_sample_pos");
    overdubArmed=ysfx_find_var(f,"overdub_armed");
    captureNormalize=NSEEL_VM_regvar(f->vm.get(),"chain_capture_normalize");
    loopLength=ysfx_find_var(f,"loop_len_samples");
    if(*ysfx_find_var(f,"MAX_ONCE_VOICES")!=12)throw std::runtime_error("unsupported shared phrase voice capacity");
    const unsigned voiceBase=unsigned(*ysfx_find_var(f,"VOICE_ACTIVE_BASE"));
    for(unsigned i=0;i<12;++i)voiceActive[i]=NSEEL_VM_getramptr(f->vm.get(),voiceBase+i,nullptr);
    *NSEEL_VM_regvar(f->vm.get(),"native_free_time")=active && !grid?1:0;
    switchStopPending=NSEEL_VM_regvar(f->vm.get(),"native_stop_pending");switchStopPosition=NSEEL_VM_regvar(f->vm.get(),"native_stop_capture_pos");*switchStopPending=0;
    freeReady=NSEEL_VM_regvar(f->vm.get(),"free_record_ready");freeActive=NSEEL_VM_regvar(f->vm.get(),"free_record_active");
    overflow=NSEEL_VM_regvar(f->vm.get(),"record_overflow");
    freeOldCount=NSEEL_VM_regvar(f->vm.get(),"free_old_count");freeOldLength=NSEEL_VM_regvar(f->vm.get(),"free_old_length");freeOldTrigger=NSEEL_VM_regvar(f->vm.get(),"free_old_trigger");
    validateCapture=compile("chain_bad=0;chain_j=0;loop(layer_count(chain_target),chain_a=layer_base(chain_target,chain_j);"
        "chain_s=mem[chain_a+1];chain_n=mem[chain_a+2];chain_v=mem[chain_a+3];"
        "(!(mem[chain_a]>=0 && mem[chain_a]<=chain_duration) || chain_s<128 || chain_s>255 || "
        "(chain_s<240 && (chain_n<0 || chain_n>127 || chain_v<0 || chain_v>127)))?chain_bad=1;chain_j+=1;);");
    rollbackCapture=compile("set_layer_count(chain_target,free_old_count);mem[LEN_BASE+chain_target]=free_old_length;mem[TRIG_BASE+chain_target]=free_old_trigger;free_record_ready=0;free_record_active=0;overdub_active=0;overdub_armed=0;state=STATE_STOPPED;panic_pending=1;");
    instanceAccepted=NSEEL_VM_regvar(f->vm.get(),"chain_instance_accepted");
    instanceId=NSEEL_VM_regvar(f->vm.get(),"chain_instance_id");instanceGeneration=NSEEL_VM_regvar(f->vm.get(),"chain_instance_generation");
    instanceStop=compile("chain_instance_accepted=instance_request_stop(chain_instance_id,chain_instance_generation);");
    independentPlay=compile("chain_instance_accepted=phrase_admit_independent(chain_target,0);");
    freeArm=compile("free_old_count=layer_count(chain_target);free_old_length=mem[LEN_BASE+chain_target];free_old_trigger=mem[TRIG_BASE+chain_target];record_overflow=0;select_phrase_record(chain_target);");
    freeFinish=compile("finish_phrase_record();overdub_active=0;overdub_armed=0;overdub_wait_note=0;");
    freeStop=compile("native_phrase_contract || mem[MODE_BASE+chain_target]<.5?free_loop_stop_mask|=1<<chain_target:native_hold_enqueue(chain_target,0);");
    // Legacy choke emits releases only after ysfx opens its DSP output buffer.
    freePlay=compile("native_phrase_contract && mem[MODE_BASE+chain_target]<.5?"
        "chain_hold_accepted=native_hold_enqueue(chain_target,2):"
        "mem[MODE_BASE+chain_target]<.5?"
        "(layer_count(chain_target)>0 && mem[LEN_BASE+chain_target]>=max(128,samplesblock/8)?(state!=STATE_PLAYING?play_sample_pos=0;mem[FREE_FINISHED_BASE+chain_target]=0;mem[FREE_LOOP_ANCHOR_BASE+chain_target]=play_sample_pos;mem[TRIG_BASE+chain_target]=1;state=STATE_PLAYING;);):"
        "(chain_hold_accepted=native_hold_enqueue(chain_target,1););");
    align = compile(
        "loop_len_samples=chain_duration;slider6=chain_bpm;play_sample_pos="
        "chain_phase;state=chain_running?STATE_PLAYING:STATE_STOPPED;");
    play = compile("layer_count(chain_target)>0?(mem[MODE_BASE+chain_target]<.5?"
        "mem[TRIG_BASE+chain_target]=1:mem[MODE_BASE+chain_target]<1.5?"
        "(native_hold_enqueue(chain_target,1);));");
    holdPress=compile("chain_hold_accepted=native_hold_can_play(chain_target)?native_hold_enqueue(chain_target,1):0;");
    holdRelease=compile("chain_hold_accepted=native_hold_enqueue(chain_target,0);");
    begin = compile(
        "chain_capture_origin=-1;chain_capture_normalize=layer_count(chain_target)==0;mem[LEN_BASE+chain_target]=chain_"
        "duration;mem[TRIG_BASE+chain_target]=layer_count(chain_target)>0;"
        "record_layer=chain_target;overdub_layer=chain_target;overdub_active=1;"
        "overdub_armed=0;overdub_wait_note=0;overdub_pos=chain_phase;"
        "chain_j=0;loop(2048,mem[3002048+chain_j]=0;chain_j+=1;);");
    finish = compile(
        "chain_capture_active=0;overdub_active=0;overdub_armed=0;chain_bad=0;chain_j=0;loop(16,mem[3007400+chain_j]=0;chain_j+=1;);chain_j=0;loop(2048,mem["
        "3000000+chain_j]=0;chain_j+=1;);chain_j=0;loop(layer_count(chain_"
        "target),chain_a=layer_base(chain_target,chain_j);chain_s=mem[chain_a+"
        "1];chain_n=mem[chain_a+2];chain_v=mem[chain_a+3];chain_k=(chain_s&15)*"
        "128+chain_n;(chain_s&240)==176 && chain_n==64?mem[3007400+(chain_s&15)]=chain_v>=64;(chain_s&240)==144 && "
        "chain_v>0?mem[3000000+chain_k]+=1:((chain_s&240)==128 || "
        "((chain_s&240)==144 && "
        "chain_v==0))?mem[3000000+chain_k]=max(0,mem[3000000+chain_k]-1);chain_"
        "j+=1;);chain_j=0;loop(2048,chain_c=mem[3000000+chain_j];loop(chain_c,"
        "layer_count(chain_target)<MAX_EVENTS_PER_LAYER?store_event(chain_"
        "target,max(0,chain_duration-1-(chain_capture_normalize?max(0,chain_capture_origin):0)),128|(chain_j/"
        "128|0),chain_j%128,0,0):chain_bad=1;);chain_j+=1;);mem[TRIG_BASE+"
        "chain_target]=!chain_bad;mem[LEN_BASE+chain_target]=chain_duration;chain_j=0;loop(16,mem[3007400+chain_j]>0?(layer_count(chain_target)<MAX_EVENTS_PER_LAYER?store_event(chain_target,max(0,chain_duration-1),176|chain_j,64,0,0):chain_bad=1;);chain_j+=1;);");
  }
  NSEEL_CODEHANDLE compile(const char *s) {
    std::string source(s);
    if(phraseCapacity>16){
      for(const auto &pair: {std::pair<const char*,const char*>("3000000","6000000"),{"3002048","6002048"},{"3007400","6007400"}}){size_t p=0;while((p=source.find(pair.first,p))!=std::string::npos){source.replace(p,7,pair.second);p+=7;}}
      const std::string old="free_loop_stop_mask|=1<<chain_target";auto p=source.find(old);if(p!=std::string::npos)source.replace(p,old.size(),"(mem[NATIVE_STOP_FLAGS+chain_target]=1;free_loop_stop_mask=1;)");
    }
    auto code = NSEEL_code_compile(fx->vm.get(), source.c_str(), 0);
    if (!code)
      throw std::runtime_error("chain bridge compilation");
    return code;
  }
  ~ChainMode() {
    NSEEL_code_free(align);
    NSEEL_code_free(begin);
    NSEEL_code_free(finish);
    NSEEL_code_free(play);NSEEL_code_free(holdPress);NSEEL_code_free(holdRelease);
    NSEEL_code_free(instanceStop);NSEEL_code_free(independentPlay);NSEEL_code_free(freeArm);NSEEL_code_free(freeFinish);NSEEL_code_free(freePlay);NSEEL_code_free(freeStop);NSEEL_code_free(rollbackCapture);NSEEL_code_free(validateCapture);
  }
  bool stopInstance(uint64_t id,uint64_t generation) {
    *instanceId=double(id);*instanceGeneration=double(generation);NSEEL_code_execute(instanceStop);return *instanceAccepted>.5;
  }
  void observe() {
    if(gridCapture)return;
    recording=*musicalState==2 || *freeActive>.5 || *overdub>.5;
    armed=*musicalState==1 || *freeReady>.5 || *overdubArmed>.5;
    run=false;
    for(unsigned i=0;i<phraseCapacity;++i)
      run=run || (*musicalState==3 && *phraseModes[i]<.5 && *phraseTriggers[i]>.5 && *phraseCounts[i]>0);
    for(unsigned i=0;i<12;++i)run=run || *voiceActive[i]>.5;
    if(!run && !recording && !armed && *musicalState==3)*musicalState=4;
    length=uint64_t(std::max(0.,*loopLength));
  }
  void rejectCapture(CaptureError reason) {
    error=true;errorPhrase=phrase;errorReason=reason;++captureRejected;
    if(reason==CaptureError::RecordOverflow)++captureOverflows;
    NSEEL_code_execute(rollbackCapture);
    *overflow=0;freeCaptureSession=false;observe();
  }
  void finishFree() {
    // A failed append must leave the original source, duration and trigger intact.
    if(freeCaptureSession && *overflow>.5){rejectCapture(CaptureError::RecordOverflow);return;}
    if(freeCaptureSession && (*musicalState==2 || *freeActive>.5 || *freeOldCount>0 || *phraseCounts[phrase]>0)) {
      if(*freeOldCount<=0 && !std::isfinite(*recordPosition)){
        rejectCapture(CaptureError::InvalidCapture);return;
      }
      *duration=*freeOldCount>0?*freeOldLength:std::max(1.,*recordPosition);
      const double count=*phraseCounts[phrase];
      if(!std::isfinite(count) || count<0 || count>2048 || count!=std::floor(count) ||
         !std::isfinite(*duration) || *duration<=0) {
        rejectCapture(CaptureError::InvalidCapture);return;
      }
      NSEEL_code_execute(validateCapture);
      if(*bad>.5){rejectCapture(CaptureError::InvalidCapture);return;}
      *captureNormalize=0;
      NSEEL_code_execute(finish);
      if(*bad>.5){rejectCapture(CaptureError::ReleaseCapacity);return;}
      *phraseTriggers[phrase]=*freeOldTrigger;
    }
    NSEEL_code_execute(freeFinish);
    freeCaptureSession=false;
    observe();
  }
  void finishSwitchStop(){
    if(!gridCapture && *switchStopPending>.5){
      if(freeCaptureSession)*recordPosition=*switchStopPosition;
      cancel();*switchStopPending=0;
    }
  }
  void cancel() {
    if(!gridCapture) {
      finishFree();
      *musicalState=4; // STATE_STOPPED: caller performs existing owned-note PANIC
      armed=recording=run=false;
      return;
    }
    if (recording)
      NSEEL_code_execute(finish);
    armed = recording = run = false;
    *captureActive=0;
  }
  bool command(int action, int selected) {
    if(selected<0 || selected>=int(phraseCapacity) || action<0 || action>7)return false;
    if(action==7){
      *target=selected;NSEEL_code_execute(independentPlay);*target=phrase;observe();return *instanceAccepted>0;
    }
    if(action==6 && gridCapture && *phraseModes[selected]>=1.5)return command(4,selected);
    if(action==6){
      if(gridCapture || ((recording || armed) && selected==phrase))return false;
      *target=selected;NSEEL_code_execute(freeStop);*target=phrase;observe();return true;
    }
    if(!gridCapture) {
      if(action==2 && !recording && !armed){
        if(phraseDirections[selected] && *phraseDirections[selected]>0)return false;
        for(unsigned i=0;i<12;++i)if(directionVoices[i] && *voiceActive[i]>.5 && *directionVoiceLayers[i]==selected && *directionVoices[i]>0)return false;
      }
      observe();
      if((recording || armed) && selected!=phrase && action!=0 && action!=4)return false;
      // STOP finishes the current recording target, not the HTTP placeholder 0.
      if(action!=4 && action!=0){phrase=selected;*target=selected;}
      if(action==5){if(!freeCaptureSession)return false;NSEEL_code_execute(rollbackCapture);freeCaptureSession=false;observe();return true;}
      if(action==0)cancel();
      if(action==2){clearError();if(recording || armed)finishFree();else{freeCaptureSession=true;NSEEL_code_execute(freeArm);}}
      if(action==3)finishFree();
      if(action==1){
        if(recording || armed)finishFree();
        if(*phraseModes[selected]>=1.5){
          NSEEL_code_execute(holdPress);
          if(*holdAccepted<.5)return false;
        }else {
          *holdAccepted=1;NSEEL_code_execute(freePlay);
          if(*holdAccepted<.5)return false;
        }
      }
      if(action==4){
        *target=selected;NSEEL_code_execute(holdRelease);*target=phrase;
        if(*holdAccepted<.5)return false;
      }
      observe();
      return true;
    }
    if ((recording || armed) && selected != phrase && action != 0 && action != 4) return false;
    if(action==4 || (action==1 && *phraseModes[selected]>=1.5)) {
      if(action==1){if(recording)NSEEL_code_execute(finish);recording=armed=false;phrase=selected;}
      *target=selected;
      NSEEL_code_execute(action==4?holdRelease:holdPress);
      *target=phrase;
      if(*holdAccepted<.5)return false;
      if(action==1)run=true;
      return true;
    }
    if (action == 2 && (recording || armed))
      return false;
    if (!recording && !armed)
      phrase = selected;
    *target = phrase;
    if (action == 0)
      cancel();
    if (action == 1) {
      if (recording)
        NSEEL_code_execute(finish);
      recording = armed = false;
      run = true;
      *target = phrase;
      NSEEL_code_execute(play);
    }
    if (action == 2) {
      armed = true;
      run = true;
      clearError();
    }
    if (action == 3 && recording) {
      NSEEL_code_execute(finish);
      recording = false;
      error = *bad > .5;
      if (error){
        run = false;errorPhrase=phrase;errorReason=CaptureError::ReleaseCapacity;
      }
    }
    if (action == 3 && armed)
      armed = false;
    return true;
  }
  bool tick(uint64_t frame, unsigned frames, unsigned rate, bool rolling,
            double tempo, uint64_t clock = UINT64_MAX) {
    if (!enabled)
      return false;
    if(!gridCapture) {
      observe();
      if(*overflow>.5){finishFree();*overflow=0;return true;}
      if(freeCaptureSession && *freeOldCount>0 && !recording && !armed)finishFree();
      // Source timestamps already come from the shared sample counter. Only
      // the continuous JACK audio-cycle clock can diagnose missing callbacks;
      // transport STOP/START/seek is a separate domain, never a capture origin.
      bpm=tempo;
      const uint64_t audio=clock==UINT64_MAX?(haveAudioClock?previousClock:0):clock;
      // jack_nframes_t wraps at 32 bits. Compare modulo that domain so one
      // ordinary wrap after a long performance is not a false recording error.
      const bool gap=haveAudioClock && uint32_t(audio)!=uint32_t(previousClock);
      bool interrupted=false;
      if(gap) {
        lastFrameGap=int64_t(frame)-int64_t(previous);
        lastClockGap=int64_t(int32_t(uint32_t(audio)-uint32_t(previousClock)));
        if(recording){rejectCapture(CaptureError::AudioClockGap);interrupted=true;}
        else if(run){cancel();interrupted=true;}
      }
      previous=rolling?frame+frames:0;
      previousClock=audio+frames;haveAudioClock=true;
      return interrupted;
    }
    // Optional grid capture retains its transport-aligned timing V1/V2 policy.
    if(clock==UINT64_MAX)clock=0;
    bool failed = false;
    uint64_t proposed = timingVersion==1
        ? uint64_t(std::llround(rate * 480.0 / tempo / frames))*frames
        : uint64_t(std::llround(rate * 480.0 / tempo)); // nearest sample, two 4/4 bars
    proposed = std::max<uint64_t>(timingVersion==1?frames:1, proposed);
    bool gap = previous && frame != previous;
    bool missed = gap && clock && frame - previous == clock - previousClock;
    bool discontinuity = gap && !missed;
    bool changed = length && (proposed != length || tempo != bpm);
    bool stopped = ((!rolling && previous) || discontinuity || changed ||
                    (missed && recording)) &&
                   (run || recording || armed);
    if (stopped) {
      lastFrameGap = int64_t(frame) - int64_t(previous);
      lastClockGap = int64_t(clock) - int64_t(previousClock);
      const bool interruptedRecording = recording;
      cancel();
      error = changed || (missed && interruptedRecording);
      if(error){errorPhrase=phrase;errorReason=changed?CaptureError::GridTempoChanged:CaptureError::AudioClockGap;}
    }
    if (!length) {
      length = proposed;
      bpm = tempo;
    }
    // A tempo change never silently retimes recorded data. Recreate/load at the
    // desired tempo.
    *target = phrase;
    *duration = double(length);
    *phase = double((timingVersion==1?frame/frames*frames:frame) % length);
    *tempoVar = bpm;
    *runVar = rolling && run;
    NSEEL_code_execute(align);
    if (recording && frame >= end) {
      NSEEL_code_execute(finish);
      recording = false;
      failed = error = *bad > .5;
      if(error){errorPhrase=phrase;errorReason=CaptureError::ReleaseCapacity;}
    }
    const uint64_t boundaryOffset = uint64_t(*phase)==0?0:length-uint64_t(*phase);
    if (armed && rolling && (timingVersion==1?*phase==0:boundaryOffset<frames)) {
      armed = false;
      recording = true;
      end = timingVersion==1?frame-uint64_t(*phase)+length:frame+boundaryOffset+length;
      NSEEL_code_execute(begin);
    }
    if (recording) {
      *overdub = 1;
      *overdubPos = timingVersion==1?*phase:double(frame)-double(end-length);
      *captureActive=1;
      *captureStart=timingVersion==2?std::max(0.,double(end-length)-double(frame)):0;
      *captureEnd=timingVersion==2?std::min(double(frames),double(end)-double(frame)):frames;
    }
    previous = rolling ? frame + frames : 0;
    previousClock = clock ? clock + frames : 0;
    return stopped || failed || (missed && run);
  }
};
