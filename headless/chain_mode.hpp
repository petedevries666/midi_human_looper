// Opt-in Zynthian chain transport. Existing free-time REAPER/standalone
// behavior is untouched.
#pragma once
#include "ysfx.hpp"
#include <cmath>
#include <stdexcept>
struct ChainMode {
  bool enabled, run = false, armed = false, recording = false, error = false;
  int phrase = 0;
  uint64_t length = 0, end = 0, previous = 0, previousClock = 0;
  double bpm = 120;
  int64_t lastFrameGap = 0, lastClockGap = 0;
  EEL_F *phase, *duration, *target, *tempoVar, *runVar, *bad, *overdub,
      *overdubPos;
  NSEEL_CODEHANDLE align, begin, finish, play;
  ysfx_t *fx;
  ChainMode(ysfx_t *f, bool active) : enabled(active), fx(f) {
    if (active)
      for (unsigned i = 0; i < 2048; ++i)
        *NSEEL_VM_getramptr(f->vm.get(), 3000000 + i, nullptr) = 0;
    phase = NSEEL_VM_regvar(f->vm.get(), "chain_phase");
    duration = NSEEL_VM_regvar(f->vm.get(), "chain_duration");
    target = NSEEL_VM_regvar(f->vm.get(), "chain_target");
    tempoVar = NSEEL_VM_regvar(f->vm.get(), "chain_bpm");
    runVar = NSEEL_VM_regvar(f->vm.get(), "chain_running");
    bad = NSEEL_VM_regvar(f->vm.get(), "chain_bad");
    overdub = ysfx_find_var(f, "overdub_active");
    overdubPos = ysfx_find_var(f, "overdub_pos");
    align = compile(
        "loop_len_samples=chain_duration;slider6=chain_bpm;play_sample_pos="
        "chain_phase;state=chain_running?STATE_PLAYING:STATE_STOPPED;");
    play = compile("mem[TRIG_BASE+chain_target]=layer_count(chain_target)>0;");
    begin = compile(
        "mem[MODE_BASE+chain_target]=0;mem[LEN_BASE+chain_target]=chain_"
        "duration;mem[TRIG_BASE+chain_target]=layer_count(chain_target)>0;"
        "record_layer=chain_target;overdub_layer=chain_target;overdub_active=1;"
        "overdub_armed=0;overdub_wait_note=0;overdub_pos=chain_phase;");
    finish = compile(
        "overdub_active=0;overdub_armed=0;chain_bad=0;chain_j=0;loop(2048,mem["
        "3000000+chain_j]=0;chain_j+=1;);chain_j=0;loop(layer_count(chain_"
        "target),chain_a=layer_base(chain_target,chain_j);chain_s=mem[chain_a+"
        "1];chain_n=mem[chain_a+2];chain_v=mem[chain_a+3];chain_k=(chain_s&15)*"
        "128+chain_n;(chain_s&240)==144 && "
        "chain_v>0?mem[3000000+chain_k]+=1:((chain_s&240)==128 || "
        "((chain_s&240)==144 && "
        "chain_v==0))?mem[3000000+chain_k]=max(0,mem[3000000+chain_k]-1);chain_"
        "j+=1;);chain_j=0;loop(2048,chain_c=mem[3000000+chain_j];loop(chain_c,"
        "layer_count(chain_target)<MAX_EVENTS_PER_LAYER?store_event(chain_"
        "target,chain_duration-1,128|(chain_j/"
        "128|0),chain_j%128,0,0):chain_bad=1;);chain_j+=1;);mem[TRIG_BASE+"
        "chain_target]=!chain_bad;mem[LEN_BASE+chain_target]=chain_duration;");
  }
  NSEEL_CODEHANDLE compile(const char *s) {
    auto code = NSEEL_code_compile(fx->vm.get(), s, 0);
    if (!code)
      throw std::runtime_error("chain bridge compilation");
    return code;
  }
  ~ChainMode() {
    NSEEL_code_free(align);
    NSEEL_code_free(begin);
    NSEEL_code_free(finish);
    NSEEL_code_free(play);
  }
  void cancel() {
    if (recording)
      NSEEL_code_execute(finish);
    armed = recording = run = false;
  }
  bool command(int action, int selected) {
    if ((recording || armed) && selected != phrase && action != 0)
      return false;
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
      error = false;
    }
    if (action == 3 && recording) {
      NSEEL_code_execute(finish);
      recording = false;
      error = *bad > .5;
      if (error)
        run = false;
    }
    if (action == 3 && armed)
      armed = false;
    return true;
  }
  bool tick(uint64_t frame, unsigned frames, unsigned rate, bool rolling,
            double tempo, uint64_t clock = 0) {
    if (!enabled)
      return false;
    bool failed = false;
    uint64_t proposed = uint64_t(std::llround(rate * 480.0 / tempo / frames)) *
                        frames; // two 4/4 bars
    proposed = std::max<uint64_t>(frames, proposed);
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
    }
    if (!length) {
      length = proposed;
      bpm = tempo;
    }
    // A tempo change never silently retimes recorded data. Recreate/load at the
    // desired tempo.
    *target = phrase;
    *duration = double(length);
    *phase = double((frame / frames * frames) % length);
    *tempoVar = bpm;
    *runVar = rolling && run;
    NSEEL_code_execute(align);
    if (recording && frame >= end) {
      NSEEL_code_execute(finish);
      recording = false;
      failed = error = *bad > .5;
    }
    if (armed && rolling && *phase == 0) {
      armed = false;
      recording = true;
      end = frame - uint64_t(*phase) + length;
      NSEEL_code_execute(begin);
    }
    if (recording) {
      *overdub = 1;
      *overdubPos = *phase;
    }
    previous = rolling ? frame + frames : 0;
    previousClock = clock ? clock + frames : 0;
    return stopped || failed || (missed && run);
  }
};
