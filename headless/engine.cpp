// Native JACK MIDI host. All EEL and ownership run on one processing thread.
// Disk, sockets and JSON are confined to the control worker.
#include "chain_mode.hpp"
#include "controller_wire.hpp"
#include "conductor_wire.hpp"
#include "conductor_execution.hpp"
#include "movement_engine.hpp"
#include "reveal_engine.hpp"
#include "realtime_trace.hpp"
#include "parameter_registry.hpp"
#include "panic_sweep.hpp"
#include "echocity_runtime.hpp"
#include "snapshot_wire.hpp"
#include "native_expressive_config.hpp"
#include "ysfx.hpp"
#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cmath>
#include <csignal>
#include <cstring>
#include <fcntl.h>
#include <functional>
#include <iomanip>
#include <iostream>
#include <jack/jack.h>
#include <jack/midiport.h>
#include <poll.h>
#include <sstream>
#include <string>
#include <sys/random.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/un.h>
#include <thread>
#include <unistd.h>
#include <vector>

#ifndef MBMF_BUILD_REVISION
#define MBMF_BUILD_REVISION "unknown"
#endif

template <class T, unsigned N> class Queue {
  std::array<T, N> slots{};
  std::atomic<uint64_t> written{0}, read{0};

public:
  bool push(const T &v) {
    auto w = written.load(std::memory_order_relaxed);
    if (w - read.load(std::memory_order_acquire) >= N)
      return false;
    slots[w % N] = v;
    written.store(w + 1, std::memory_order_release);
    return true;
  }
  bool pop(T &v) {
    auto r = read.load(std::memory_order_relaxed);
    if (r == written.load(std::memory_order_acquire))
      return false;
    v = slots[r % N];
    read.store(r + 1, std::memory_order_release);
    return true;
  }
  unsigned free() const {
    return N - unsigned(written.load(std::memory_order_acquire) -
                        read.load(std::memory_order_acquire));
  }
};
struct ParameterChange {
  int kind = 0;
  double value = 0;
};
struct RequestFields {
  echocity::Configurations echoConfig{};
  expressive::Configuration expressiveConfig{};
  uint64_t id = 0, session = 0, instanceId=0, instanceGeneration=0;
  int op = 0, target = 0, arg = 0, revision = 1, ch = 0, note = 0, value = 0;
  int module = 0, count = 0;
  char snapshotName[49]{};
  double macroPosition = 0;
  double snapshotSeconds = 2;
  int snapshotEase = 1, snapshotSwitch = 2;
  std::array<ParameterChange, 5> parameters{};
  std::array<int,101> switchSettings{};bool hasLongHold=false;
  controller::Binding binding;
  controller::Configuration controllerConfig;
};
struct Request : RequestFields {
  performance::Configuration snapshotConfig;
  Request &operator=(const Request &other) {
    static_cast<RequestFields &>(*this)=static_cast<const RequestFields &>(other);
    // The large saved-snapshot payload is irrelevant to ordinary telemetry,
    // MIDI edges and mixer commands. Never copy its megabyte on those callbacks.
    if(other.op==5 || other.op==27 || other.op==42)
      snapshotConfig=other.snapshotConfig;
    return *this;
  }
};
struct Switch {
  int conductorQueued=0,conductorStep=0,conductorSteps=0,conductorResult=0,conductorMissing=0,conductorAdmitted=0;
  int slot=0,id = 0, on = 0, type = 0, kind = 0, ch = 0, num = 0, length = 0, step = 0, actionCount = 0, lastAction = 0, result = 0;
  bool charging=false;double charge=0;int chargeStep=0;
  char name[17]{};int longHoldMs=0,longHoldAction=0,longHoldTarget=0;
  std::array<int,18> settings{};std::array<int,64> sequence{};
};
struct Instrument {
  int id = 0, on = 0, input = 0, output = 0, level = 0;
  std::array<double,2> hostMixer{};
  std::array<uint64_t,2> hostMixerSequence{};
  char name[17]{};
  std::array<int, 6> transformerIds{}, transformerTypes{}, transformerOn{};
  std::array<std::array<double, 5>, 6> transformerValues{},transformerPending{};
  std::array<std::array<int, 5>, 6> transformerKinds{},
      transformerAssignments{};
  std::array<int, 6> parameterCounts{};
  int transformerCount = 0;
  bool serialPitch = false;
};
struct Phrase {
  char name[17]{};
  int events = 0, mode = 0, state = 0;
  double time = 1, velocityDecay = .8, baseVelocity = 1;
  int mute = 0, solo = 0, triggerNote = -1, triggerChannel = 0, outputChannel = 0;
};
struct Snapshot {
  echocity::Configurations echoConfig{};
  expressive::Configuration expressiveConfig{};
  bool echoAvailable=false;
  unsigned echoPending=0,echoSources=0;
  uint64_t echoRejected=0;
  uint64_t expressiveRejected=0,expressiveClamped=0;
  unsigned expressivePending=0;
  unsigned switchLearnTarget=0;bool switchLearnConflict=false;
  uint64_t samples = 0, blocks = 0, midi = 0, late = 0, last_sample = 0;
  int revision = 1;
  unsigned pendingOutput = 0;
  int chainPhrase=0,chainErrorPhrase=-1,chainErrorCode=0;
  uint64_t captureRejected=0,captureOverflows=0;
  unsigned chainTimingVersion=1;
  bool chain = false, chainGridCapture = false, chainRun = false, chainArmed = false, chainRecord = false,
       chainError = false;
  uint64_t chainFrame = 0, chainLength = 0;
  double chainBpm = 120;
  int64_t chainFrameGap = 0, chainClockGap = 0;
  int backend = 0, sampleRate = 48000, blockSize = 128;
  uint64_t outputOverflow = 0;
  // Single processing-thread writers, copied through the existing Snapshot queue.
  // midi/midiCount retains its historical pre-JACK semantics.
  uint64_t midiReceived=0,midiInputAccepted=0,midiGenerated=0,midiQueued=0,
           midiWritten=0,midiDropped=0,midiWriteFailures=0,midiRecoveries=0;
  int active = 0, last_status = 0, last_note = 0, last_value = 0;
  double max_us = 0;
  std::array<std::array<double,14>,140> instances{};
  int instanceError=0;uint64_t instanceRejected=0;
  unsigned revealCount=0;std::array<uint64_t,12> revealIds{};
  std::array<bool,12> revealHidden{};std::array<unsigned,12> revealMasks{};
  std::array<std::array<unsigned,16>,12> revealVolumes{};
  std::array<Switch, 64> switches{};
  std::array<Instrument, 8> instruments{};
  std::array<Phrase, 128> phrases{};
  unsigned phraseCapacity=16,switchCapacity=16,schema=7;
  controller::Configuration controllerConfig;
  uint32_t learnTarget = 0;
  bool learnCommand = false;
  controller::Source learnCandidate;
  int learnConflict = 0;
  std::array<double, 32> effective{};
  std::array<uint32_t, 32> owners{};
  std::array<bool, 32> returning{}, pickup{};
  unsigned performanceCount = 0, performanceSkipped = 0;
  unsigned movementActive=0,movementRejected=0,movementEmitted=0,movementCancelled=0,movementRunningCount=0;
  std::array<std::array<char,37>,512> movementIds{};
  std::array<double,512> movementProgress{};
  uint32_t performanceSelected = 0, performanceTarget = 0;
  double performanceProgress = 1;
  std::array<uint32_t, 16> performanceIds{}, performanceSizes{};
  std::array<std::array<char, 49>, 16> performanceNames{};
  std::array<double, 16> performanceSeconds{};
  std::array<int, 16> performanceEase{}, performanceSwitch{};
  std::array<bool, 16> performanceDirty{};
  std::array<performance::SwitchAction, 48> snapshotActions{};
  performance::AB ab;
  unsigned abSkipped = 0, abOverridden = 0;
};
struct Reply {
  int legacySource=0,legacyCount=0;
  std::array<std::array<double,3>,16> legacyPoints{};
  uint64_t id = 0;
  int status = 0;
  Snapshot state;
  performance::Record detail;
  int detailRevision = 0;
  Reply &operator=(const Reply &other) {
    legacySource=other.legacySource;legacyCount=other.legacyCount;
    legacyPoints=other.legacyPoints;id=other.id;status=other.status;
    state=other.state;detailRevision=other.detailRevision;
    if(detailRevision)detail=other.detail;
    return *this;
  }
};
static uint64_t engineSession = 0;
static std::atomic<bool> running{true};
static_assert(
    ATOMIC_LLONG_LOCK_FREE == 2,
    "64-bit atomics must be lock-free; verify ARMHF toolchain or use ARM64");
static_assert(ATOMIC_BOOL_LOCK_FREE == 2, "signal flag must be lock free");
static void stop(int) { running = 0; }
static double variable(ysfx_t *fx, const char *name) {
  auto p = ysfx_find_var(fx, name);
  if (!p)
    throw std::runtime_error(name);
  return *p;
}
static EEL_F *cell(ysfx_t *fx, unsigned address) {
  auto p = NSEEL_VM_getramptr(fx->vm.get(), address, nullptr);
  if (!p)
    throw std::runtime_error("RAM allocation");
  return p;
}
static void execute(ysfx_t *fx, const char *text) {
  auto p = NSEEL_code_compile(fx->vm.get(), text, 0);
  if (!p)
    throw std::runtime_error(NSEEL_code_getcodeerror(fx->vm.get()));
  NSEEL_code_execute(p);
  NSEEL_code_free(p);
}
struct Model {
  unsigned phraseCapacity=16,switchCapacity=16,schema=7;
  std::array<std::array<EEL_F*,128>,64> switchFields;
  std::array<std::array<EEL_F*,8>,64> conductorFields;
  std::array<std::array<EEL_F*,5>,64> chargeFields;std::array<EEL_F*,64> conductorQueued;std::array<double*,64> switchPressed;
  EEL_F *musicalState,*recordLayer,*odLayer,*odActive,*odArmed,*freeActive,*freeReady,*freeError;
  std::array<EEL_F*,12> voiceActive,voiceLayer;
  std::array<EEL_F*,128> phraseTriggers,phraseFinished;
  struct CurvePointers{double *count=nullptr;std::array<std::array<double*,3>,16> points{};};
  std::array<std::array<std::array<CurvePointers,5>,12>,8> legacyCurves;
  std::array<CurvePointers,8> levelCurves;
  mutable std::array<std::array<double,2>,8> hostMixer{};
  mutable std::array<std::array<uint64_t,2>,8> hostMixerSequence{};
  mutable double abPosition = 0;
  mutable std::atomic<bool> abRestorePending{false};
  std::array<std::array<double*,14>,140> instances;
  double *instanceError,*instanceRejected,*instanceFault;
  std::array<std::array<double *, 28>, 64> sw;
  std::array<std::array<double *, 22>, 8> inst;
  std::array<std::array<double *, 11>, 128> phrase;
  std::array<std::array<double *, 16>, 128> phraseNames;
  std::array<double *, 8> tfCount, levelAssignment, levelPending;
  std::array<std::array<double *, 6>, 8> tfCodes;
  std::array<std::array<double *, 12>, 8> tfIds, tfTypes;
  std::array<std::array<std::array<double *, 5>, 12>, 8> values, assignments,
      pendingValues;
  std::array<std::array<std::array<int, 5>, 12>, 8> kinds, curveIndices;
  std::array<int, 8> levelCurveIndices;
  mutable expressive::Configuration expressiveSettings{};
  expressive::Configuration expressiveConfiguration() const { return expressiveSettings; }
  bool expressiveTargets(const expressive::Configuration &config) const {
    for(const auto &setting:config) if(setting.instrument) {
      bool found=false;
      for(unsigned i=0;i<8;++i)
        found |= *inst[i][0]>.5 && unsigned(*inst[i][1])==setting.instrument;
      if(!found)return false;
    }
    return true;
  }
  void loadExpressive(const expressive::Configuration &config) { expressiveSettings=config; }
  void initParameters(ysfx_t *fx) {
    auto i = NSEEL_VM_regvar(fx->vm.get(), "remote_pi"),
         c = NSEEL_VM_regvar(fx->vm.get(), "remote_pc"),
         r = NSEEL_VM_regvar(fx->vm.get(), "remote_pr"),
         k = NSEEL_VM_regvar(fx->vm.get(), "remote_pk"),
         a = NSEEL_VM_regvar(fx->vm.get(), "remote_pa"),
         b = NSEEL_VM_regvar(fx->vm.get(), "remote_pb"),
         pending = NSEEL_VM_regvar(fx->vm.get(), "remote_pending"),
         ti = NSEEL_VM_regvar(fx->vm.get(), "remote_pti");
    auto lookup = NSEEL_code_compile(
        fx->vm.get(),
        "remote_pk=param_editor_kind(transform_type(remote_pi,remote_pc),"
        "remote_pr);remote_pti=remote_pc<7?param_ti(remote_pi,remote_pk):cc_ti("
        "cc_index(remote_pi,remote_pc),remote_pr);remote_pa=remote_pc<7?param_"
        "addr(remote_pi,remote_pk):cc_cfg(cc_index(remote_pi,remote_pc))+("
        "remote_pr==0?2:remote_pr==1?1:3);remote_pb=exp_assign_addr(remote_pti)"
        ";"
        "remote_pending=(remote_pk>=0 || "
        "remote_pc>=7)?param_pending_addr(remote_pti):0;",
        0);
    if (!lookup)
      throw std::runtime_error("parameter descriptors");
    auto gx=NSEEL_VM_regvar(fx->vm.get(),"remote_gx"),gy=NSEEL_VM_regvar(fx->vm.get(),"remote_gy"),gb=NSEEL_VM_regvar(fx->vm.get(),"remote_gb"),gc=NSEEL_VM_regvar(fx->vm.get(),"remote_gc");
    auto geometry=NSEEL_code_compile(fx->vm.get(),"remote_gx=exp_x_addr(remote_pti);remote_gy=exp_y_addr(remote_pti);remote_gb=exp_bend_addr(remote_pti);remote_gc=exp_count_addr(remote_pti);",0);
    if(!geometry)throw std::runtime_error("curve bridge");
    auto cacheCurve=[&](CurvePointers &curve){NSEEL_code_execute(geometry);curve.count=cell(fx,unsigned(*gc));for(unsigned j=0;j<16;++j){curve.points[j][0]=cell(fx,unsigned(*gx)+j);curve.points[j][1]=cell(fx,unsigned(*gy)+j);curve.points[j][2]=cell(fx,unsigned(*gb)+j);}};

    for (unsigned gi = 0; gi < 8; ++gi)
      for (unsigned code = 1; code < 12; ++code)
        for (unsigned row = 0; row < 5; ++row) {
          *i = gi;
          *c = code;
          *r = row;
          NSEEL_code_execute(lookup);
          cacheCurve(legacyCurves[gi][code][row]);
          kinds[gi][code][row] = int(*k);
          curveIndices[gi][code][row] = int(*ti);
          values[gi][code][row] = cell(fx, unsigned(*a));
          assignments[gi][code][row] = cell(fx, unsigned(*b));
          pendingValues[gi][code][row] =
              *pending ? cell(fx, unsigned(*pending)) : nullptr;
        }
    NSEEL_code_free(lookup);
    auto level =
        NSEEL_code_compile(fx->vm.get(),
                           "remote_pti=param_ti(remote_pi,1);remote_pb=exp_"
                           "assign_addr(remote_pti);remote_pending=param_"
                           "pending_addr(param_ti(remote_pi,1));",
                           0);
    if (!level)
      throw std::runtime_error("level assignment bridge");
    for (unsigned gi = 0; gi < 8; ++gi) {
      *i = gi;
      NSEEL_code_execute(level);
      cacheCurve(levelCurves[gi]);
      levelCurveIndices[gi] = int(*ti);
      levelAssignment[gi] = cell(fx, unsigned(*b));
      levelPending[gi] = cell(fx, unsigned(*pending));
    }
    NSEEL_code_free(level);NSEEL_code_free(geometry);
  }
  explicit Model(ysfx_t *fx) {
    phraseCapacity=unsigned(variable(fx,"LAYERS"));switchCapacity=unsigned(variable(fx,"SW_COUNT"));schema=unsigned(variable(fx,"IO_SCHEMA"));
    if(phraseCapacity>128||switchCapacity>64)throw std::runtime_error("native capacity exceeds compiled bounds");
    if(variable(fx,"MAX_ONCE_VOICES")!=voiceActive.size())throw std::runtime_error("shared voice capacity mismatch");
    musicalState=ysfx_find_var(fx,"state");recordLayer=ysfx_find_var(fx,"record_layer");odLayer=ysfx_find_var(fx,"overdub_layer");odActive=ysfx_find_var(fx,"overdub_active");odArmed=ysfx_find_var(fx,"overdub_armed");freeActive=ysfx_find_var(fx,"free_record_active");freeReady=ysfx_find_var(fx,"free_record_ready");freeError=ysfx_find_var(fx,"free_play_error");
    auto instanceBase=unsigned(variable(fx,"INSTANCE_BASE"));
    for(unsigned j=0;j<12+phraseCapacity;++j)for(unsigned k=0;k<14;++k)instances[j][k]=cell(fx,instanceBase+j*48+k);
    instanceFault=NSEEL_VM_regvar(fx->vm.get(),"instance_output_fault");
    instanceError=NSEEL_VM_regvar(fx->vm.get(),"instance_error");instanceRejected=NSEEL_VM_regvar(fx->vm.get(),"instance_rejected");
    for(unsigned j=0;j<12;++j){voiceActive[j]=cell(fx,unsigned(variable(fx,"VOICE_ACTIVE_BASE"))+j);voiceLayer[j]=cell(fx,unsigned(variable(fx,"VOICE_LAYER_BASE"))+j);}
    for(unsigned j=0;j<phraseCapacity;++j){phraseTriggers[j]=cell(fx,unsigned(variable(fx,"TRIG_BASE"))+j);phraseFinished[j]=cell(fx,unsigned(variable(fx,"FREE_FINISHED_BASE"))+j);}

    auto gi = NSEEL_VM_regvar(fx->vm.get(), "remote_model_i"),
         c = NSEEL_VM_regvar(fx->vm.get(), "remote_model_c"),
         a = NSEEL_VM_regvar(fx->vm.get(), "remote_model_a"),
         b = NSEEL_VM_regvar(fx->vm.get(), "remote_model_b");
    auto lookup = NSEEL_code_compile(
        fx->vm.get(),
        "remote_model_a=engine_addr(INST_TRANSFORM_COUNT_BASE,remote_model_i);"
        "remote_model_b=engine_addr(INST_TRANSFORM_TYPE_BASE,remote_model_i*"
        "TRANSFORM_SLOTS+remote_model_c);",
        0);
    auto identity = NSEEL_code_compile(
        fx->vm.get(),
        "remote_model_a=remote_model_c<6?engine_addr(TF_PRIMARY_IDS,remote_"
        "model_i*TRANSFORM_TYPES+remote_model_c-1):remote_model_c==6?primary_"
        "cc_id_addr(remote_model_i):cc_cfg(cc_index(remote_model_i,remote_"
        "model_c));remote_model_b=remote_model_c>=7?tf_record(cc_index(remote_"
        "model_i,remote_model_c)):0;",
        0);
    if (!lookup || !identity)
      throw std::runtime_error("model bridge");
    for (unsigned i = 0; i < 8; ++i) {
      *gi = i;
      for (unsigned j = 0; j < 6; ++j) {
        *c = j;
        NSEEL_code_execute(lookup);
        tfCount[i] = cell(fx, unsigned(*a));
        tfCodes[i][j] = cell(fx, unsigned(*b));
      }
      for (unsigned j = 1; j < 12; ++j) {
        *c = j;
        NSEEL_code_execute(identity);
        tfIds[i][j] = cell(fx, unsigned(*a));
        tfTypes[i][j] = j >= 7 ? cell(fx, unsigned(*b)) : nullptr;
      }
    }
    NSEEL_code_free(lookup);
    NSEEL_code_free(identity);
    initParameters(fx);
    for (unsigned i = 0; i < switchCapacity; ++i) {
      unsigned b =
          i < 4 ? unsigned(variable(fx, "SW_CFG_BASE")) + 1 + i * 128
                : unsigned(variable(fx, "DS_CFG_BASE")) + 2 + (i - 4) * 128;
      const unsigned offsets[] = {20, 21, 0, 1, 2, 3, 4, 11};
      for (unsigned j = 0; j < 8; ++j)
        sw[i][j] = cell(fx, b + offsets[j]);
      for (unsigned j = 0; j < 16; ++j)
        sw[i][8 + j] = cell(fx, b + 32 + j);
      unsigned rt = i < 4 ? unsigned(variable(fx, "SW_RT_BASE")) + i * 32
                          : unsigned(variable(fx, "DS_RT_BASE")) + (i - 4) * 32;
      switchPressed[i]=cell(fx,rt);chargeFields[i]={{cell(fx,rt+31),cell(fx,rt+30),cell(fx,rt+23),cell(fx,rt),cell(fx,rt+25)}};
      for(unsigned j=0;j<128;++j)switchFields[i][j]=cell(fx,b+j);
      conductorQueued[i]=cell(fx,unsigned(variable(fx,"CONDUCTOR_GESTURE_BASE"))+i*8+3);
      for(unsigned k=0;k<8;++k)conductorFields[i][k]=cell(fx,unsigned(variable(fx,"CONDUCTOR_BASE"))+i*8+k);
      sw[i][24] = cell(fx, rt + 7);
      sw[i][25] = cell(fx, rt + 12);
      sw[i][26] = cell(fx, rt + 11);sw[i][27] = cell(fx, rt + 17);
    }
    for(unsigned i=0;i<phraseCapacity;++i){
      for (unsigned j=0;j<16;++j)
        phraseNames[i][j]=cell(fx,unsigned(variable(fx,"PHRASE_NAME_BASE"))+i*16+j);
      phrase[i][8] = cell(fx, unsigned(variable(fx, "PHRASE_NOTE_BASE")) + i);
      phrase[i][9] = cell(fx, i>=16?unsigned(variable(fx,"NATIVE_CHANNEL_BASE"))+i:unsigned(variable(fx, "SW_CFG_BASE")) + 1 + (i / 4) * 128 + 27 + i % 4);
      phrase[i][10] = cell(fx, i>=16?unsigned(variable(fx,"NATIVE_OUTPUT_BASE"))+i:unsigned(variable(fx, "SW_CFG_BASE")) + 1 + (i / 4) * 128 + 116 + i % 4);
      phrase[i][3] = cell(fx, unsigned(variable(fx, "DECAY_BASE")) + i);
      const char *extra[] = {"VEL_BASE", "MUTE_BASE", "SOLO_BASE", "MODE_BASE"};
      for (unsigned j = 0; j < 4; ++j)
        phrase[i][4 + j] = cell(fx, unsigned(variable(fx, extra[j])) + i);
      phrase[i][0] = cell(fx, unsigned(variable(fx, "COUNT_BASE")) + i);
      phrase[i][1] = cell(fx, unsigned(variable(fx, "MODE_BASE")) + i);
      phrase[i][2] = cell(fx, i>=16?unsigned(variable(fx,"NATIVE_TIME_BASE"))+i:unsigned(variable(fx, "SW_CFG_BASE")) + 1 + (i / 4) * 128 + 112 + i % 4);
    }
    for (unsigned i = 0; i < 8; ++i) {
      inst[i][0] = cell(fx, unsigned(variable(fx, "I_EXISTS_BASE")) + i);
      inst[i][1] = cell(fx, unsigned(variable(fx, "I_IDS_BASE")) + i);
      const char *names[] = {"INST_ENABLED_BASE", "INST_IN_BASE",
                             "INST_OUT_BASE", "INST_LEVEL_BASE"};
      for (unsigned j = 0; j < 4; ++j) {
        std::string n = i < 3 ? names[j] : std::string("I_") + names[j];
        inst[i][2 + j] =
            cell(fx, unsigned(variable(fx, n.c_str())) + (i < 3 ? i : i - 3));
      }
      for (unsigned j = 0; j < 16; ++j)
        inst[i][6 + j] =
            cell(fx, unsigned(variable(fx, i < 3 ? "INSTR_NAME_BASE"
                                                 : "I_INSTR_NAME_BASE")) +
                         (i < 3 ? i : i - 3) * 16 + j);
    }
  }
  performance::State effectiveState() const {
    performance::State result;
    auto identity = [](double value) -> uint32_t {
      return std::isfinite(value) && value == std::floor(value) && value > 0 &&
                     value <= 16777215
                 ? uint32_t(value)
                 : 0;
    };
    auto add = [&](unsigned instrument, unsigned module, int kind, double value,
                   bool expression) {
      if (result.count >= result.values.size())
        return;
      auto &v = result.values[result.count++];
      v.key.instrument = instrument;
      v.key.module = module;
      v.key.kind = kind;
      v.effective = value;
      v.expression = expression;
    };
    for (unsigned i = 0; i < 8; ++i)
      if (*inst[i][0]) {
        add(identity(*inst[i][1]), 0, 1, *inst[i][5], *levelAssignment[i] != 0);
        for (unsigned j = 0; j < 3; ++j)
          add(identity(*inst[i][1]), 0, 21 + j, *inst[i][2 + j], false);
        for (const auto &setting : expressiveSettings)
          if (setting.instrument == identity(*inst[i][1]) && setting.curveModule)
            add(setting.instrument, setting.curveModule, 27,
                setting.curve.amount, false);
        if (!std::isfinite(*tfCount[i]) || *tfCount[i] < 0 || *tfCount[i] > 6 ||
            *tfCount[i] != std::floor(*tfCount[i])) {
          result.count = 513;
          return result;
        }
        unsigned count = unsigned(*tfCount[i]);
        for (unsigned j = 0; j < count; ++j) {
          double raw = std::abs(*tfCodes[i][j]);
          if (!std::isfinite(raw) || raw < 1 || raw >= 12 ||
              raw != std::floor(raw)) {
            result.count = 513;
            return result;
          }
          int c = int(raw);
          double rawType = c < 7 ? c : *tfTypes[i][c];
          if (!std::isfinite(rawType) || rawType < 1 || rawType > 6 ||
              rawType != std::floor(rawType)) {
            result.count = 513;
            return result;
          }
          int type = int(rawType);
          int rows = performance::parameterCount(type);
          add(identity(*inst[i][1]), identity(*tfIds[i][c]), 24,
              *tfCodes[i][j] > 0, false);
          for (int r = 0; r < rows; ++r)
            add(identity(*inst[i][1]), identity(*tfIds[i][c]),
                performance::parameterKind(type, r), *values[i][c][r],
                *assignments[i][c][r] != 0);
        }
      }
    for (unsigned i = 0; i < phraseCapacity; ++i) {
      add(i + 1, 0, 14, *phrase[i][2], false);
      add(i + 1, 0, 15, *phrase[i][3], false);
      for (unsigned j = 0; j < 4; ++j)
        add(i + 1, 0, 17 + j, *phrase[i][4 + j], false);
    }
    return result;
  }
  bool resolve(const controller::Binding &b, unsigned &i, int &code, int &row,
               bool legacy = false) const {
    if (performance::phraseKind(b.kind)) {
      i = b.instrument - 1;
      code = -1;
      row = b.kind == 14 ? 2 : b.kind == 15 ? 3 : b.kind - 13;
      return i < phraseCapacity && !b.module;
    }
    for (i = 0; i < 8; ++i)
      if (*inst[i][0] && *inst[i][1] == double(b.instrument))
        break;
    if (i == 8)
      return false;
    if (b.kind == 27) {
      for (const auto &setting : expressiveSettings)
        if (setting.instrument == b.instrument && setting.curveModule &&
            setting.curveModule == b.module) {
          code = -3;
          row = 0;
          return true;
        }
      return false;
    }
    if (!b.module) {
      code = 0;
      row = 0;
      return b.kind==25 || b.kind==26 || (b.kind >= 21 && b.kind <= 23) ||
             (b.kind == 1 && (legacy || !*levelAssignment[i]));
    }
    if (!std::isfinite(*tfCount[i]) || *tfCount[i] < 0 || *tfCount[i] > 6)
      return false;
    for (int j = 0; j < int(*tfCount[i]); ++j) {
      double raw = std::abs(*tfCodes[i][j]);
      if (!std::isfinite(raw) || raw < 1 || raw >= 12)
        continue;
      int c = int(raw);
      if (c > 0 && c < 12 && *tfIds[i][c] == double(b.module)) {
        code = c;
        if (b.kind == 24) {
          code = -2;
          row = j;
          return true;
        }
        int type = c < 7 ? c : int(*tfTypes[i][c]);
        int rows = performance::parameterCount(type);
        for (row = 0; row < rows; ++row)
          if (performance::parameterKind(type, row) == b.kind)
            return legacy || !*assignments[i][c][row];
      }
    }
    return false;
  }
  double* legacyAssignment(const controller::Binding &b) const{unsigned i;int c,r;if(b.kind>=14 || !resolve(b,i,c,r,true))return nullptr;return c?assignments[i][c][r]:levelAssignment[i];}
  double *bindingValue(const controller::Binding &b,
                       bool legacy = false) const {
    if (b.kind == 16)
      return b.instrument == 1 && !b.module ? &abPosition : nullptr;
    unsigned i;
    int c, r;
    if (!resolve(b, i, c, r, legacy))
      return nullptr;
    if(b.kind==25 || b.kind==26)return &hostMixer[i][b.kind-25];
    if(c==-3){
      for(auto &setting:expressiveSettings)
        if(setting.instrument==b.instrument && setting.curveModule==b.module)
          return &setting.curve.amount;
      return nullptr;
    }
    return c == -1   ? phrase[i][r]
           : c == -2 ? tfCodes[i][r]
           : c       ? values[i][c][r]
                     : inst[i][b.kind >= 21 ? b.kind - 19 : 5];
  }
  int legacyCurve(const controller::Binding &b) const {
    if (b.kind >= 14)
      return -1;
    unsigned i;
    int c, r;
    if (!resolve(b, i, c, r, true))
      return -1;
    return c ? (*assignments[i][c][r] ? curveIndices[i][c][r] : -1)
             : (*levelAssignment[i] ? levelCurveIndices[i] : -1);
  }
  double bindingBase(const controller::Binding &b) const {
    if (b.kind == 16)
      return abPosition;
    unsigned i;
    int c, r;
    if (!resolve(b, i, c, r))
      return 0;
    if (b.kind >= 17)
      return b.kind == 24 ? (*bindingValue(b) > 0 ? 1 : 0) : *bindingValue(b);
    auto pending = c == -1 ? nullptr
                   : c     ? pendingValues[i][c][r]
                           : levelPending[i];
    return pending && *pending != -999 ? *pending : *bindingValue(b);
  }
  void snapshot(Snapshot &s) const {
    s.expressiveConfig=expressiveConfiguration();
    s.phraseCapacity=phraseCapacity;s.switchCapacity=switchCapacity;s.schema=schema;
    s.instanceError=int(*instanceError);s.instanceRejected=uint64_t(*instanceRejected);
    for(unsigned j=0;j<12+phraseCapacity;++j)for(unsigned k=0;k<14;++k)s.instances[j][k]=*instances[j][k];
    for(unsigned j=0;j<12+phraseCapacity;++j){s.instances[j][2]=j<12?*voiceActive[j]:(*instances[j][11]>.5 && *phraseTriggers[j-12]>.5);s.instances[j][3]=j<12?*voiceLayer[j]+1:j-12+1;}

    for (unsigned i = 0; i < switchCapacity; ++i) {
      auto &v = s.switches[i];
      v.id = *sw[i][0] ? int(*sw[i][1]) : 0;
      v.conductorQueued=0;v.conductorStep=v.conductorSteps=v.conductorResult=v.conductorMissing=v.conductorAdmitted=0;
      if(v.id && *conductorFields[i][0]==v.id){v.conductorQueued=int(*conductorQueued[i]);v.conductorStep=int(*conductorFields[i][3])+1;v.conductorSteps=int(*conductorFields[i][1]);v.conductorResult=int(*conductorFields[i][4]);v.conductorMissing=int(*conductorFields[i][5]);v.conductorAdmitted=int(*conductorFields[i][6]);}
      v.on = int(*sw[i][2]);
      v.type = int(*sw[i][3]);
      v.kind = int(*sw[i][4]);
      v.ch = int(*sw[i][5]) + 1;
      v.slot=i;v.num = int(*sw[i][6]);
      v.length = int(*sw[i][7]);
      v.step = int(*sw[i][24]) + 1;
      v.actionCount=int(*sw[i][25]);v.lastAction=int(*sw[i][26]);v.result=int(*sw[i][27]);
      const unsigned fields[]={0,2,3,4,12,13,6,7,8,9,10,11,14,15,16,17,18,19};
      v.charging=*chargeFields[i][0]>0&&*chargeFields[i][3]>0&&*chargeFields[i][4]>0;v.charge=controller::clamp(*chargeFields[i][1]);v.chargeStep=int(*chargeFields[i][2]);
      v.longHoldMs=int(*switchFields[i][120]);v.longHoldAction=int(*switchFields[i][121]);v.longHoldTarget=int(*switchFields[i][122]);
      for(unsigned j=0;j<18;++j)v.settings[j]=int(*switchFields[i][fields[j]]);
      for(unsigned j=0;j<64;++j)v.sequence[j]=int(*switchFields[i][48+j])+1;
      for (unsigned j = 0; j < 16; ++j)
        v.name[j] = char(*sw[i][8 + j]);
    }
    for(unsigned i=0;i<phraseCapacity;++i){
      for (unsigned j=0;j<16;++j) s.phrases[i].name[j]=char(*phraseNames[i][j]);
      s.phrases[i].events = int(*phrase[i][0]);
      bool playing=s.phrases[i].events>0 && *musicalState==3 && *phrase[i][1]<.5 && *phraseTriggers[i]>.5;
      for(unsigned j=0;j<12;++j)playing|=*voiceActive[j]>.5 && *voiceLayer[j]==i;
      auto &p=s.phrases[i];p.state=!p.events?0:*phraseFinished[i]>.5?3:7;
      if(playing)p.state=4;
      if(*odLayer==i && *odArmed>.5)p.state=5;
      if(*odLayer==i && *odActive>.5)p.state=6;
      if(*recordLayer==i && (*musicalState==1 || *freeReady>.5))p.state=1;
      if(*recordLayer==i && (*musicalState==2 || *freeActive>.5))p.state=2;
      if((s.chainError && s.chainErrorPhrase==int(i)) || *freeError==i+1)p.state=8;
      s.phrases[i].mode = int(*phrase[i][1]);
      s.phrases[i].time = *phrase[i][2];
      s.phrases[i].velocityDecay = *phrase[i][3];
      s.phrases[i].baseVelocity = *phrase[i][4];
      s.phrases[i].mute = int(*phrase[i][5]);
      s.phrases[i].solo = int(*phrase[i][6]);
      s.phrases[i].triggerNote = int(*phrase[i][8]);
      s.phrases[i].triggerChannel = int(*phrase[i][9]);
      s.phrases[i].outputChannel = int(*phrase[i][10]);
    }
    for (unsigned i = 0; i < 8; ++i) {
      auto &v = s.instruments[i];
      v.id = *inst[i][0] ? int(*inst[i][1]) : 0;
      v.on = int(*inst[i][2]);
      v.input = int(*inst[i][3]);
      v.output = int(*inst[i][4]);
      v.level = int(*inst[i][5]);
      v.hostMixer=hostMixer[i];v.hostMixerSequence=hostMixerSequence[i];
      v.transformerCount = std::max(0, std::min(6, int(*tfCount[i])));
      v.serialPitch = false;
      for (int j = 0; j < v.transformerCount; ++j) {
        int code = int(*tfCodes[i][j]);
        int k = std::abs(code);
        v.transformerIds[j] = k > 0 && k < 12 ? int(*tfIds[i][k]) : 0;
        v.transformerTypes[j] =
            k > 0 && k < 12 ? (k < 7 ? k : int(*tfTypes[i][k])) : 0;
        v.transformerOn[j] = code > 0;
        if (k <= 0 || k >= 12 || v.transformerTypes[j] < 1 ||
            v.transformerTypes[j] > 6) {
          v.parameterCounts[j] = 0;
          continue;
        }
        int type = v.transformerTypes[j];
        if (k >= 7 && (type == 1 || type == 2 || type == 4)) v.serialPitch = true;
        v.parameterCounts[j] = performance::parameterCount(type);
        for (int r = 0; r < v.parameterCounts[j]; ++r) {
          v.transformerValues[j][r] = *values[i][k][r];
          v.transformerPending[j][r]=pendingValues[i][k][r]?*pendingValues[i][k][r]:-999;
          v.transformerAssignments[j][r] = int(*assignments[i][k][r]);
          v.transformerKinds[j][r] = performance::parameterKind(type, r);
        }
      }

      for (unsigned j = 0; j < 16; ++j)
        v.name[j] = char(*inst[i][6 + j]);
    }
  }
};
// All JSON and socket operations execute on the control thread.
static std::string quote(const char *s) {
  std::string out = "\"";
  for (; *s; ++s) {
    unsigned char c = *s;
    if (c == '"' || c == '\\')
      out += '\\';
    if (c >= 32 && c < 127)
      out += char(c);
  }
  return out + '"';
}
static std::string json(const Reply &r) {
  auto &s = r.state;
  std::ostringstream o;
  const char *status[] = {"ok", "conflict", "unknown_target", "invalid"};
  o << "{\"protocolVersion\":1,\"schemaVersion\":"<<s.schema<<",\"switchCapacity\":"<<s.switchCapacity<<",\"phraseCapacity\":"<<s.phraseCapacity<<",\"revision\":" << s.revision
    << ","
       "\"requestId\":"
    << r.id << ",\"engineSessionId\":" << engineSession
    << ",\"status\":" << quote(status[r.status])
    << ",\"backend\":" << quote(s.backend ? "jack" : "mock")
    << ",\"buildRevision\":" << quote(MBMF_BUILD_REVISION)
    << ",\"echocityAvailable\":" << (s.echoAvailable?"true":"false")
    << ",\"echocity\":" << echocity::json(s.echoConfig)
    << ",\"echocityPending\":" << s.echoPending << ",\"echocitySources\":" << s.echoSources
    << ",\"expressivePending\":" << s.expressivePending << ",\"expressiveRejected\":" << s.expressiveRejected << ",\"expressiveClamped\":" << s.expressiveClamped
    << ",\"nativeExpressive\":" << expressive::configurationJson(s.expressiveConfig)
    << ",\"echocityRejected\":" << s.echoRejected
    << ",\"chainFrameGap\":" << s.chainFrameGap << ",\"chainClockGap\":" << s.chainClockGap
    << ",\"chainTimingVersion\":" << s.chainTimingVersion
    << ",\"chainCaptureMode\":" << quote(s.chainGridCapture?"two-bar-grid":"free-time")
    << ",\"chainMode\":" << s.chain << ",\"chainRunning\":" << s.chainRun
    << ",\"chainArmed\":" << s.chainArmed
    << ",\"chainPhraseId\":" << s.chainPhrase+1
    << ",\"chainRecording\":" << s.chainRecord
    << ",\"chainError\":" << s.chainError
    << ",\"chainErrorCode\":" << s.chainErrorCode
    << ",\"chainErrorReason\":" << quote(ChainMode::errorName(static_cast<ChainMode::CaptureError>(s.chainErrorCode)))
    << ",\"chainErrorPhraseId\":" << s.chainErrorPhrase+1
    << ",\"captureRejected\":" << s.captureRejected
    << ",\"captureOverflows\":" << s.captureOverflows
    << ",\"chainFrame\":" << s.chainFrame
    << ",\"chainLength\":" << s.chainLength << ",\"chainBpm\":" << s.chainBpm
    << ",\"sampleRate\":" << s.sampleRate << ",\"blockSize\":" << s.blockSize
    << ",\"sampleClock\":" << s.samples << ",\"blocks\":" << s.blocks
    << ",\"midiCount\":" << s.midi << ",\"activeNotes\":" << s.active
    << ",\"pendingOutput\":" << s.pendingOutput
    << ",\"outputOverflow\":" << s.outputOverflow
    << ",\"midiReceived\":" << s.midiReceived
    << ",\"midiInputAccepted\":" << s.midiInputAccepted
    << ",\"midiGenerated\":" << s.midiGenerated
    << ",\"midiQueued\":" << s.midiQueued
    << ",\"midiWritten\":" << s.midiWritten
    << ",\"midiDropped\":" << s.midiDropped
    << ",\"midiWriteFailures\":" << s.midiWriteFailures
    << ",\"midiRecoveries\":" << s.midiRecoveries
    << ",\"lateBlocks\":" << s.late << ",\"maxCallbackUs\":" << s.max_us
    << ",\"lastEvent\":[" << s.last_sample << "," << s.last_status << ","
    << s.last_note << "," << s.last_value << "]"
    << ",\"instanceError\":"<<s.instanceError<<",\"instanceRejected\":"<<s.instanceRejected<<",\"instances\":[";
  bool instanceComma=false;
  for(const auto &v:s.instances)if(v[2]>.5 || v[5]>0 || v[9]>0){
    if(instanceComma)o<<',';instanceComma=true;
    o<<"{\"id\":"<<uint64_t(v[0])<<",\"generation\":"<<uint64_t(v[1])<<",\"phraseId\":"<<int(v[3])
     <<",\"active\":"<<(v[2]>.5?"true":"false")<<",\"reservedAttacks\":"<<int(v[5])<<",\"ownedOutputs\":"<<int(v[13])
     <<",\"ownershipSupported\":"<<(v[6]>=0?"true":"false")<<",\"independent\":"<<(v[7]>.5?"true":"false")<<",\"mode\":"<<int(v[8])<<'}';
  }
  o<<"],\"switches\":[";
  bool comma = false;
  for (auto &v : s.switches)
    if (v.id) {
      if (comma)
        o << ',';
      comma = true;
      o << "{\"id\":" << v.id << ",\"slot\":"<<v.slot<<",\"name\":" << quote(v.name)
        << ",\"enabled\":" << v.on << ",\"type\":" << v.type
        << ",\"kind\":" << v.kind << ",\"channel\":" << v.ch
        << ",\"number\":" << v.num << ",\"length\":" << v.length
        << ",\"step\":" << v.step << ",\"actionCount\":" << v.actionCount
        << ",\"conductor\":{\"step\":"<<v.conductorStep<<",\"queuedStep\":"<<v.conductorQueued<<",\"steps\":"<<v.conductorSteps<<",\"result\":"<<v.conductorResult<<",\"missing\":"<<v.conductorMissing<<",\"admitted\":"<<v.conductorAdmitted<<"}"
        << ",\"supercharge\":{\"active\":"<<(v.charging?"true":"false")<<",\"progress\":"<<v.charge<<",\"step\":"<<v.chargeStep<<"}"
        << ",\"lastAction\":" << v.lastAction << ",\"result\":" << v.result << ",\"longHold\":{\"milliseconds\":"<<v.longHoldMs<<",\"action\":"<<v.longHoldAction<<",\"target\":"<<v.longHoldTarget<<"},\"settings\":[";
      for(unsigned j=0;j<18;++j){if(j)o<<',';o<<v.settings[j];}
      o<<"],\"sequence\":[";for(int j=0;j<v.length;++j){if(j)o<<',';o<<v.sequence[j];}o<<"]}";
    }
  o << "],\"instruments\":[";
  comma = false;
  for (auto &v : s.instruments)
    if (v.id) {
      if (comma)
        o << ',';
      comma = true;
      o << "{\"id\":" << v.id << ",\"name\":" << quote(v.name)
        << ",\"enabled\":" << v.on << ",\"input\":" << v.input
        << ",\"output\":" << v.output << ",\"level\":" << v.level
        << ",\"hostMixer\":{\"volume\":"<<v.hostMixer[0]<<",\"pan\":"<<v.hostMixer[1]<<",\"volumeSequence\":"<<v.hostMixerSequence[0]<<",\"panSequence\":"<<v.hostMixerSequence[1]<<'}'
        << ",\"serialPitchOrder\":" << (v.serialPitch ? "true" : "false")
        << ",\"transformers\":[";
      for (int j = 0; j < v.transformerCount; ++j) {
        if (j)
          o << ',';
        o << "{\"id\":" << v.transformerIds[j]
          << ",\"type\":" << v.transformerTypes[j]
          << ",\"enabled\":" << v.transformerOn[j] << ",\"parameters\":[";
        for (int r = 0; r < v.parameterCounts[j]; ++r) {
          if (r)
            o << ',';
          o << "{\"kind\":" << v.transformerKinds[j][r]
            << ",\"value\":" << v.transformerValues[j][r]
            << ",\"assignment\":" << v.transformerAssignments[j][r];
          if(v.transformerPending[j][r]!=-999)o<<",\"pendingValue\":"<<v.transformerPending[j][r];
          o<<'}';
        }
        o << "]}";
      }
      o << "]}";
    }
  o << "],\"nativePhraseContract\":" << (s.chain?2:1) << ",\"nativeHeldRelease\":false,\"phrases\":[";
  for (unsigned i = 0; i < s.phraseCapacity; ++i) {
    if (i)
      o << ',';
    o << "{\"id\":" << i + 1 << ",\"events\":" << s.phrases[i].events
      << ",\"name\":" << quote(s.phrases[i].name)
      << ",\"state\":" << quote(std::array<const char*,9>{{"IDLE","ARMED","RECORDING","FINISHED","PLAYING","OVERDUB ARMED","OVERDUB ACTIVE","STOPPED","ERROR"}}[s.phrases[i].state])
      << ",\"outputChannel\":" << s.phrases[i].outputChannel
      << ",\"mode\":" << s.phrases[i].mode
      << ",\"timeDecay\":" << s.phrases[i].time
      << ",\"velocityDecay\":" << s.phrases[i].velocityDecay
      << ",\"baseVelocity\":" << s.phrases[i].baseVelocity
      << ",\"triggerNote\":" << s.phrases[i].triggerNote << ",\"triggerChannel\":" << s.phrases[i].triggerChannel
      << ",\"mute\":" << s.phrases[i].mute << ",\"solo\":" << s.phrases[i].solo
      << '}';
  }
  o << "],\"legacyCurve\":{\"source\":"<<r.legacySource<<",\"points\":[";for(int j=0;j<r.legacyCount;++j){if(j)o<<',';o<<'['<<r.legacyPoints[j][0]<<','<<r.legacyPoints[j][1]<<','<<r.legacyPoints[j][2]<<']';}o<<"]}";
  o << ",\"controllerEngine\":"
    << controller::configurationJson(s.controllerConfig)
    << ",\"switchLearn\":{\"target\":"<<s.switchLearnTarget<<",\"conflict\":"<<(s.switchLearnConflict?"true":"false")<<"}"
    << ",\"controllerLearn\":{\"domain\":" << quote(s.learnCommand ? "phrase" : "source") << ",\"target\":" << s.learnTarget
    << ",\"conflict\":" << s.learnConflict
    << ",\"kind\":" << s.learnCandidate.kind
    << ",\"channel\":" << s.learnCandidate.channel + 1
    << ",\"number\":" << s.learnCandidate.number << "},\"controllerRuntime\":[";
  for (unsigned j = 0; j < 32; ++j) {
    if (j)
      o << ',';
    o << "{\"effective\":" << s.effective[j] << ",\"owner\":" << s.owners[j]
      << ",\"returning\":" << s.returning[j] << ",\"pickup\":" << s.pickup[j]
      << '}';
  }
  o << "],\"reveals\":[";
  for(unsigned j=0;j<s.revealCount;++j){if(j)o<<',';o<<"{\"instanceId\":"<<s.revealIds[j]<<",\"requestedHidden\":"<<s.revealHidden[j]<<",\"ownedChannels\":"<<s.revealMasks[j]<<",\"restoreVolumes\":[";for(unsigned ch=0;ch<16;++ch){if(ch)o<<',';o<<s.revealVolumes[j][ch];}o<<"]}";}
  o << "],\"selectedSnapshotId\":" << s.performanceSelected
    << ",\"snapshotSkippedTargets\":" << s.performanceSkipped
    << ",\"movements\":{\"active\":"<<s.movementActive<<",\"rejected\":"<<s.movementRejected<<",\"emitted\":"<<s.movementEmitted<<",\"cancelled\":"<<s.movementCancelled<<",\"running\":[";
  for(unsigned j=0;j<s.movementRunningCount;++j){if(j)o<<',';o<<"{\"id\":"<<quote(s.movementIds[j].data())<<",\"progress\":"<<s.movementProgress[j]<<'}';}
  o<<"]}"
    << ",\"targetSnapshotId\":" << s.performanceTarget
    << ",\"morphProgress\":" << s.performanceProgress << ",\"snapshots\":[";
  for (unsigned j = 0; j < s.performanceCount; ++j) {
    if (j)
      o << ',';
    o << "{\"id\":" << s.performanceIds[j]
      << ",\"name\":" << quote(s.performanceNames[j].data())
      << ",\"seconds\":" << s.performanceSeconds[j]
      << ",\"ease\":" << s.performanceEase[j]
      << ",\"switching\":" << s.performanceSwitch[j]
      << ",\"parameterCount\":" << s.performanceSizes[j]
      << ",\"dirty\":" << (s.performanceDirty[j] ? "true" : "false") << '}';
  }
  o << "],\"snapshotActions\":[";
  bool firstAction = true;
  for (const auto &a : s.snapshotActions)
    if (a.switchId) {
      if (!firstAction)
        o << ',';
      firstAction = false;
      o << "{\"switchId\":" << a.switchId << ",\"gesture\":" << a.gesture
        << ",\"action\":" << a.action << ",\"snapshotId\":" << a.snapshotId
        << '}';
    }
  o << "] ,\"snapshotAB\":{\"a\":" << s.ab.a << ",\"b\":" << s.ab.b
    << ",\"position\":" << s.ab.position << ",\"ease\":" << s.ab.ease
    << ",\"skipped\":" << s.abSkipped << ",\"overridden\":" << s.abOverridden
    << '}';
  if (r.detail.id) {
    const auto &d = r.detail;
    o << ",\"snapshotDetail\":{\"id\":" << d.id << ",\"name\":" << quote(d.name)
      << ",\"seconds\":" << d.seconds << ",\"ease\":" << int(d.ease)
      << ",\"switching\":" << int(d.switching)
      << ",\"revision\":" << r.detailRevision
      << ",\"engineSessionId\":" << engineSession
      << ",\"parameterCount\":" << d.state.count << ",\"parameters\":[";
    for (unsigned j = 0; j < d.state.count; ++j) {
      if (j)
        o << ',';
      const auto &v = d.state.values[j];
      o << "{\"instrumentId\":" << v.key.instrument
        << ",\"moduleId\":" << v.key.module << ",\"kind\":" << v.key.kind
        << ",\"value\":" << v.effective
        << ",\"included\":" << (v.included ? "true" : "false")
        << ",\"expression\":" << (v.expression ? "true" : "false") << '}';
    }
    o << "]}";
  }
  o << "}\n";
  return o.str();
}
static bool send_line(int fd, const std::string &s,
                      std::atomic<bool> &shutdown) {
  size_t at = 0;
  auto end = std::chrono::steady_clock::now() + std::chrono::seconds(2);
  while (at < s.size() && !shutdown && std::chrono::steady_clock::now() < end) {
    auto n = send(fd, s.data() + at, s.size() - at, MSG_NOSIGNAL);
    if (n > 0)
      at += size_t(n);
    else {
      pollfd p{fd, POLLOUT, 0};
      if (poll(&p, 1, 20) < 0)
        return false;
      if (p.revents & (POLLHUP | POLLERR))
        return false;
    }
  }
  return at == s.size();
}

struct PatchModel {
  std::vector<double *> memory;
  std::array<double *, 9> globals;
  std::array<unsigned, 9> sizes{};
  std::array<unsigned, 7> markers{};
  std::vector<double> snapshot, guardedSnapshot, factory;
  bool guardedReady = false;
  unsigned schema=7;
  ysfx_t *fx;
  explicit PatchModel(ysfx_t *f) : fx(f) {
    schema=unsigned(variable(f,"IO_SCHEMA"));
    const char *sizeNames[] = {"WORK_MEM_SIZE",     "SW_LEGACY_PAYLOAD",
                               "CC_LEGACY_PAYLOAD", "TF_LEGACY_PAYLOAD",
                               "DS_LEGACY_PAYLOAD", "I_LEGACY_PAYLOAD",
                               "PATCH_PAYLOAD_SIZE"};
    for (unsigned i = 0; i < 7; ++i)
      sizes[i + 1] = unsigned(variable(f, sizeNames[i]));
    const char *markerNames[] = {"WORK_MEM_SIZE",     "SW_LEGACY_PAYLOAD",
                                 "CC_LEGACY_PAYLOAD", "TF_LEGACY_PAYLOAD",
                                 "DS_LEGACY_PAYLOAD", "I_LEGACY_PAYLOAD"};
    for (unsigned i = 0; i < 6; ++i)
      markers[i] = unsigned(variable(f, markerNames[i]));
    auto j = NSEEL_VM_regvar(f->vm.get(), "remote_j"),
         addr = NSEEL_VM_regvar(f->vm.get(), "remote_address");
    auto code = NSEEL_code_compile(f->vm.get(),
                                   "remote_address=payload_addr(remote_j);", 0);
    if (!code)
      throw std::runtime_error("patch bridge");
    if(schema==8){sizes[8]=sizes[7];sizes[7]=unsigned(variable(f,"NATIVE_LEGACY_PAYLOAD"));markers[6]=sizes[7];}
    memory.reserve(sizes[schema]);
    snapshot.resize(sizes[schema] + 9);
    guardedSnapshot.resize(sizes[schema] + 9);
    for (unsigned i = 0; i < sizes[schema]; ++i) {
      *j = i;
      NSEEL_code_execute(code);
      memory.push_back(cell(f, unsigned(*addr)));
    }
    NSEEL_code_free(code);
    const char *names[] = {"loop_len_samples", "analysis_done", "slider4",
                           "slider5",          "slider6",       "slider7",
                           "slider8",          "slider9",       "record_layer"};
    for (unsigned i = 0; i < 9; ++i)
      globals[i] = ysfx_find_var(f, names[i]);
    factory.resize(9+memory.size());for(unsigned i=0;i<9;++i)factory[i]=*globals[i];for(unsigned i=0;i<memory.size();++i)factory[9+i]=*memory[i];
  }
  bool validate(unsigned schema, const std::vector<double> &v) const {
    if (schema < 1 || schema > this->schema || (this->schema==8 && schema!=8) || v.size() < 10)
      return false;
    unsigned n = unsigned(v.size() - 9);
    if (schema == 1 ? (n == 0 || n > sizes[1]) : n != sizes[schema])
      return false;
    for (auto x : v)
      if (!std::isfinite(x))
        return false;
    for (unsigned i = 0; i + 1 < schema; ++i)
      if (v[9 + markers[i]] != double(i + 2))
        return false;
    if(schema>=3)for(unsigned i=0;i<16;++i){
      const auto channel=v[9+markers[1]+1+(i/4)*128+116+i%4];
      if(channel<0 || channel>17 || channel!=std::floor(channel))return false;
    }
    if(schema==8){
      const auto countBase=unsigned(variable(fx,"COUNT_BASE"));
      for(unsigned i=0;i<128;++i){
        const auto count=v[9+countBase+i];
        const auto output=v[9+markers[6]+1+128+i];
        const auto channel=v[9+markers[6]+1+256+i];
        if(count<0||count>2048||count!=std::floor(count)||output<0||output>17||output!=std::floor(output)||channel<0||channel>16||channel!=std::floor(channel))return false;
      }
    }
    return v[0] >= 0 && v[0] <= 48000.0 * 3600 && v[8] >= 0 && v[8] < (this->schema==8?128:16);
  }
  bool unchanged() const {
    if (!guardedReady) return false;
    for (unsigned i=0;i<9;++i)
      if (*globals[i] != guardedSnapshot[i]) return false;
    for (unsigned i=0;i<memory.size();++i)
      if (*memory[i] != guardedSnapshot[9+i]) return false;
    return true;
  }
  std::string save(std::atomic<bool> &paused,
                   const controller::Configuration &config,
                   const Model &model, bool guarded = false) {
    for (unsigned i = 0; i < 9; ++i)
      snapshot[i] = *globals[i];
    for (unsigned i = 0; i < memory.size(); ++i)
      snapshot[9 + i] = *memory[i];
    if (guarded) {
      std::copy(snapshot.begin(),snapshot.end(),guardedSnapshot.begin());
      guardedReady = true;
    }
    // Save committed bases, never a transient pedal/return value, in the legacy
    // payload.
    for (auto &b : config.bindings)
      if (b.policy.id) {
        auto address = model.bindingValue(b);
        if (!address)
          continue;
        double physical = performance::physical(b.kind, b.base);
        if (b.kind == 24)
          physical = physical > .5 ? std::abs(*address) : -std::abs(*address);
        for (unsigned j = 0; j < memory.size(); ++j)
          if (memory[j] == address) {
            snapshot[9 + j] = physical;
            break;
          }
      }
    paused.store(false, std::memory_order_release);
    std::ostringstream o;
    o << std::setprecision(17)
      << "{\"format\":\"MIDI_HUMAN_LOOPER_PATCH\",\"schema\":"<<schema<<",\"work_mem_"
         "size\":"
      << memory.size() << ",\"globals\":[";
    for (unsigned i = 0; i < 9; ++i) {
      if (i)
        o << ',';
      o << snapshot[i];
    }
    o << "],\"memory\":[";
    for (unsigned i = 0; i < memory.size(); ++i) {
      if (i)
        o << ',';
      o << snapshot[9 + i];
    }
    o << "],\"controllerEngine\":" << controller::configurationJson(config)
      << "}\n";
    return o.str();
  }
  void load(unsigned schema, const std::vector<double> &v) {
    execute(fx, "reset_note_runtime();cancel_patch_editors();i_defaults();"
                "param_extension_reset();param_runtime_reset();sw_defaults();"
                "sw_runtime_reset();cc_defaults();cc_runtime_reset();tf_"
                "defaults();tf_runtime_reset();");
    if (schema == 1)
      for (unsigned i = v.size() - 9; i < sizes[1]; ++i)
        *memory[i] = 0;
    for (unsigned i = 0; i < 9; ++i)
      *globals[i] = v[i];
    for (unsigned i = 9; i < v.size(); ++i)
      *memory[i - 9] = v[i];
    if (schema < 6)
      execute(fx, "ds_migrate();");
    execute(fx, "sw_validate();record_sample_pos=0;play_sample_pos=0;overdub_"
                "armed=0;overdub_active=0;overdub_pos=0;state=loop_len_samples>"
                "0?STATE_STOPPED:STATE_IDLE;panic_pending=1;");
  }
};
// One synchronous control worker admits a request, then waits for its reply.
// Eight slots retain bounded backpressure without reserving 64 large snapshot
// configurations in every engine process.
static void control(int listener, Queue<Request, 8> &commands,
                    Queue<Reply, 8> &replies, std::atomic<bool> &shutdown,
                    std::atomic<bool> &paused, std::atomic<bool> &loading,
                    PatchModel &patch, Model &model,
                    controller::Host &controllers,
                    performance::Snapshots &performanceSnapshots,
                    const std::function<bool(int, int, int)> &conflicts, movement::Runtime &movements,echocity::Runtime &echoRuntime) {
  std::vector<unsigned> conductorConfiguration; // worker-owned, never live MIDI state
  auto installConductor=[&](const std::vector<unsigned>& bytes){
    std::array<unsigned,64> owners{};
    for(unsigned i=0;i<model.switchCapacity;++i)owners[i]=*model.sw[i][0]?unsigned(*model.sw[i][1]):0;
    unsigned base=unsigned(variable(patch.fx,"CONDUCTOR_BASE"));
    auto prepared=movement::prepare(bytes);
    auto cells=conductor::compile(bytes,base,owners,prepared.blocks);
    movements.install(std::move(prepared));
    std::array<unsigned,128> groups{};
    if(!bytes.empty()){auto sourceDocument=conductor::document(bytes);
      for(const auto& source:sourceDocument.at("sources").array)
        if(source.object.count("muteGroup"))groups[unsigned(source.at("slot").number)-1]=unsigned(source.at("muteGroup").number);
    }
    for(unsigned i=0;i<model.phraseCapacity;++i)*cell(patch.fx,unsigned(variable(patch.fx,"PHRASE_GROUP_BASE"))+i)=groups[i];
    // Touch/resolve every cell on the worker while processing is paused.
    for(unsigned i=0;i<cells.size();++i)*cell(patch.fx,base+i)=cells[i];
    *NSEEL_VM_regvar(patch.fx->vm.get(),"conductor_host_enabled")=1;
  };
  while (!shutdown) {
    pollfd p{listener, POLLIN, 0};
    if (poll(&p, 1, 20) <= 0)
      continue;
    int fd = accept(listener, nullptr, nullptr);
    if (fd < 0)
      continue;
    fcntl(fd, F_SETFL, O_NONBLOCK);
    std::string line;
    bool complete = false;
    auto end = std::chrono::steady_clock::now() + std::chrono::seconds(10);
    while (!shutdown && line.size() < 134217728 &&
           std::chrono::steady_clock::now() < end) {
      pollfd q{fd, POLLIN, 0};
      if (poll(&q, 1, 20) <= 0)
        continue;
      char b[65536];
      auto n = recv(fd, b, sizeof b, 0);
      if (n <= 0)
        break;
      line.append(b, size_t(n));
      if (line.find('\n') != std::string::npos) {
        complete = true;
        break;
      }
    }
    Request request;
    std::istringstream input(line);
    std::string extra;
    std::vector<double> patchValues;
    std::vector<unsigned> pendingConductor;
    bool valid = complete &&
                 bool(input >> request.id >> request.op >> request.target >>
                      request.arg >> request.revision >> request.ch >>
                      request.note >> request.value) &&
                 request.id > 0 && request.id <= 9007199254740991ULL &&
                 request.op >= 0 && (request.op <= 55) && request.arg >= 0 &&
                 request.arg <= (request.op == 1 ? 5 : request.op == 13   ? 5
                                 : request.op == 40 ? 7
                                 : request.op == 15 || request.op == 34 ? 3
                                 : request.op == 32 || request.op == 38 ? 26
                                                    : 2) &&
                 request.ch >= 0 &&
                 (request.op == 11 ? request.ch <= 16 : request.ch < 16) &&
                 request.note >= 0 && request.note < 128 &&
                 request.value >= 0 && request.value < 128;
    input >> std::ws;
    if (valid && input.peek() == 's') {
      std::string marker;
      valid = bool(input >> marker >> request.session) && marker == "session" &&
              request.session > 0 && request.session <= 9007199254740991ULL;
    }
    if (valid && (request.op == 36 || request.op == 37)) {
      std::string hex;
      valid=bool(input>>hex) && request.arg<=(request.op==37?2:1) && request.target>0 &&
            request.target<=(request.op==37 || request.arg?16777215:model.phraseCapacity);
      if (hex!="-") {
        valid=valid && !hex.empty() && hex.size()<=32 && hex.size()%2==0;
        for (unsigned j=0;valid && j<hex.size()/2;++j) {
          auto digit=[](char c){return c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:-1;};
          int a=digit(hex[j*2]),b=digit(hex[j*2+1]),v=a*16+b;
          valid=a>=0 && b>=0 && v>=32 && v<127;
          if(valid) request.snapshotName[j]=char(v);
        }
      }
      if(input>>extra)valid=false;
    } else if(valid && request.op==41){
      for(unsigned j=0;j<98;++j){int v=0;valid=valid && bool(input>>v);request.switchSettings[j]=v;}
      const auto &v=request.switchSettings;
      valid=valid && request.target>0 && request.target<=16777215 && v[0]>=0 && v[0]<=1 && v[1]>=0 && v[1]<=2 && v[2]>=0 && v[2]<16 && v[3]>=0 && v[3]<128 && v[4]>=0 && v[4]<128 && v[5]>=0 && v[5]<128 && (v[1]!=2 || v[4]!=v[5]) && v[6]>=0 && v[6]<=1 && v[7]>=50 && v[7]<=2000 && v[8]>=100 && v[8]<=5000 && v[9]>=0 && v[9]<=3 && v[10]>=0 && v[10]<=1 && v[11]>=0 && v[11]<=64;
      for(unsigned j=12;j<15;++j)valid=valid && v[j]>=0 && v[j]<=9;
      for(unsigned j=15;j<18;++j)valid=valid && v[j]>=0 && (v[j-3]>=7?v[j]<48:v[j]<=int(model.switchCapacity));
      for(unsigned j=18;j<82;++j)valid=valid && v[j]>=0 && v[j]<int(model.phraseCapacity);
      for(unsigned j=82;j<98;++j)valid=valid && (v[j]==0 || (v[j]>=32 && v[j]<127));
      input>>std::ws;
      if(!input.eof()){request.hasLongHold=true;valid=valid&&bool(input>>request.switchSettings[98]>>request.switchSettings[99]>>request.switchSettings[100]);valid=valid&&(v[98]==0||(v[98]>v[8]&&v[98]<=30000))&&v[99]>=0&&v[99]<=9&&v[100]>=0&&(v[99]>=7?v[100]<48:v[100]<=int(model.switchCapacity));}
      if(input>>extra)valid=false;
    } else if(valid && request.op==54){
      valid=echocity::read(input,request.echoConfig);
      if(input>>extra)valid=false;
    } else if(valid && request.op==55){
      valid=expressive::readConfiguration(input,request.expressiveConfig);
      if(input>>extra)valid=false;
    } else if (valid && request.op == 35) {
      valid = request.target >= 0 && request.target < int(model.phraseCapacity) && request.arg >= 0 && request.arg <= 2;
      if (valid && request.arg == 1) {
        double duration=0; unsigned count=0;
        valid = bool(input >> duration >> count) && std::isfinite(duration) &&
                duration > 0 && duration <= 3600 && count > 0 && count <= 2048;
        patchValues.push_back(duration);
        double previous = -1;
        std::array<unsigned,2048> held{};
        for (unsigned j=0; valid && j<count; ++j) {
          double time; int status, note, velocity;
          valid = bool(input >> time >> status >> note >> velocity) &&
                  std::isfinite(time) && time >= previous && time >= 0 && time <= duration &&
                  (status >= 128 && status < 160) && note >= 0 && note < 128 &&
                  velocity >= 0 && velocity < 128;
          if (!valid) break;
          unsigned key=(status&15)*128+note;
          if ((status&240)==144 && velocity) ++held[key];
          else if (!held[key]) valid=false;
          else --held[key];
          previous=time;
          patchValues.insert(patchValues.end(),{time,double(status),double(note),double(velocity)});
        }
        for (auto n:held) if (n) valid=false;
      }
      if (input >> extra) valid=false;
    } else if (valid && request.op == 5) {
      double x;
      while (input >> x)
        patchValues.push_back(x);
      valid = patch.validate(unsigned(request.target), patchValues);
      if (!input.eof()) {
        input.clear();
        std::string marker;
        // Ordered optional carriers. Legacy packets keep their original syntax.
        if (!(input>>marker)) valid=false;
        if (valid && marker=="controllers") {
          valid=controller::readConfiguration(input,request.controllerConfig);
          if (!(input>>marker)) marker.clear();
        }
        if (valid && marker=="snapshots") {
          valid=performance::readConfiguration(input,request.snapshotConfig);
          if (!(input>>marker)) marker.clear();
        }
        if (valid && marker=="conductor") {
          valid=conductor::read(input,pendingConductor);
          if(valid&&!pendingConductor.empty()){
            const auto document=conductor::document(pendingConductor);
            for(const auto &source:document.at("sources").array)
              valid=valid&&source.at("slot").number<=model.phraseCapacity;
          }
          if (!(input>>marker)) marker.clear();
        }
        if(valid && marker=="echocity"){
          valid=echocity::read(input,request.echoConfig);
          if(!(input>>marker))marker.clear();
        }
        if(valid && marker=="native_expressive"){
          valid=expressive::readConfiguration(input,request.expressiveConfig);
          if(!(input>>marker))marker.clear();
        }
        if (!marker.empty()) valid=false;
      }
    } else if (valid &&
               (request.op == 30 || request.op == 31 || request.op == 32 || request.op == 38)) {
      valid = bool(input >> request.module >> request.macroPosition) &&
              request.module >= 0 && request.module <= 16777215 &&
              std::isfinite(request.macroPosition) &&
              (request.op == 32 || request.op == 38 ||
               (request.macroPosition >= 0 && request.macroPosition <= 1));
      if (input >> extra)
        valid = false;
    } else if (valid && request.op == 44) {
      valid=bool(input>>request.instanceId>>request.instanceGeneration) && request.instanceId>0 && request.instanceId<=9007199254740991ULL && request.instanceGeneration>0 && request.instanceGeneration<=9007199254740991ULL;
      if(input>>extra)valid=false;
    } else if (valid && request.op == 28) {
      valid = bool(input >> request.module) && request.module >= 0 &&
              request.module <= 16777215 && request.ch <= 7;
      if (input >> extra)
        valid = false;
    } else if (valid && (request.op == 25 || request.op == 27)) {
      std::string hex;
      valid = bool(input >> hex) && hex.size() > 0 && hex.size() <= 96 &&
              hex.size() % 2 == 0;
      for (unsigned j = 0; valid && j < hex.size() / 2; ++j) {
        auto digit = [](char c) {
          return c >= '0' && c <= '9'   ? c - '0'
                 : c >= 'a' && c <= 'f' ? c - 'a' + 10
                                        : -1;
        };
        int a = digit(hex[j * 2]), b = digit(hex[j * 2 + 1]);
        int value = a * 16 + b;
        valid = a >= 0 && b >= 0 && value >= 32 && value < 127;
        if (valid)
          request.snapshotName[j] = char(value);
      }
      if (valid && request.op == 27)
        valid = bool(input >> request.snapshotSeconds >> request.snapshotEase >>
                     request.snapshotSwitch) &&
                std::isfinite(request.snapshotSeconds) &&
                request.snapshotSeconds >= 0 && request.snapshotSeconds <= 30 &&
                request.snapshotEase >= 0 && request.snapshotEase <= 1 &&
                request.snapshotSwitch >= 1 && request.snapshotSwitch <= 3;
      input >> std::ws;
      if (valid && request.op == 27 && input.peek() != EOF) {
        std::string marker;
        auto &mask = request.snapshotConfig.records[0].state;
        valid = bool(input >> marker) && marker == "include" &&
                performance::integer(input, mask.count, 2048);
        for (unsigned j = 0; valid && j < mask.count; ++j) {
          auto &v = mask.values[j];
          unsigned kind = 0, included = 0;
          valid = performance::integer(input, v.key.instrument, 16777215) &&
                  performance::integer(input, v.key.module, 16777215) &&
                  performance::integer(input, kind, 24) &&
                  performance::integer(input, included, 1);
          v.key.kind = kind;
          v.included = included;
        }
        valid = valid && mask.valid();
      }
      if (input >> extra)
        valid = false;
    } else if (valid && (request.op == 16 || request.op == 39)) {
      valid = controller::readBinding(input, request.binding) &&
              (request.op==39 ? request.target<4 : request.binding.policy.id == unsigned(request.target)) &&
              request.binding.valid();
      if (input >> extra)
        valid = false;
    } else if (valid && request.op == 13) {
      valid = bool(input >> request.module) && request.module >= 0 &&
              request.module <= 16777215;
      if (input >> extra)
        valid = false;
    } else if (valid && request.op == 12) {
      valid = bool(input >> request.module >> request.count) &&
              request.module > 0 && request.module <= 16777215 &&
              request.count > 0 && request.count <= 5;
      for (int j = 0; valid && j < request.count; ++j)
        valid = bool(input >> request.parameters[j].kind >>
                     request.parameters[j].value) &&
                request.parameters[j].kind >= 0 &&
                request.parameters[j].kind < 14 &&
                std::isfinite(request.parameters[j].value);
      if (input >> extra)
        valid = false;
    } else if (valid && (input >> extra))
      valid = false;
    if (valid && request.op >= 6 && request.op <= 8)
      valid = request.target >= 0 && request.target < int(model.phraseCapacity);
    if (valid && request.op >= 9 && request.op <= 10)
      valid = request.target > 0 && request.target <= 16777215 &&
              (request.arg == 2 || request.value <= 16);
    if (valid && request.op == 11)
      valid = request.arg <= 1 && request.note <= 16;
    if (valid && request.op >= 11 && request.op <= 18)
      valid = request.target > 0 && request.target <= 16777215;
    if (valid && request.op == 49)
      valid = request.target >= 0 && request.target < int(model.phraseCapacity) && request.value <= 17;
    if (valid && request.op == 40)
      valid = request.target >= 0 && request.target < int(model.phraseCapacity);
    if (!valid)
      send_line(fd, "{\"status\":\"invalid\"}\n", shutdown);
    else if(request.op==48){
      send_line(fd,"{\"conductor\":"+(conductorConfiguration.empty()?std::string("null"):conductor::json(conductorConfiguration))+"}\n",shutdown);
    }
    else if (!commands.push(request))
      send_line(fd, "{\"status\":\"queue_full\"}\n", shutdown);
    else {
      Reply reply;
      bool received = false;
      end = std::chrono::steady_clock::now() + std::chrono::seconds(2);
      while (!shutdown && std::chrono::steady_clock::now() < end) {
        if (replies.pop(reply)) {
          if (reply.id == request.id) {
            received = true;
            break;
          }
        } else
          std::this_thread::sleep_for(std::chrono::milliseconds(1));
      }
      if (received) {
        if(reply.status==0 && request.op==35 && request.arg==2){
          // Already cleared with bounded pointer writes in the callback. No pause,
          // worker RAM mutation or skipped JACK callback for inactive content.
          send_line(fd,json(reply),shutdown);
        } else if (reply.status == 0 && request.op == 35) {
          const unsigned selected=unsigned(request.target), base=selected*unsigned(variable(patch.fx,"LAYER_STRIDE"));
          const unsigned countBase=unsigned(variable(patch.fx,"COUNT_BASE"));
          const unsigned lengthBase=unsigned(variable(patch.fx,"LEN_BASE"));
          const double rate=reply.state.sampleRate;
          if (request.arg == 2) {
            // Content only: keep phrase identity, mode, names and all parameters.
            *patch.memory[countBase+selected]=0;
            *patch.memory[lengthBase+selected]=0;
            for(const char* name : {"TRIG_BASE","HOLD_ACTIVE_BASE","ONCEPOS_BASE"})
              *NSEEL_VM_getramptr(patch.fx->vm.get(),unsigned(variable(patch.fx,name))+selected,nullptr)=0;
            paused.store(false,std::memory_order_release);
            send_line(fd,json(reply),shutdown);
          } else if (request.arg == 1) {
            double duration=std::max(std::ceil(patchValues[0]*rate),std::round(patchValues[patchValues.size()-4]*rate)+1);
            if (reply.state.chainGridCapture && (duration>reply.state.chainLength ||
                std::round(patchValues[patchValues.size()-4]*rate)>=reply.state.chainLength)) reply.status=3;
            if (!reply.state.chain && *patch.memory[unsigned(variable(patch.fx,"MODE_BASE"))+selected]<.5 &&
                *patch.globals[0]>0 && duration>*patch.globals[0]) reply.status=3;
            if (!reply.status) {
              for (unsigned j=0;j<(patchValues.size()-1)/4;++j) {
                *patch.memory[base+j*5]=std::round(patchValues[1+j*4]*rate);
                for(unsigned k=1;k<4;++k) *patch.memory[base+j*5+k]=patchValues[1+j*4+k];
                *patch.memory[base+j*5+4]=0;
              }
              *patch.memory[countBase+selected]=(patchValues.size()-1)/4;
              *patch.memory[lengthBase+selected]=reply.state.chainGridCapture?reply.state.chainLength:duration;
              if(reply.state.chainGridCapture) *patch.memory[unsigned(variable(patch.fx,"MODE_BASE"))+selected]=0;
              if (*patch.globals[0]<=0) { *patch.globals[0]=duration; *patch.globals[1]=1; }
            }
            paused.store(false,std::memory_order_release);
            send_line(fd,json(reply),shutdown);
          } else {
            double storedCount=*patch.memory[countBase+selected];
            bool validEvents=std::isfinite(storedCount) && storedCount>=0 && storedCount<=2048 && std::floor(storedCount)==storedCount;
            unsigned count=validEvents?unsigned(storedCount):0;
            for(unsigned j=0;validEvents && j<count;++j) {
              double time=*patch.memory[base+j*5];
              validEvents=std::isfinite(time) && time>=0 && time<=rate*3600;
              for(unsigned k=1;validEvents && k<4;++k) {
                double v=*patch.memory[base+j*5+k];
                validEvents=std::isfinite(v) && v>=0 && v<=(k==1?239:127) && std::floor(v)==v;
              }
            }
            if (!validEvents) send_line(fd,"{\"status\":\"invalid\"}\n",shutdown);
            else {
              std::ostringstream out; out<<std::setprecision(17);
              double duration=*patch.memory[lengthBase+selected];
              if(duration<=0) duration=*patch.globals[0];
              for(unsigned j=0;j<count;++j) duration=std::max(duration,*patch.memory[base+j*5]+1);
              out<<"{\"status\":\"ok\",\"phraseData\":{\"lengthSeconds\":"<<duration/rate
                 <<",\"bpm\":"<<(*patch.globals[4]>0?*patch.globals[4]:120)<<",\"events\":[";
              for(unsigned j=0;j<count;++j) {
                if(j) out<<',';
                out<<'['<<*patch.memory[base+j*5]/rate;
                for(unsigned k=1;k<4;++k) out<<','<<int(*patch.memory[base+j*5+k]);
                out<<']';
              }
              out<<"]}}\n";
              paused.store(false,std::memory_order_release);
              send_line(fd,out.str(),shutdown);
            }
          }
          paused.store(false,std::memory_order_release);
        } else if(reply.status==0 && request.op==42){
          patch.load(patch.schema,patch.factory);patch.guardedReady=false;conductorConfiguration.clear();installConductor(conductorConfiguration);
          model.loadExpressive(expressive::Configuration{});
          echoRuntime.configure(echocity::Configurations{},true);
          send_line(fd,json(reply),shutdown);
        } else if (reply.status == 0 && request.op == 4) {
          auto document =
              patch.save(paused, reply.state.controllerConfig, model, request.arg == 1);
          auto last = document.find_last_of('}');
          if (last != std::string::npos)
            document.insert(last,
                            ",\"globalSnapshots\":" +
                                performance::configurationJson(
                                    performanceSnapshots.configuration()));
          if (!conductorConfiguration.empty())
            document.insert(document.find_last_of('}'),",\"conductor\":"+conductor::json(conductorConfiguration));
          if(model.schema==8){
            auto savedExpressive=model.expressiveConfiguration();
            for(const auto &binding:reply.state.controllerConfig.bindings)
              if(binding.policy.id && binding.kind==27)
                for(auto &setting:savedExpressive)
                  if(setting.instrument==binding.instrument &&
                     setting.curveModule==binding.module)
                    setting.curve.amount=performance::physical(27,binding.base);
            document.insert(document.find_last_of('}'),",\"nativeExpressive\":"+expressive::configurationJson(savedExpressive));
          }
          if(reply.state.echoAvailable)document.insert(document.find_last_of('}'),",\"echocity\":"+echocity::json(reply.state.echoConfig));
          paused.store(false, std::memory_order_release);
          send_line(fd, document, shutdown);
        } else {
          if (reply.status == 0 && request.op == 5 && reply.state.chainGridCapture &&
              patchValues[0] != double(reply.state.chainLength))
            reply.status = 3;
          if (reply.status == 0 && request.op == 5) {
            std::vector<double> previous(9 + patch.memory.size());
            for (unsigned j = 0; j < 9; ++j)
              previous[j] = *patch.globals[j];
            for (unsigned j = 0; j < patch.memory.size(); ++j)
              previous[9 + j] = *patch.memory[j];
            auto previousExpressive=model.expressiveConfiguration();
            patch.load(unsigned(request.target), patchValues);
            model.loadExpressive(request.expressiveConfig);
            bool collision = !model.expressiveTargets(request.expressiveConfig);
            for(const auto &c:request.echoConfig)if(c.id){
              bool found=false;for(unsigned j=0;j<8;++j)found|=*model.inst[j][1]==c.instrument && *model.inst[j][0]>.5;
              if(!reply.state.echoAvailable || !found)collision=true;
            }
            for (auto &source : request.controllerConfig.sources)
              if (source.id && source.kind &&
                  conflicts(source.kind, source.channel, source.number))
                collision = true;
            if (collision ||
                !controllers.replace(request.controllerConfig,
                                     [&](const controller::Binding &b) {
                                       return model.bindingValue(b) != nullptr;
                                     })) {
              patch.load(patch.schema, previous);
              model.loadExpressive(previousExpressive);
              reply.status = 3;
            }
          }
          if (reply.status == 0 && request.op == 5) {
            installConductor(pendingConductor);
            echoRuntime.configure(request.echoConfig,true);
            conductorConfiguration.swap(pendingConductor);
            performanceSnapshots.restore(request.snapshotConfig);
            model.abPosition = performanceSnapshots.ab.position;
            controllers.recall(1, 0, 16, model.abPosition);
            model.abRestorePending.store(performanceSnapshots.ab.a != 0,
                                         std::memory_order_release);
          }
          send_line(fd, json(reply), shutdown);
        }
      }
      if (request.op == 4 || request.op == 5 || request.op == 35 || request.op==42) {
        loading.store(false, std::memory_order_release);
        paused.store(false, std::memory_order_release);
      }
    }
    close(fd);
  }
}
int main(int argc, char **argv) {
  if (argc == 2 && std::string(argv[1]) == "--queue-test") {
    Queue<int, 64> q;
    for (int i = 0; i < 64; ++i)
      if (!q.push(i))
        return 1;
    if (q.push(99))
      return 1;
    for (int i = 0; i < 64; ++i) {
      int v;
      if (!q.pop(v) || v != i)
        return 1;
    }
    int v;
    if (q.pop(v))
      return 1;
    std::cout << "PASS bounded FIFO\n";
    return 0;
  }
  if (argc < 3) {
    std::cerr << "usage: engine source.jsfx /tmp/control.sock [--jack] "
                 "[--demo] [--input JACK_PORT] [--output JACK_PORT]\n";
    return 2;
  }
  bool useJack = false, demo = false, chainMode = false, chainGridCapture = false;
  unsigned chainTimingVersion=1;
  std::string clientName = "midi_human_looper";
  std::string inputPort, outputPort, tracePath;
  for (int i = 3; i < argc; ++i) {
    std::string a = argv[i];
    if (a == "--rt-trace" && i+1<argc)
      tracePath=argv[++i];
    else if (a == "--jack")
      useJack = true;
    else if (a == "--chain-timing" && i+1<argc)
      chainTimingVersion=std::stoul(argv[++i]);
    else if (a == "--chain")
      chainMode = true;
    else if (a == "--chain-grid-capture")
      chainGridCapture = true;
    else if (a == "--client" && i + 1 < argc) {
      clientName = argv[++i];
      if (clientName.empty() || clientName.size() > 48 ||
          clientName.find_first_not_of("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLM"
                                       "NOPQRSTUVWXYZ0123456789_-") !=
              std::string::npos)
        return 2;
    } else if (a == "--demo")
      demo = true;
    else if ((a == "--input" || a == "--output") && i + 1 < argc) {
      (a == "--input" ? inputPort : outputPort) = argv[++i];
    } else {
      std::cerr << "unknown option " << a << '\n';
      return 2;
    }
  }
  jack_client_t *jack = nullptr;
  jack_port_t *midiIn = nullptr, *midiOut = nullptr;
  unsigned sampleRate = 48000, blockSize = 128;
  int listener = -1;
  ysfx_t *fx = nullptr;
  ysfx_config_t *config = nullptr;
  bool bound = false;
  std::unique_ptr<realtime_trace::Trace> rtTrace;
  try {
    if(!tracePath.empty()) rtTrace.reset(new realtime_trace::Trace(tracePath));
    if (getrandom(&engineSession, sizeof(engineSession), 0) !=
        static_cast<ssize_t>(sizeof(engineSession)))
      throw std::runtime_error("session identity entropy unavailable");
    engineSession &= 9007199254740991ULL;
    if (!engineSession)
      engineSession = 1;
    config = ysfx_config_new();
    fx = ysfx_new(config);
    if (!ysfx_load_file(fx, argv[1], 0) ||
        !ysfx_compile(fx, ysfx_compile_no_gfx))
      throw std::runtime_error("JSFX compilation");
    if (useJack) {
      jack_status_t status;
      jack = jack_client_open(
          clientName.c_str(),
          jack_options_t(JackNoStartServer | JackUseExactName), &status);
      if (!jack)
        throw std::runtime_error("JACK unavailable: start/connect Zynthian "
                                 "JACK first, or omit --jack for mock mode");
      sampleRate = jack_get_sample_rate(jack);
      blockSize = jack_get_buffer_size(jack);
      midiIn = jack_port_register(jack, "midi_in", JACK_DEFAULT_MIDI_TYPE,
                                  JackPortIsInput, 0);
      midiOut = jack_port_register(jack, "midi_out", JACK_DEFAULT_MIDI_TYPE,
                                   JackPortIsOutput, 0);
      if (!midiIn || !midiOut)
        throw std::runtime_error("JACK MIDI ports");
    }
    ysfx_set_sample_rate(fx, sampleRate);
    ysfx_set_block_size(fx, blockSize);
    ysfx_set_midi_capacity(fx, 65536, false);
    NSEEL_VM_setramsize(fx->vm.get(),33554432);
    ysfx_init(fx);
    if (variable(fx, "IO_SCHEMA") != 7 && variable(fx,"IO_SCHEMA") != 8)
      throw std::runtime_error("spike requires audited schema 7");
    if (chainMode)
      execute(fx, "ext_noinit=1;gmem[0]=0;slider9=1;remote_ci=0;loop(INST_CAP,"
                  "mem[engine_addr(INST_ENABLED_BASE,remote_ci)]=remote_ci==0;"
                  "remote_ci+=1;);mem[engine_addr(INST_IN_BASE,0)]=0;mem["
                  "engine_addr(INST_OUT_BASE,0)]=0;");
    PatchModel patch(fx); // Capture clean factory data before demo or restored user data.
    ChainMode chain(fx, chainMode, chainTimingVersion, chainGridCapture);
    // Allocate/touch native ownership pages before JACK can call us. The first
    // emergency reset must not fault in enlarged phrase/transformer tables.
    if (chainMode) execute(fx, "reset_note_runtime();");
    struct ClearPage { EEL_F *data; unsigned count; };
    std::vector<ClearPage> nativeClearPages;
    auto nativeHostBulkClear = NSEEL_VM_regvar(fx->vm.get(),"native_host_bulk_clear");
    if (chainMode && variable(fx,"IO_SCHEMA")==8) {
      auto bindClear = [&](unsigned address,unsigned count) {
        while(count) {
          int available=0;
          auto data=NSEEL_VM_getramptr(fx->vm.get(),address,&available);
          if(!data || available<=0)throw std::runtime_error("native cleanup page allocation");
          unsigned n=std::min(count,unsigned(available));
          nativeClearPages.push_back({data,n});address+=n;count-=n;
        }
      };
      if(!chainGridCapture)bindClear(6200000,unsigned(variable(fx,"LAYERS"))*2064);
      for(const char *name:{"NATIVE_ARP_HELD_BASE","NATIVE_ARP_SOURCE_BASE","NATIVE_MONO_SOURCE_BASE"})
        bindClear(unsigned(variable(fx,name)),unsigned(variable(fx,"NATIVE_TRANSFORM_CELLS")));
    }
    if (demo)
      execute(
          fx,
          "gmem[0]=0;panic_pending=0;state="
          "STATE_STOPPED;slider9=1;loop_len_samples=24000;"
          "store_event(0,0,144,60,90,0);store_event(0,9600,128,60,0,0);mem[LEN_"
          "BASE]=24000;mem[MODE_BASE]=0;mem[DECAY_BASE]=1;"
          "store_event(1,0,144,64,90,0);store_event(1,9600,128,64,0,0);mem[LEN_"
          "BASE+1]=24000;mem[MODE_BASE+1]=1;mem[DECAY_BASE+1]=1;"
          "sw_assign(0,1,0,72,127,0);sw_assign(1,1,0,73,127,0);mem[sw_cfg(0)]="
          "1;"
          "mem[sw_cfg(1)]=1;mem[sw_cfg(0)+11]=1;mem[sw_cfg(0)+SW_LIST]=0;"
          "mem[sw_cfg(1)+11]=1;mem[sw_cfg(1)+SW_LIST]=1;mem[sw_cfg(0)+15]=SW_"
          "NEXT;mem[sw_cfg(0)+16]=SW_RESET;"
          "mem[sw_cfg(0)+SW_NAME]=86;mem[sw_cfg(0)+SW_NAME+1]=69;mem[sw_cfg(0)+"
          "SW_NAME+2]=82;mem[sw_cfg(0)+SW_NAME+3]=83;mem[sw_cfg(0)+SW_NAME+4]="
          "69;"
          "mem[sw_cfg(1)+SW_NAME]=67;mem[sw_cfg(1)+SW_NAME+1]=72;mem[sw_cfg(1)+"
          "SW_NAME+2]=79;mem[sw_cfg(1)+SW_NAME+3]=82;mem[sw_cfg(1)+SW_NAME+4]="
          "85;"
          "mem[sw_cfg(1)+SW_NAME+5]=83;");
    // Warm OS pages before JACK activation, including the expanded ownership
    // tables. Retain initialized values; the callback never allocates this RAM.
    const unsigned warmEnd=unsigned(variable(fx,"IO_SCHEMA"))==8?
        unsigned(variable(fx,"CONDUCTOR_BASE"))+512:unsigned(variable(fx,"I_RUNTIME_END"));
    for (unsigned i = 0; i < warmEnd; i += 512) {
      volatile double *page=cell(fx,i);*page=*page;
    }
    auto target = NSEEL_VM_regvar(fx->vm.get(), "remote_target"),
         gesture = NSEEL_VM_regvar(fx->vm.get(), "remote_gesture"),
         ok = NSEEL_VM_regvar(fx->vm.get(), "remote_ok");
    auto bridge = NSEEL_code_compile(
        fx->vm.get(),
        "remote_ok=0;remote_i=0;loop(SW_COUNT,mem[sw_committed_cfg(remote_i)+"
        "20] && "
        "mem[sw_committed_cfg(remote_i)+21]==remote_target?(sw_submit(remote_i,"
        "0,remote_gesture,0);remote_ok=1;);remote_i+=1;);",
        0);
    if (!bridge)
      throw std::runtime_error("command bridge compilation");
    auto switchReset = NSEEL_code_compile(fx->vm.get(),"sw_reset(remote_target);",0);
    if(!switchReset)throw std::runtime_error("switch reset bridge");
    auto panic_bridge =
        NSEEL_code_compile(fx->vm.get(),
                           chainMode && useJack ?
                           // Global native recovery clears live and phrase ownership
                           // below and sends channel safety in this callback. The
                           // selective phrase stop would scan the same tables first
                           // and even re-voice retained live mono notes unnecessarily.
                           "memset(TRIG_BASE,0,LAYERS);memset(HOLD_ACTIVE_BASE,0,LAYERS);"
                           "state==STATE_PLAYING?state=STATE_STOPPED;"
                           "snap_parameter_cancel();panic_pending=1;" :
                           "sw_stop_phrases();reset_note_runtime();snap_"
                           "parameter_cancel();panic_pending=1;",
                           0);
    if (!panic_bridge)
      throw std::runtime_error("panic bridge compilation");
    // A skipped chain callback must not enqueue 2,048 synthetic releases ahead
    // of current grid events. Reset ownership and emit bounded channel cleanup.
    auto panicPending = ysfx_find_var(fx, "panic_pending");
    auto chainRecovery = NSEEL_code_compile(fx->vm.get(),
        // Channel safety is emitted by the host immediately below. Do not
        // generate 2,048 EEL Note Offs only to discard them, or reset twice.
        "memset(I_QUARANTINE_BASE,0,INST_CAP*2048+INST_CAP);"
        "memset(I_FALLBACK_BASE,0,4096);memset(I_SUSTAIN_BASE,0,INST_CAP*16+16);"
        "memset(SW_PHRASE_OUT_BASE,0,SW_MEMORY_END-SW_PHRASE_OUT_BASE);"
        "reset_note_runtime();panic_pending=0;", 0);
    if (!chainRecovery) throw std::runtime_error("chain recovery bridge");
    auto phraseTarget = NSEEL_VM_regvar(fx->vm.get(), "remote_phrase");
    auto phrasePlay = NSEEL_code_compile(
        fx->vm.get(),
        "trigger_request=remote_phrase;process_phrase_trigger(0,0);", 0);
    auto phraseRecord = NSEEL_code_compile(
        fx->vm.get(), "select_phrase_record(remote_phrase);", 0);
    auto phraseClear=NSEEL_code_compile(fx->vm.get(),"set_layer_count(remote_phrase,0);mem[LEN_BASE+remote_phrase]=0;mem[TRIG_BASE+remote_phrase]=0;mem[HOLD_ACTIVE_BASE+remote_phrase]=0;mem[ONCEPOS_BASE+remote_phrase]=0;mem[FREE_FINISHED_BASE+remote_phrase]=0;free_play_error==remote_phrase+1?free_play_error=0;",0);
    if(!phraseClear)throw std::runtime_error("phrase content clear bridge");
    auto phraseStop = NSEEL_code_compile(
        fx->vm.get(),
        "finish_phrase_record();overdub_armed=0;overdub_active=0;", 0);
    if (!phrasePlay || !phraseRecord || !phraseStop)
      throw std::runtime_error("phrase bridge compilation");
    auto editI = NSEEL_VM_regvar(fx->vm.get(), "remote_edit_i"),
         editCode = NSEEL_VM_regvar(fx->vm.get(), "remote_edit_code"),
         editKind = NSEEL_VM_regvar(fx->vm.get(), "remote_edit_kind"),
         editValue = NSEEL_VM_regvar(fx->vm.get(), "remote_edit_value"),
         editRow = NSEEL_VM_regvar(fx->vm.get(), "remote_edit_row");
    auto editOp = NSEEL_VM_regvar(fx->vm.get(), "remote_edit_op"),
         editArg = NSEEL_VM_regvar(fx->vm.get(), "remote_edit_arg"),
         editResult = NSEEL_VM_regvar(fx->vm.get(), "remote_edit_result");
    auto structure =
        NSEEL_code_compile(fx->vm.get(),
                           "remote_edit_result=tf_submit(remote_edit_i,remote_"
                           "edit_op,remote_edit_arg);",
                           0);
    if (!structure)
      throw std::runtime_error("module lifecycle bridge");
    auto instrumentLifecycle = NSEEL_code_compile(fx->vm.get(),
        "remote_edit_op==0?remote_edit_result=i_add():"
        "remote_edit_result=i_submit(2,remote_edit_i,remote_target);", 0);
    if (!instrumentLifecycle) throw std::runtime_error("Instrument lifecycle bridge");
    auto edit = NSEEL_code_compile(
        fx->vm.get(),
        "remote_edit_code<7?param_apply(remote_edit_i,remote_edit_kind,remote_"
        "edit_value):mem[param_pending_addr(cc_ti(cc_index(remote_edit_i,"
        "remote_edit_code),remote_edit_row))]=remote_edit_value;",
        0);
    if (!edit)
      throw std::runtime_error("typed parameter bridge");
    auto normalized =
        NSEEL_VM_regvar(fx->vm.get(), "remote_controller_normalized");
    auto controllerApply = NSEEL_code_compile(
        fx->vm.get(),
        "remote_edit_value=param_scale(remote_edit_kind,remote_controller_"
        "normalized);"
        "remote_edit_code==0?param_apply(remote_edit_i,1,remote_edit_value):"
        "remote_edit_code<7?param_apply(remote_edit_i,remote_edit_kind,remote_"
        "edit_value):"
        "mem[param_pending_addr(cc_ti(cc_index(remote_edit_i,remote_edit_code),"
        "remote_edit_row))]=remote_edit_value;",
        0);
    auto learnKind = NSEEL_VM_regvar(fx->vm.get(), "remote_learn_kind"),
         learnCh = NSEEL_VM_regvar(fx->vm.get(), "remote_learn_ch"),
         learnNum = NSEEL_VM_regvar(fx->vm.get(), "remote_learn_num"),
         learnConflict = NSEEL_VM_regvar(fx->vm.get(), "remote_learn_conflict");
    auto learnSkip = NSEEL_VM_regvar(fx->vm.get(), "remote_learn_skip");
    auto phraseAssign = NSEEL_code_compile(fx->vm.get(),
        "mem[PHRASE_NOTE_BASE+remote_phrase]=remote_learn_num;"
        "mem[learn_phrase_channel(remote_phrase)]=remote_learn_ch+1;", 0);
    if (!phraseAssign) throw std::runtime_error("phrase trigger assignment bridge");
    auto legacyConflict = NSEEL_code_compile(
        fx->vm.get(),
        "remote_learn_conflict=0;remote_learn_j=0;loop(SW_COUNT+CONTROLLERS+"
        "LAYERS,remote_learn_j!=remote_learn_skip && learn_matches(remote_learn_j,remote_learn_kind,remote_learn_ch,"
        "remote_learn_num)?remote_learn_conflict=1;remote_learn_j+=1;);",
        0);
    auto cancelLearn = NSEEL_code_compile(fx->vm.get(), "learn_cancel();", 0);
    if (!controllerApply || !legacyConflict || !cancelLearn)
      throw std::runtime_error("controller bridge");
    Model model(fx);
    auto conductorHoldWrite=ysfx_find_var(fx,"native_hold_write"), conductorHoldRead=ysfx_find_var(fx,"native_hold_read"), conductorReleaseMask=NSEEL_VM_regvar(fx->vm.get(),"conductor_release_mask");
    std::array<double*,32> conductorReleaseQueue{};
    for(unsigned j=0;j<32;++j)conductorReleaseQueue[j]=cell(fx,unsigned(variable(fx,"NATIVE_HOLD_QUEUE_BASE"))+j);
    auto importState=ysfx_find_var(fx,"state"), importOverdub=ysfx_find_var(fx,"overdub_active");
    std::array<double*,12> importVoices{};
    std::array<double*,16> importSustain{}, importLiveSustain{};
    for(unsigned j=0;j<16;++j) {
      importSustain[j]=cell(fx,unsigned(variable(fx,"SUSTAIN_REF_BASE"))+j);
      importLiveSustain[j]=cell(fx,unsigned(variable(fx,"SW_LIVE_SUSTAIN_BASE"))+j);
    }
    for(unsigned j=0;j<12;++j) importVoices[j]=cell(fx,unsigned(variable(fx,"VOICE_ACTIVE_BASE"))+j);
    const double importRecording=variable(fx,"STATE_RECORDING"), importPlaying=variable(fx,"STATE_PLAYING"), importReady=variable(fx,"STATE_READY");
    auto importArmed=ysfx_find_var(fx,"overdub_armed");
    controller::Host controllers;
    std::unique_ptr<movement::Runtime> movementStorage(new movement::Runtime(controllers,sampleRate));
    auto &movements=*movementStorage;
    reveal::Runtime reveals(controllers,sampleRate);
    *NSEEL_VM_regvar(fx->vm.get(),"native_control_host")=1;
    *NSEEL_VM_regvar(fx->vm.get(),"ext_midi_bus")=1;
    std::array<unsigned,128> revealMasks{};std::array<double*,256> revealMaskCells{};
    for(unsigned j=0;j<256;++j)revealMaskCells[j]=cell(fx,unsigned(variable(fx,"REVEAL_TARGET_MASK_BASE"))+j);
    auto revealExisting=NSEEL_VM_regvar(fx->vm.get(),"reveal_existing_mask");
    auto revealReserved=NSEEL_VM_regvar(fx->vm.get(),"reveal_reserved_mask");
    auto revealFree=NSEEL_VM_regvar(fx->vm.get(),"reveal_free_targets");
    auto nativeControlCount=NSEEL_VM_regvar(fx->vm.get(),"native_control_count");
    const double phraseLearnBase = variable(fx, "SW_COUNT") + variable(fx, "CONTROLLERS");
    auto matchesLegacy = [&](int kind, int ch, int num, double skip) {
      *learnSkip = skip;
      *learnKind = kind;
      *learnCh = ch;
      *learnNum = num;
      NSEEL_code_execute(legacyConflict);
      return *learnConflict != 0;
    };
    std::function<bool(int, int, int)> conflicts = [&](int kind, int ch, int num) {
      return matchesLegacy(kind, ch, num, controllers.learnsCommand()
          ? phraseLearnBase + controllers.learnTarget() - 1 : -1);
    };
    auto resolveBinding = [&](const controller::Binding &b) {
      return model.bindingValue(b, true) != nullptr;
    };
    bool abRequested = false;
    auto normalizedBase = [](int k, double v) {
      return performance::normalized(k, k == 24 ? (v > 0 ? 1 : 0) : v);
    };
    auto safeApply = NSEEL_code_compile(
        fx->vm.get(),
        "snap_parameter_apply(remote_edit_i,remote_edit_code,remote_edit_row,"
        "remote_edit_kind,remote_edit_value);",
        0);
    if (!safeApply)
      throw std::runtime_error("safe descriptor parameter bridge");
    auto applyBinding = [&](const controller::Binding &b, double value) {
      if (b.kind == 16) {
        if (std::abs(model.abPosition - value) > 1e-12) {
          model.abPosition = value;
          abRequested = true;
        }
        return;
      }
      unsigned i;
      int code, row;
      if (!model.resolve(b, i, code, row, true))
        return;
      if(b.kind==25 || b.kind==26){
        const unsigned field=b.kind-25;const double physical=performance::physical(b.kind,value);
        if(std::abs(model.hostMixer[i][field]-physical)>1e-9){model.hostMixer[i][field]=physical;++model.hostMixerSequence[i][field];}
        return;
      }
      if (b.kind == 27) {
        if (auto amount = model.bindingValue(b, true))
          *amount = performance::physical(27, value);
        return;
      }
      if (b.kind >= 17) {
        *editI = i;
        *editCode = code;
        *editRow = row;
        *editKind = b.kind;
        *editValue = performance::physical(b.kind, value);
        NSEEL_code_execute(safeApply);
        return;
      }
      if (code == -1) {
        *model.phrase[i][row] = performance::physical(b.kind, value);
        return;
      }
      *editI = i;
      *editCode = code;
      *editKind = b.kind;
      *editRow = row;
      *normalized = value;
      NSEEL_code_execute(controllerApply);
    };
    sockaddr_un address{};
    address.sun_family = AF_UNIX;
    if (std::strlen(argv[2]) >= sizeof address.sun_path)
      throw std::runtime_error("socket path too long");
    std::strcpy(address.sun_path, argv[2]);
    listener = socket(AF_UNIX, SOCK_STREAM, 0);
    if (listener < 0 || bind(listener, reinterpret_cast<sockaddr *>(&address),
                             sizeof address) < 0)
      throw std::runtime_error("socket bind (choose an unused path)");
    bound = true;
    chmod(argv[2], 0600);
    if (listen(listener, 16) < 0)
      throw std::runtime_error("socket listen");
    std::signal(SIGINT, stop);
    std::signal(SIGTERM, stop);
    std::signal(SIGPIPE, SIG_IGN);
    std::unique_ptr<Queue<Request, 8>> commandStorage(
        new Queue<Request, 8>());
    std::unique_ptr<Queue<Reply, 8>> replyStorage(new Queue<Reply, 8>());
    auto &commands = *commandStorage;
    auto &replies = *replyStorage;
    std::atomic<bool> shutdown{false}, paused{false}, loading{false};
    std::thread io;
    std::unique_ptr<performance::Snapshots> performanceSnapshots(
        new performance::Snapshots());
    struct PerformanceTarget {
      performance::Key key;
      controller::Binding binding;
      uint32_t id = 0;
      uint64_t token = 0;
      double goal = 0;
      bool active = false;
      int legacyCurve = -1;
      uint32_t snapshotId = 0;
    };
    std::unique_ptr<std::array<PerformanceTarget, 2048>> performanceTargets(
        new std::array<PerformanceTarget, 2048>());
    unsigned performanceTargetCount = 0;
    uint32_t performanceNextTarget = 8388608;
    uint32_t performanceTargetSnapshot = 0;
    double performanceMorphAt = 0, performanceMorphSeconds = 0;
    unsigned performanceSkipped = 0;
    Snapshot state;
    std::unique_ptr<echocity::Runtime> echoStorage(new echocity::Runtime(sampleRate));
    auto &echoRuntime=*echoStorage;
    std::unique_ptr<expressive::StreamRuntime<256>> expressiveStream(
        new expressive::StreamRuntime<256>(sampleRate));
    bool expressiveCancelPending=false;
    std::unique_ptr<echocity::SourceJournal<>> echoJournal(new echocity::SourceJournal<>());
    auto echoHost=NSEEL_VM_regvar(fx->vm.get(),"native_echo_sources");
    auto echoRead=NSEEL_VM_regvar(fx->vm.get(),"native_echo_read");
    auto echoWrite=NSEEL_VM_regvar(fx->vm.get(),"native_echo_write");
    auto echoOverflow=NSEEL_VM_regvar(fx->vm.get(),"native_echo_overflow");
    bool echoProtocol=false,echoRecovering=false;
    auto echoCapacity=ysfx_find_var(fx,"NATIVE_ECHO_SOURCE_CAP");
    state.echoAvailable=chainMode && model.schema==8 && echoCapacity && *echoCapacity==8192;
    std::unique_ptr<std::array<EEL_F*,8192*6>> echoCells(new std::array<EEL_F*,8192*6>());
    if(state.echoAvailable)for(unsigned j=0;j<echoCells->size();++j)(*echoCells)[j]=cell(fx,29000000+j);
    if(state.echoAvailable)ysfx_set_midi_capacity(fx,524288,false);
    std::array<unsigned,8192> echoOrders{};
    std::unique_ptr<std::array<echocity::SourceEvent,16384>> echoTimeline(new std::array<echocity::SourceEvent,16384>());
    volatile echocity::SourceEvent *echoWarm=echoTimeline->data();for(unsigned j=0;j<echoTimeline->size();++j)echoWarm[j].order=0;
    state.backend = useJack;
    state.sampleRate = sampleRate;
    state.blockSize = blockSize;
    auto learnedRelease=NSEEL_VM_regvar(fx->vm.get(),"remote_learn_release");
    auto smartQuarantine=NSEEL_code_compile(fx->vm.get(),"learn_quarantine(remote_learn_kind,remote_learn_ch,remote_learn_num,remote_learn_release);",0);
    if(!smartQuarantine)throw std::runtime_error("switch learn bridge");
    auto captureSwitch=[&](const uint8_t* data,unsigned size){
      if(!state.switchLearnTarget||size!=3)return false;
      int kind=(data[0]&240)==144&&data[2]>0?1:(data[0]&240)==176&&data[1]<128?2:0;
      if(!kind)return false;
      int si=-1;for(unsigned j=0;j<model.switchCapacity;++j)if(*model.sw[j][0]&&*model.sw[j][1]==state.switchLearnTarget)si=j;
      if(si<0){state.switchLearnTarget=0;return false;}
      unsigned ch=data[0]&15,num=data[1];bool conflict=matchesLegacy(kind,ch,num,si);
      for(const auto &source:controllers.configuration().sources)conflict|=source.id&&source.kind==kind&&source.channel==ch&&source.number==num;
      state.switchLearnConflict=conflict;if(conflict)return true;
      int press=kind==1?127:data[2],release=kind==2&&press==0?127:0;
      *model.switchFields[si][0]=1;*model.switchFields[si][2]=kind;*model.switchFields[si][3]=ch;*model.switchFields[si][4]=num;*model.switchFields[si][12]=press;*model.switchFields[si][13]=release;
      *learnKind=kind;*learnCh=ch;*learnNum=num;*learnedRelease=release;NSEEL_code_execute(smartQuarantine);
      state.switchLearnTarget=0;++state.revision;return true;
    };

    int lastRecallStatus = 0;
    bool abActive = false;
    struct ABTarget {
      unsigned slot = 0;
      uint64_t token = 0;
      double a = 0, b = 0;
    };
    std::array<ABTarget, 2048> abTargets{};
    unsigned abCount = 0, abSkipped = 0;
    auto cancelPending =
        NSEEL_code_compile(fx->vm.get(),
                           "snap_parameter_cancel_target(remote_edit_i,remote_"
                           "edit_row,remote_edit_kind);",
                           0);
    if (!cancelPending)
      throw std::runtime_error("pending target cancellation");
    auto cancelPerformance = [&](PerformanceTarget &p, uint64_t token) {
      auto t = controllers.target(p.id);
      bool owned =
          t && t->token == token && (t->owner == 0 || t->owner == UINT32_MAX);
      controllers.cancelPerformanceTarget(p.id, token);
      unsigned i;
      int c, r;
      if (owned && p.binding.kind >= 18 && p.binding.kind<=24 &&
          model.resolve(p.binding, i, c, r, true)) {
        *editI = i;
        *editRow = r;
        *editKind = p.binding.kind;
        NSEEL_code_execute(cancelPending);
      }
    };
    auto cancelAB = [&]() {
      for (unsigned j = 0; j < abCount; ++j) {
        auto &p = (*performanceTargets)[abTargets[j].slot];
        cancelPerformance(p, abTargets[j].token);
      }
      abCount = 0;
      abActive = false;
      abRequested = false;
    };
    auto recallSnapshot = [&](uint32_t snapshotId, bool timed,
                              const performance::Record *supplied) {
      if (!supplied)
        cancelAB();
      int status = 0;
      const auto *r =
          supplied ? supplied : performanceSnapshots->find(snapshotId);
      std::array<controller::Transition, 2048> transitions{};
      std::array<unsigned, 2048> slots{};
      std::array<double, 2048> starts{};
      unsigned n = 0, newTargets = 0, skipped = 0;
      bool valid = r != nullptr;
      if (r)
        for (unsigned j = 0; valid && j < r->state.count; ++j) {
          const auto &v = r->state.values[j];
          if (!v.included)
            continue;
          controller::Binding b;
          b.instrument = v.key.instrument;
          b.module = v.key.module;
          b.kind = v.key.kind;
          auto address = model.bindingValue(b, true);
          if (!address) {
            ++skipped;
            continue;
          }
          unsigned slot = 0;
          while (slot < performanceTargetCount &&
                 !((*performanceTargets)[slot].key == v.key))
            ++slot;
          if (slot == performanceTargetCount) {
            if (slot == 2048) {
              valid = false;
              break;
            }
            auto &p = (*performanceTargets)[slot];
            p.key = v.key;
            p.binding = b;
            ++performanceTargetCount;
          }
          auto &p = (*performanceTargets)[slot];
          uint32_t mapped = 0;
          for (const auto &mapping : controllers.configuration().bindings)
            if (mapping.policy.id && mapping.instrument == b.instrument &&
                mapping.module == b.module && mapping.kind == b.kind)
              mapped = mapping.policy.target;
          if (mapped)
            p.id = mapped;
          if (!p.id) {
            while (controllers.target(performanceNextTarget))
              ++performanceNextTarget;
            p.id = performanceNextTarget++;
          }
          if (!controllers.target(p.id))
            ++newTargets;
          slots[n] = slot;
          starts[n] = normalizedBase(b.kind, *address);
          transitions[n].target = p.id;
          transitions[n].goal = performance::normalized(b.kind, v.effective);
          transitions[n].seconds = timed ? r->seconds : 0;
          transitions[n].ease = r->ease;
          bool discrete = performance::discrete(b.kind);
          transitions[n].switching =
              discrete ? r->switching : controller::Switch::Continuous;
          ++n;
        }
      if (valid && !n && skipped)
        status = 2;
      valid = valid && n > 0 && newTargets <= controllers.freeTargets();
      if (valid) {
        for (unsigned j = 0; j < n; ++j)
          controllers.stagePerformanceTarget(transitions[j].target, starts[j]);
        valid = controllers.morphBatch(transitions.data(), n);
        if (valid) {
          performanceSnapshots->selected = r->id;
          performanceSkipped = skipped;
          performanceTargetSnapshot = r->id;
          performanceMorphAt = controllers.time;
          performanceMorphSeconds = timed ? r->seconds : 0;
          for (unsigned j = 0; j < n; ++j) {
            auto &p = (*performanceTargets)[slots[j]];
            p.token = controllers.target(p.id)->token;
            p.goal = transitions[j].goal;
            p.active = true;
            p.snapshotId = r->id;
            p.legacyCurve = model.legacyCurve(p.binding);
          }
        }
      }
      lastRecallStatus = valid ? 0 : status ? status : 3;
      return lastRecallStatus;
    };
    auto resolveMovement=[&](const controller::Binding &binding,uint32_t &id,double &effective){
      auto address=model.bindingValue(binding);if(!address||binding.kind==16)return false;
      performance::Key key;key.instrument=binding.instrument;key.module=binding.module;key.kind=binding.kind;
      unsigned slot=0;while(slot<performanceTargetCount&&!((*performanceTargets)[slot].key==key))++slot;
      if(slot==performanceTargetCount){if(slot==2048)return false;auto &p=(*performanceTargets)[slot];p.key=key;p.binding=binding;++performanceTargetCount;}
      auto &p=(*performanceTargets)[slot];
      for(const auto &b:controllers.configuration().bindings)if(b.policy.id&&b.instrument==binding.instrument&&b.module==binding.module&&b.kind==binding.kind)p.id=b.policy.target;
      if(!p.id){while(controllers.target(performanceNextTarget))++performanceNextTarget;p.id=performanceNextTarget++;}
      id=p.id;effective=normalizedBase(binding.kind,*address);
      return controllers.target(id)||controllers.stagePerformanceTarget(id,effective);
    };
    auto snapHostEnabled = NSEEL_VM_regvar(fx->vm.get(), "snap_host_enabled");
    auto snapHostCancel = NSEEL_VM_regvar(fx->vm.get(), "snap_host_cancel");
    auto snapHostRead = NSEEL_VM_regvar(fx->vm.get(), "snap_host_read");
    auto snapHostWrite = NSEEL_VM_regvar(fx->vm.get(), "snap_host_write");
    unsigned snapHostBase = unsigned(variable(fx, "I_RUNTIME_END"));
    const unsigned snapshotParameterBase=model.schema==8?unsigned(variable(fx,"NATIVE_SNAPSHOT_PARAMETER_BASE")):snapHostBase+520;
    const unsigned snapshotParameterSlots=24+model.phraseCapacity*3+48;
    for (unsigned j=0;j<snapshotParameterSlots*4;++j)
      *cell(fx,snapshotParameterBase+j)=0;
    std::array<double *, 520> snapHostCells{};
    for (unsigned j = 0; j < snapHostCells.size(); ++j)
      snapHostCells[j] = cell(fx, snapHostBase + j);
    *snapHostEnabled = 1;
    *snapHostRead = *snapHostWrite = 0;
    for (unsigned j = 288; j < snapHostCells.size(); ++j)
      *snapHostCells[j] = 0;
    std::array<double*,384> switchActionCells{};
    const auto switchActionBase=model.schema==8?unsigned(variable(fx,"NATIVE_SNAPSHOT_ACTION_BASE")):snapHostBase;
    for(unsigned j=0;j<model.switchCapacity*6;++j)switchActionCells[j]=cell(fx,switchActionBase+j);
    auto syncSwitchActions = [&]() {
      for (unsigned j = 0; j < model.switchCapacity*6; ++j)
        *switchActionCells[j] = 0;
      for (const auto &a : performanceSnapshots->switchActions())
        if (a.switchId)
          for (unsigned si = 0; si < model.switchCapacity; ++si)
            if (*model.sw[si][0] && *model.sw[si][1] == a.switchId) {
              *switchActionCells[si * 6 + a.gesture * 2] = a.action;
              *switchActionCells[si * 6 + a.gesture * 2 + 1] = a.snapshotId;
            }
    };
    auto updateAB = [&]() {
      if (!abRequested)
        return;
      abRequested = false;
      auto &config = performanceSnapshots->ab;
      const auto *a = performanceSnapshots->find(config.a),
                 *b = performanceSnapshots->find(config.b);
      if (!a || !b) {
        cancelAB();
        return;
      }
      double x = controller::clamp(model.abPosition);
      if (config.ease)
        x = x * x * (3 - 2 * x);
      if (!abActive) {
        performance::Record blend = *a;
        blend.state.count = 0;
        abSkipped = 0;
        for (unsigned j = 0; j < a->state.count; ++j) {
          const auto &va = a->state.values[j];
          if (!va.included)
            continue;
          const performance::Value *vb = nullptr;
          for (unsigned k = 0; k < b->state.count; ++k)
            if (b->state.values[k].included && va.key == b->state.values[k].key)
              vb = &b->state.values[k];
          controller::Binding binding;
          binding.instrument = va.key.instrument;
          binding.module = va.key.module;
          binding.kind = va.key.kind;
          if (!vb || !model.bindingValue(binding, true) ||
              (va.key.kind == 14 &&
               (va.effective <= 0 || vb->effective <= 0))) {
            ++abSkipped;
            continue;
          }
          auto &out = blend.state.values[blend.state.count++];
          out = va;
          out.effective = performance::discrete(va.key.kind)
                              ? (x < .5 ? va.effective : vb->effective)
                          : va.key.kind == 14
                              ? std::pow(2, (1 - x) * std::log2(va.effective) +
                                                x * std::log2(vb->effective))
                              : (1 - x) * va.effective + x * vb->effective;
        }
        if (!blend.state.count || recallSnapshot(blend.id, false, &blend) != 0)
          return;
        abCount = 0;
        for (unsigned j = 0; j < blend.state.count; ++j) {
          const auto &v = blend.state.values[j];
          unsigned slot = 0;
          while (slot < performanceTargetCount &&
                 !((*performanceTargets)[slot].key == v.key))
            ++slot;
          if (slot == performanceTargetCount)
            continue;
          auto &p = (*performanceTargets)[slot];
          auto &t = abTargets[abCount++];
          t.slot = slot;
          for (unsigned k = 0; k < a->state.count; ++k)
            if (a->state.values[k].key == v.key)
              t.a = performance::normalized(v.key.kind,
                                            a->state.values[k].effective);
          for (unsigned k = 0; k < b->state.count; ++k)
            if (b->state.values[k].key == v.key)
              t.b = performance::normalized(v.key.kind,
                                            b->state.values[k].effective);
          t.token = controllers.acquirePerformanceTarget(
              p.id, performance::normalized(v.key.kind, v.effective));
          p.token = t.token;
          p.active = false;
        }
        abActive = true;
        performanceSnapshots->selected = 0;
        performanceMorphSeconds = 0;
      }
      for (unsigned j = 0; j < abCount; ++j) {
        auto &t = abTargets[j];
        auto &p = (*performanceTargets)[t.slot];
        double value = performance::discrete(p.binding.kind)
                           ? (x < .5 ? t.a : t.b)
                           : (1 - x) * t.a + x * t.b;
        if (t.token &&
            controllers.updatePerformanceTarget(p.id, t.token, value))
          applyBinding(p.binding, value);
      }
    };
    auto publishPerformance = [&]() {
      state.performanceCount = performanceSnapshots->count;
      state.snapshotActions = performanceSnapshots->switchActions();
      state.ab = performanceSnapshots->ab;
      state.ab.position = model.abPosition;
      state.abSkipped = abSkipped;
      state.abOverridden = 0;
      for (unsigned j = 0; j < abCount; ++j) {
        auto &p = (*performanceTargets)[abTargets[j].slot];
        auto t = controllers.target(p.id);
        if (!t || t->owner != UINT32_MAX || t->token != abTargets[j].token)
          ++state.abOverridden;
      }
      state.performanceSelected = performanceSnapshots->selected;
      state.performanceSkipped = performanceSkipped;
      state.performanceProgress =
          performanceMorphSeconds > 0
              ? controller::clamp((controllers.time - performanceMorphAt) /
                                  performanceMorphSeconds)
              : 1;
      state.performanceTarget =
          state.performanceProgress < 1 ? performanceTargetSnapshot : 0;
      auto current = model.effectiveState();
      for (unsigned j = 0; j < state.performanceCount; ++j) {
        const auto &r = performanceSnapshots->at(j);
        state.performanceIds[j] = r.id;
        state.performanceSizes[j] = r.state.count;
        std::memcpy(state.performanceNames[j].data(), r.name, 49);
        state.performanceSeconds[j] = r.seconds;
        state.performanceEase[j] = int(r.ease);
        state.performanceSwitch[j] = int(r.switching);
        state.performanceDirty[j] = performanceSnapshots->dirty(r.id, current);
      }
    };
    std::array<bool, 2048> held{};
    struct MidiPacket {
      unsigned size = 0, offset = 0, order = 0, bus = 0;
      std::array<uint8_t, 256> data{};
    };
    std::unique_ptr<std::array<MidiPacket, 8192>> outputQueue(
        new std::array<MidiPacket, 8192>());
    // A processing-block batch and index order are allocated once at startup.
    // Sort indices, not 256-byte packets; timestamp ties preserve generation
    // order.
    std::unique_ptr<std::array<MidiPacket, 8192>> outputBatch(
        new std::array<MidiPacket, 8192>());
    std::unique_ptr<std::array<unsigned, 8192>> outputOrder(
        new std::array<unsigned, 8192>());
    std::unique_ptr<std::array<MidiPacket, 8192>> expressiveBatch(
        new std::array<MidiPacket, 8192>());
    unsigned outputRead = 0, outputWrite = 0;
    std::atomic<unsigned> outputPending{0};
    std::atomic<bool> finalAcknowledged{false};
    bool muted = false, overflowRecovery = false;
    std::unique_ptr<std::array<MidiPacket, 8192>> inputQueue(
        new std::array<MidiPacket, 8192>());
    unsigned inputRead = 0, inputWrite = 0;
    struct NativeControl {unsigned offset=0,order=0,sequence=0,kind=0,slot=0,mask=0;uint64_t id=0;};
    std::unique_ptr<std::array<NativeControl,8328>> nativeControls(new std::array<NativeControl,8328>());

    std::atomic<uint64_t> xruns{0};
    PanicSweep panicSweep;
    uint64_t tracedNotes=0,tracedNoteOns=0,tracedCCs=0,tracedOrderErrors=0;
    unsigned tracedLastOffset=0;bool tracedHaveOutput=false;
    auto traceWrite=[&](unsigned offset){if(!rtTrace)return;if(tracedHaveOutput&&offset<tracedLastOffset)++tracedOrderErrors;tracedLastOffset=offset;tracedHaveOutput=true;};
    auto flushOutput = [&](void *buffer, jack_nframes_t frames) {
      unsigned budget = 64;
      while (outputRead != outputWrite && budget--) {
        auto &m = (*outputQueue)[outputRead % 8192];
        if (jack_midi_event_write(buffer, std::min(m.offset, frames - 1),
                                  m.data.data(), m.size)) {
          ++state.midiWriteFailures; // Retry later; not a dropped event yet.
          break;
        }
        ++state.midiWritten;
        traceWrite(std::min(m.offset,frames-1));
        if(rtTrace && m.size>=3){unsigned type=m.data[0]&240;if(type==128||type==144){++tracedNotes;if(type==144&&m.data[2])++tracedNoteOns;}else if(type==176)++tracedCCs;}
        ++outputRead;
      }
    };
    auto deadline = std::chrono::steady_clock::now();
    const auto period =
        std::chrono::nanoseconds(uint64_t(1e9 * blockSize / sampleRate));
    std::cout << "READY " << argv[2] << std::endl;
    // Large fixed command records must not consume JACK's small callback stack.
    // Allocate them once; the sole processing thread owns these scratch
    // buffers.
    std::unique_ptr<std::array<Reply, 8>> pendingStorage(
        new std::array<Reply, 8>());
    std::unique_ptr<Request> processingRequest(new Request());
    struct MovementPhysical {unsigned offset=0,ch=0,cc=0,value=0;};
    std::array<MovementPhysical,136> movementPhysical{};
    size_t nativeClearCursor=nativeClearPages.size();unsigned nativeClearOffset=0;
    auto clearNativeChunk = [&]() {
      unsigned budget=262144; // At most 2 MiB; no allocation or VM lookup here.
      while(budget && nativeClearCursor<nativeClearPages.size()) {
        const auto &page=nativeClearPages[nativeClearCursor];
        unsigned n=std::min(budget,page.count-nativeClearOffset);
        std::memset(static_cast<void*>(page.data+nativeClearOffset),0,n*sizeof(EEL_F));
        budget-=n;nativeClearOffset+=n;
        if(nativeClearOffset==page.count){++nativeClearCursor;nativeClearOffset=0;}
      }
    };
    int programChannel = 0; // Global host reservation, 0 disables it; never a patch parameter.
    std::function<int(jack_nframes_t)> process = [&](jack_nframes_t frames) {
      realtime_trace::Trace::Scope trace(rtTrace.get(),state.samples,frames);
      if(rtTrace)trace.value.jackFrame=useJack?jack_last_frame_time(jack):state.samples;
      const uint64_t noteStart=tracedNotes,noteOnStart=tracedNoteOns,ccStart=tracedCCs,orderStart=tracedOrderErrors;
      tracedHaveOutput=false;
      movements.block(frames);
      void *outBuffer =
          useJack ? jack_port_get_buffer(midiOut, frames) : nullptr;
      auto drainPanic = [&]() {
        panicSweep.drain(64,[&](const std::array<uint8_t,3>& event) {
          if(outBuffer && jack_midi_event_write(outBuffer,frames-1,event.data(),event.size())) {
            ++state.midiWriteFailures;return false;
          }
          ++state.midiGenerated;++state.midi;state.last_sample=state.samples+frames-1;
          state.last_status=event[0];state.last_note=event[1];state.last_value=0;
          if(outBuffer){++state.midiWritten;traceWrite(frames-1);if(rtTrace)++tracedNotes;}
          return true;
        });
      };
      auto cleanupChain = [&]() {
        ++state.midiRecoveries;
        state.midiDropped += outputWrite-outputRead;
        outputRead = outputWrite;
        nativeClearCursor=0;nativeClearOffset=0;
        // An explicit global stop is already silent. Bound its cold-table work
        // across callbacks, admitting queued inputs/commands only when complete.
        // A running grid recovery retains its synchronous transport semantics.
        if(chain.run || chain.recording || chain.armed)
          while(nativeClearCursor<nativeClearPages.size())clearNativeChunk();
        *nativeHostBulkClear=nativeClearPages.empty()?0:1;
        NSEEL_code_execute(chainRecovery);
        *nativeHostBulkClear=0;
        ysfx_midi_clear(fx->midi.out.get());
        if (panicSweep.remaining()) jack_midi_clear_buffer(outBuffer);
        bool complete = true;
        for (unsigned ch = 0; ch < 16; ++ch)
          for (unsigned cc : {64u, 66u, 69u, 123u, 120u}) {
            uint8_t data[] = {uint8_t(176 | ch), uint8_t(cc), 0};
            ++state.midiGenerated;
            if (jack_midi_event_write(outBuffer, 0, data, 3)) {
              ++state.midiWriteFailures;
              ++state.midiDropped;
              complete = false;
              overflowRecovery = true;
              ++state.outputOverflow;
            } else {
              ++state.midiWritten;
              traceWrite(0);if(rtTrace)++tracedCCs;
              ++state.midi;
              state.last_sample = state.samples;
              state.last_status = 176 | ch;
              state.last_note = cc;
              state.last_value = 0;
            }
          }
        if (complete) { held.fill(false); state.active = 0; }
      };
      bool recovering = overflowRecovery;
      if(echoRecovering && !panicSweep.remaining()){
        echoRuntime.recovered();echoRecovering=false;*echoRead=*echoWrite=*echoOverflow=0;
        held.fill(false);state.active=0;
      }
      overflowRecovery = false;
      if (outBuffer) {
        jack_midi_clear_buffer(outBuffer);
        if (recovering) {
          ++state.midiRecoveries;
          state.midiDropped += outputWrite-outputRead + inputWrite-inputRead;
          reveals.panic();movements.panic();
          controllers.panic();
          outputRead = outputWrite;
          inputRead = inputWrite;
          ysfx_midi_clear(fx->midi.in.get());
          NSEEL_code_execute(panic_bridge);
          for (unsigned ch = 0; ch < 16; ++ch)
            for (unsigned cc : {64u, 123u, 120u}) {
              uint8_t data[] = {uint8_t(176 | ch), uint8_t(cc), 0};
              ++state.midiGenerated;
              if (jack_midi_event_write(outBuffer, 0, data, 3)) {
                ++state.midiWriteFailures;++state.midiDropped;
                overflowRecovery = true;
              } else {++state.midiWritten;traceWrite(0);if(rtTrace)++tracedCCs;}
            }
        } else
          flushOutput(outBuffer, frames);
      }
      if (useJack) {
        void *in = jack_port_get_buffer(midiIn, frames);
        unsigned n = jack_midi_get_event_count(in);
        trace.value.inputEvents=n;
        state.midiReceived+=n;
        for (unsigned i = 0; i < n; ++i) {
          jack_midi_event_t e;
          if (jack_midi_event_get(&e, in, i) || muted || recovering || echoRecovering ||
              loading.load(std::memory_order_acquire)) {
            ++state.midiDropped;
          } else {
            if (programChannel && e.size==2 && (e.buffer[0]&240)==192 &&
                (e.buffer[0]&15)==programChannel-1) continue;
            if (inputWrite - inputRead >= 8192 || e.size > 256) {
              ++state.midiDropped;
              ++state.outputOverflow;
              overflowRecovery = true;
            } else {
              ++state.midiInputAccepted;
              auto &m = (*inputQueue)[inputWrite++ % 8192];
              m.size = e.size;
              m.offset = e.time;
              std::memcpy(m.data.data(), e.buffer, e.size);
            }
          }
        }
      }
      if (paused.load(std::memory_order_acquire)) {
        for (unsigned q = inputRead; q != inputWrite; ++q)
          (*inputQueue)[q % 8192].offset = 0;
        return 0;
      }
      if(nativeClearCursor<nativeClearPages.size()) {
        clearNativeChunk();
        if(nativeClearCursor<nativeClearPages.size()) {
          for(unsigned q=inputRead;q!=inputWrite;++q)(*inputQueue)[q%8192].offset=0;
          if(outBuffer)flushOutput(outBuffer,frames);
          drainPanic();state.pendingOutput=outputWrite-outputRead+panicSweep.remaining();
          outputPending.store(state.pendingOutput,std::memory_order_release);
          state.late=xruns.load(std::memory_order_relaxed);
          state.samples+=frames;++state.blocks;
          trace.value.xruns=state.late;trace.value.pending=state.pendingOutput;
          return 0;
        }
      }
      unsigned movementOutputCount=0,movementPhysicalCount=0;
      unsigned generatedOrder=0;uint64_t generatedAt=UINT64_MAX;
      auto emitControlled=[&](uint64_t sample,unsigned ch,unsigned cc,unsigned value){
        if(movementOutputCount>=8192){++state.midiGenerated;++state.midiDropped;return false;}
        auto &m=(*outputBatch)[movementOutputCount++];m.size=3;m.offset=unsigned(sample>state.samples?sample-state.samples:0);m.data[0]=176|ch;m.data[1]=cc;m.data[2]=value;m.order=sample==generatedAt?generatedOrder:0;m.bus=0;return true;
      };
      auto emitMovement=[&](uint64_t sample,unsigned ch,unsigned cc,unsigned value){reveals.observe(ch,cc,value);return emitControlled(sample,ch,cc,value);};
      auto applyMovement=[&](const controller::Binding &b,double value){if(!model.bindingValue(b))return false;applyBinding(b,value);return true;};
      unsigned inputBudget = 128;
      while (inputRead != inputWrite && inputBudget--) {
        auto &m = (*inputQueue)[inputRead++ % 8192];
        ysfx_midi_event_t e{};
        e.offset = std::min(m.offset, frames - 1);
        e.size = m.size;
        e.data = m.data.data();
        auto before = controllers.learnTarget();
        if (captureSwitch(e.data,e.size) || controllers.midi(e.data, e.size,
                             (state.samples + e.offset) / double(sampleRate),
                             conflicts)) {
          if (before && !controllers.learnTarget()) {
            cancelAB();
            ++state.revision;
          }
          continue;
        }
        if(e.size==3&&(e.data[0]&240)==176){auto &p=movementPhysical[movementPhysicalCount++];p.offset=e.offset;p.ch=e.data[0]&15;p.cc=e.data[1];p.value=e.data[2];}
        if (!ysfx_send_midi(fx, &e)) {
          ++state.midiDropped;
          ++state.outputOverflow;
          overflowRecovery = true;
        }
      }
      for (unsigned q = inputRead; q != inputWrite; ++q)
        (*inputQueue)[q % 8192].offset = 0;
      trace.mark(1);
      auto start = std::chrono::steady_clock::now();
      jack_position_t position{};
      bool rolling =
          chainMode && jack ? jack_transport_query(jack, &position) == JackTransportRolling
             : true;
      auto frame = jack ? uint64_t(position.frame) : state.samples;
      double bpm =
          position.valid & JackPositionBBT ? position.beats_per_minute : 120.;
      if (!std::isfinite(bpm) || bpm < 30 || bpm > 240)
        bpm = 120.;
      auto tickChain=[&](){
        if (chain.tick(frame, frames, sampleRate, rolling, bpm,
                       jack ? uint64_t(jack_last_frame_time(jack)) : state.samples)) {
          movementOutputCount=0;reveals.panic();movements.panic();
          controllers.panic();
          if (chain.run && outBuffer) {
            cleanupChain();
          } else
            NSEEL_code_execute(panic_bridge);
        }
      };
      // Validate the completed take's audio continuity BEFORE FINISH/STOP can
      // commit it. Otherwise a command arriving on a missed cycle can hide the
      // gap by clearing recording first. Grid admission remains after commands.
      if(chainMode && !chain.gridCapture)tickChain();
      auto &pending = *pendingStorage;
      unsigned count = 0;
      bool maintenance = false;
      auto &request = *processingRequest;
      while (count < 8 && replies.free() > count && commands.pop(request)) {
        auto &reply = pending[count++];
        reply.status = 0;
        reply.detailRevision = 0;
        reply.id = request.id;
        if(request.op==5||request.op==42){state.switchLearnTarget=0;state.switchLearnConflict=false;}
        if (request.op != 0 &&
            ((request.session && request.session != engineSession) ||
             (request.op != 2 && request.revision != state.revision && request.revision != -1)))
          reply.status = 1;
        else if (request.op == 35) {
          // Transactional interchange: stopped processor only. No parsing, copying
          // event vectors or filesystem work occurs in the real-time callback.
          if (chain.recording || chain.armed || *importOverdub>.5 ||
              (request.arg==2 && (*importState==importReady || *importArmed>.5)) ||
              *importState==importRecording ||
              (request.arg==1 && (state.active>0 || chain.run ||
               *importState==importPlaying ||
               std::any_of(importVoices.begin(),importVoices.end(),[](double* p){return *p>.5;}))) ||
              (request.arg==2 && ((*model.musicalState==3 && *model.phraseTriggers[request.target]>.5 && *model.phrase[request.target][1]<.5 && *model.phrase[request.target][0]>0) ||
               [&](){for(unsigned j=0;j<12;++j)if(*model.voiceActive[j]>.5 && *model.voiceLayer[j]==request.target)return true;return false;}()))) reply.status=3;
          else if(request.arg==2){*phraseTarget=request.target;NSEEL_code_execute(phraseClear);++state.revision;}
          else { maintenance=true; if(request.arg!=0) ++state.revision; }
        }
        else if(request.op==51 || request.op==52){
          bool busy=state.active||chain.run||chain.recording||chain.armed||movements.active;
          for(unsigned j=0;j<model.switchCapacity;++j)busy|=*model.switchPressed[j]>.5;
          if(busy)reply.status=3;
          else if(request.op==51){
            int slot=-1;unsigned next=std::max(1u,unsigned(*cell(fx,unsigned(variable(fx,"DS_CFG_BASE"))+1)));
            for(unsigned j=0;j<model.switchCapacity;++j){if(!*model.sw[j][0]&&slot<0)slot=j;if(*model.sw[j][0])next=std::max(next,unsigned(*model.sw[j][1])+1);}
            if(slot<0||next>16777215)reply.status=3;
            else{for(unsigned j=0;j<128;++j){
                // Legacy slots also carry four phrase/controller settings.
                // Reusing a deleted switch must retain those unrelated fields.
                if(slot<4&&((j>=24&&j<32)||(j>=112&&j<120)))continue;
                *model.switchFields[slot][j]=0;
              }
              auto &v=model.switchFields[slot];*v[0]=1;*v[4]=std::min(127,60+slot);*v[7]=300;*v[8]=800;*v[12]=127;*v[14]=1;*v[17]=slot;*v[18]=slot;*v[19]=slot;*v[20]=1;*v[21]=next;
              *cell(fx,unsigned(variable(fx,"DS_CFG_BASE"))+1)=next+1;*target=slot;NSEEL_code_execute(switchReset);++state.revision;}
          }else reply.status=3;
        }
        else if(request.op==54){
          if(!state.echoAvailable || (!echoProtocol && state.active))reply.status=3;
          for(const auto &c:request.echoConfig)if(c.id){bool found=false;
            for(unsigned j=0;j<8;++j)found|=*model.inst[j][0]>.5 && *model.inst[j][1]==c.instrument;
            if(!found)reply.status=2;
          }
          if(!reply.status){echoRuntime.configure(request.echoConfig);++state.revision;}
        }
        else if(request.op==55){
          auto previousExpressive=model.expressiveConfiguration();
          if(!model.expressiveTargets(request.expressiveConfig))reply.status=2;
          else{
            model.loadExpressive(request.expressiveConfig);
            for(const auto &binding:controllers.configuration().bindings)
              if(binding.policy.id && binding.kind==27 && !model.bindingValue(binding))
                reply.status=2;
            if(reply.status)model.loadExpressive(previousExpressive);
            else{
              for(const auto &setting:request.expressiveConfig){
                auto prior=std::find_if(previousExpressive.begin(),previousExpressive.end(),
                  [&](const auto &old){return old.instrument==setting.instrument &&
                    old.curveModule==setting.curveModule;});
                if(prior!=previousExpressive.end() &&
                   std::abs(prior->curve.amount-setting.curve.amount)>1e-9)
                  controllers.recall(setting.instrument,setting.curveModule,27,
                    performance::normalized(27,setting.curve.amount));
              }
              expressiveCancelPending=true;++state.revision;
            }
          }
        }
        else if(request.op==53){
          if(request.value>16)reply.status=3;
          else {programChannel=int(request.value);++state.revision;}
        }
        else if(request.op==50){
          if(request.arg==1){state.switchLearnTarget=0;state.switchLearnConflict=false;}
          else{
            bool busy=state.active||chain.run||chain.recording||chain.armed||movements.active;
            for(unsigned j=0;j<12;++j)busy|=*model.voiceActive[j]>.5;
            for(unsigned j=0;j<model.switchCapacity;++j)busy|=*model.switchPressed[j]>.5;
            bool found=false;for(unsigned j=0;j<model.switchCapacity;++j)found|=*model.sw[j][0]&&*model.sw[j][1]==request.target;
            if(busy||!found)reply.status=3;else{controllers.cancel();NSEEL_code_execute(cancelLearn);state.switchLearnTarget=request.target;state.switchLearnConflict=false;}
          }
        }
        else if(request.op==49){
          // Safe instances latch the policy. Legacy mono/ARP LOOP has no
          // independent route ledger, so refuse an edit until it is stopped.
          bool unsafeLoop=*model.phrase[request.target][1]<.5 && *model.musicalState==3 &&
              *model.phraseTriggers[request.target]>.5 && *model.instances[12+request.target][6]<0;
          if(unsafeLoop)reply.status=3;
          else {*model.phrase[request.target][10]=request.value;++state.revision;}
        }
        else if(request.op==45){
          bool found=false;
          for(unsigned si=0;si<model.switchCapacity;++si)if(*model.sw[si][0] && *model.sw[si][1]==request.target && *model.conductorFields[si][0]==request.target){
            found=true;
            if(*conductorHoldWrite-*conductorHoldRead>=16){if(model.schema==8)*cell(fx,unsigned(variable(fx,"NATIVE_SWITCH_RELEASE_FLAGS"))+si)=1;else *conductorReleaseMask=unsigned(*conductorReleaseMask)|(1u<<si);if(model.schema==8)*conductorReleaseMask=1;}
            else {unsigned q=unsigned(*conductorHoldWrite)%16*2;*conductorReleaseQueue[q]=si;*conductorReleaseQueue[q+1]=4;++*conductorHoldWrite;}
          }
          if(!found)reply.status=2;
        }
        else if (request.op == 4 || request.op == 5) {
          // Portable activation/capture must never stop a running performance.
          // The test and maintenance handoff occur in this same callback.
          if (request.arg == 1 && (movements.active > 0 || state.active > 0 || chain.run || chain.recording || chain.armed ||
              *importOverdub > .5 || *importState == importRecording ||
              *importState == importPlaying || performanceMorphSeconds > 0 ||
              std::any_of(importSustain.begin(),importSustain.end(),[](double* p){return *p>.5;}) ||
              std::any_of(importLiveSustain.begin(),importLiveSustain.end(),[](double* p){return *p>=64;}) ||
              std::any_of(importVoices.begin(), importVoices.end(),
                          [](double* p) { return *p > .5; }) ||
              (request.op == 5 && !patch.unchanged()))) {
            reply.status = 3;
          } else {
          if (chainMode) {
            chain.cancel();
            NSEEL_code_execute(panic_bridge);
          }
          if (request.op == 5)
            NSEEL_code_execute(panic_bridge);
          if (request.op == 5) {
            chain.cancel();
            *snapHostRead = *snapHostWrite;
            cancelAB();
            performanceTargetCount = 0;
            performanceSkipped = 0;
            performanceMorphSeconds = 0;
            performanceTargetSnapshot = 0;
            movementOutputCount=0;reveals.panic();movements.panic();
          controllers.panic();
            ++state.revision;
            loading.store(true, std::memory_order_release);
          }
          maintenance = true;
          }
        } else if (request.op == 46 || request.op == 47) {
          if(request.target<0 || unsigned(request.target)>=movements.plan.definitions.size())reply.status=3;
          else if(request.op==46){if(!movements.start(unsigned(request.target),state.samples,resolveMovement))reply.status=3;}
          else if(request.arg==1)movements.releasePreview(unsigned(request.target),state.samples);
          else movements.stop(unsigned(request.target));
        } else if (request.op == 44) {
          if(!chain.stopInstance(request.instanceId,request.instanceGeneration))reply.status=3;
        } else if (request.op == 40) {
          if (!chainMode)
            reply.status = 3;
          else {
            if (request.arg == 0) {
              // Finalize the capture before PANIC clears its authoritative flags.
              chain.cancel();
              *snapHostRead = *snapHostWrite;
              performanceMorphSeconds = 0;
              cancelAB();
              movementOutputCount=0;reveals.panic();movements.panic();
          controllers.panic();
              NSEEL_code_execute(panic_bridge);
            }
            if (!chain.command(request.arg, request.target)) reply.status = 3;
            else if (jack && chain.gridCapture && (request.arg == 1 || request.arg == 2))
              jack_transport_start(jack);
          }
        } else if(request.op==42){
          chain.cancel();chain.clearError();
          cancelAB();performanceTargetCount=0;performanceSkipped=0;performanceMorphSeconds=0;performanceTargetSnapshot=0;
          reveals.panic();movements.panic();
          *snapHostRead=*snapHostWrite;controllers.replace(request.controllerConfig,resolveBinding);
          performanceSnapshots->restore(request.snapshotConfig);
          NSEEL_code_execute(panic_bridge);++state.revision;
          loading.store(true,std::memory_order_release);maintenance=true;
        } else if(request.op==41){
          int si=-1;for(unsigned j=0;j<model.switchCapacity;++j)if(*model.sw[j][0] && *model.sw[j][1]==request.target)si=j;
          const auto &v=request.switchSettings;bool collision=false;
          for(const auto &source:controllers.configuration().sources)collision|=v[1] && source.id && source.kind==v[1] && source.channel==v[2] && source.number==v[3];
          if(si>=0 && v[1])collision|=matchesLegacy(v[1],v[2],v[3],si);
          bool sourceChanged=si>=0&&(v[0]!=*model.switchFields[si][0]||v[1]!=*model.switchFields[si][2]||v[2]!=*model.switchFields[si][3]||v[3]!=*model.switchFields[si][4]||v[4]!=*model.switchFields[si][12]||v[5]!=*model.switchFields[si][13]);
          bool sourceBusy=state.active||chain.run||chain.recording||chain.armed;bool pressed=false;
          for(unsigned j=0;j<model.switchCapacity;++j)pressed|=*model.switchPressed[j]>.5;sourceBusy|=pressed;
          for(unsigned j=0;j<12;++j)sourceBusy|=*model.voiceActive[j]>.5;
          if(si<0)reply.status=2;
          else if(collision||pressed||(sourceChanged&&sourceBusy))reply.status=3;
          else{
            const unsigned fields[]={0,2,3,4,12,13,6,7,8,9,10,11,14,15,16,17,18,19};
            for(unsigned j=0;j<18;++j)*model.switchFields[si][fields[j]]=v[j];
            if(request.hasLongHold)for(unsigned j=0;j<3;++j)*model.switchFields[si][120+j]=v[98+j];
            for(unsigned j=0;j<64;++j)*model.switchFields[si][48+j]=v[18+j];
            for(unsigned j=0;j<16;++j)*model.switchFields[si][32+j]=v[82+j];
            *target=si;NSEEL_code_execute(switchReset);++state.revision;
          }
        } else if(request.op==38){
          controller::Binding b;b.instrument=request.target;b.module=request.module;b.kind=request.arg;unsigned i;int code,row;
          auto assignment=model.legacyAssignment(b);
          if(!assignment || !model.resolve(b,i,code,row,true))reply.status=2;
          else{if(request.macroPosition==1){*assignment=0;for(unsigned j=0;j<performanceTargetCount;++j){auto &p=(*performanceTargets)[j];if(p.key.instrument==b.instrument && p.key.module==b.module && p.key.kind==b.kind){cancelPerformance(p,p.token);p.active=false;}}++state.revision;}const auto &curve=code?model.legacyCurves[i][code][row]:model.levelCurves[i];reply.legacySource=int(*assignment);reply.legacyCount=std::max(2,std::min(16,int(*curve.count)));for(int j=0;j<reply.legacyCount;++j)for(unsigned k=0;k<3;++k)reply.legacyPoints[j][k]=*curve.points[j][k];}
        } else if(request.op==39){
          if(!controllers.preset(request.target,request.binding.policy.curve))reply.status=3;else ++state.revision;
        } else if(request.op==37){
          bool success=false;
          if(request.arg==2){success=controllers.removeSource(request.target);}
          else if(request.arg){bool exists=false;for(const auto &s:controllers.configuration().sources)exists|=s.id==unsigned(request.target);if(!exists){controller::Source s;s.id=request.target;for(unsigned j=0;j<17;++j)s.name[j]=request.snapshotName[j];success=controllers.source(s);}}
          else success=controllers.rename(request.target,request.snapshotName);
          if(!success)reply.status=2;else ++state.revision;
        } else if (request.op == 36) {
          int selected=-1;
          if (!request.arg) selected=request.target-1;
          else for(unsigned i=0;i<8;++i)
            if(*model.inst[i][0] && int(*model.inst[i][1])==request.target) selected=i;
          if(selected<0) reply.status=2;
          else {
            for(unsigned j=0;j<16;++j)
              *(request.arg?model.inst[selected][6+j]:model.phraseNames[selected][j])=
                  static_cast<unsigned char>(request.snapshotName[j]);
            ++state.revision;
          }
        } else if (request.op == 43) {
          if(!controllers.testSource(request.target,request.value,(state.samples+frames)/double(sampleRate)))reply.status=2;
        } else if (request.op >= 20) {
          bool valid = false;
          if (request.op == 34) {
            if (request.target >= 1 && request.target <= int(model.phraseCapacity)) {
              if (request.arg == 0) {
                NSEEL_code_execute(cancelLearn);
                valid = controllers.learnCommand(request.target);
              } else if (request.arg == 1) { controllers.cancel(); valid = true; }
              else if (request.arg == 2) {
                controllers.cancel();
                *model.phrase[request.target - 1][8] = -1;
                *model.phrase[request.target - 1][9] = 0;
                valid = true;
              } else valid = controllers.learnsCommand() && controllers.learnTarget() == unsigned(request.target) && controllers.confirm();
            }
          } else if (request.op == 33) {
            if (request.arg == 0) {
              *editOp = 0;
              NSEEL_code_execute(instrumentLifecycle);
              valid = *editResult < 8;
            } else if (request.arg == 1) {
              unsigned i = 0;
              for (; i < 8; ++i)
                if (*model.inst[i][0] && *model.inst[i][1] == request.target) break;
              if (i < 8) {
                cancelAB();
                for (unsigned j = 0; j < performanceTargetCount; ++j) {
                  auto &p = (*performanceTargets)[j];
                  if (p.key.instrument == unsigned(request.target) &&
                      !performance::phraseKind(p.key.kind)) {
                    cancelPerformance(p, p.token);
                    p.active = false;
                  }
                }
                for (const auto &b : controllers.configuration().bindings)
                  if (b.policy.id && b.instrument == unsigned(request.target) &&
                      !performance::phraseKind(b.kind) && b.kind != 16)
                    controllers.remove(b.policy.id);
                performanceSnapshots->pruneInstrument(request.target);
                *editI = i;
                *target = request.target;
                *editOp = 1;
                NSEEL_code_execute(instrumentLifecycle);
                auto expressive=model.expressiveConfiguration();
                for(auto &setting:expressive)
                  if(setting.instrument==unsigned(request.target))setting=expressive::InstrumentSettings{};
                model.loadExpressive(expressive);
                expressiveCancelPending=true;
                valid = true;
              } else reply.status = 2;
            }
          } else if (request.op == 32) {
            controller::Binding b;
            b.instrument = request.target;
            b.module = request.module;
            b.kind = request.arg;
            double value = request.macroPosition;
            valid = b.kind != 16 && model.bindingValue(b) &&
                    value >= performance::physical(b.kind, 0) &&
                    value <= performance::physical(b.kind, 1);
            if (valid) {
              for (unsigned j = 0; j < performanceTargetCount; ++j) {
                auto &p = (*performanceTargets)[j];
                if (p.key.instrument == b.instrument &&
                    p.key.module == b.module && p.key.kind == b.kind) {
                  auto current = controllers.target(p.id);
                  cancelPerformance(p, b.kind >= 25 && current ? current->token : p.token);
                  p.active = false;
                }
              }
              controllers.recall(b.instrument, b.module, b.kind,
                                 performance::normalized(b.kind, value));
              // parameter_set already carries the physical value selected in
              // the editor. Re-scaling an enum through the legacy EEL bounds
              // can change it (for example ARP DOWN=2 becomes RANDOM when the
              // native registry has a wider enum range). Reuse the same safe
              // typed EEL edit path as module_commit so active-note deferral
              // and transformer ownership remain intact.
              unsigned instrumentIndex;
              int code, row;
              if (b.module && b.kind < 14 &&
                  model.resolve(b, instrumentIndex, code, row, true)) {
                *editI = instrumentIndex;
                *editCode = code;
                *editKind = b.kind;
                *editRow = row;
                *editValue = value;
                NSEEL_code_execute(edit);
              } else {
                applyBinding(b, performance::normalized(b.kind, value));
              }
            }
          } else if (request.op == 30) {
            performance::AB config;
            config.a = request.target;
            config.b = request.module;
            config.position = request.macroPosition;
            config.ease = request.arg;
            valid = config.valid() &&
                    (!config.a || (performanceSnapshots->find(config.a) &&
                                   performanceSnapshots->find(config.b)));
            if (valid) {
              cancelAB();
              performanceSnapshots->ab = config;
              model.abPosition = config.position;
              controllers.recall(1, 0, 16, config.position);
              abRequested = config.a != 0;
            }
          } else if (request.op == 31) {
            valid = performanceSnapshots->ab.a && performanceSnapshots->ab.b &&
                    (!request.target ||
                     (unsigned(request.target) == performanceSnapshots->ab.a &&
                      unsigned(request.module) == performanceSnapshots->ab.b));
            if (valid) {
              model.abPosition = request.macroPosition;
              performanceSnapshots->ab.position = request.macroPosition;
              controllers.recall(1, 0, 16, model.abPosition);
              abRequested = true;
            }
          } else if (request.op == 29) {
            const auto *record = performanceSnapshots->find(request.target);
            valid = record != nullptr;
            if (valid) {
              reply.detail = *record;
              reply.detailRevision = state.revision;
            }
          } else if (request.op == 20)
            valid = performanceSnapshots->capture(model.effectiveState()) != 0;
          else if (request.op == 21)
            valid = performanceSnapshots->update(request.target,
                                                 model.effectiveState());
          else if (request.op == 22)
            valid = performanceSnapshots->duplicate(request.target) != 0;
          else if (request.op == 23) {
            if (performanceSnapshots->ab.a == unsigned(request.target) ||
                performanceSnapshots->ab.b == unsigned(request.target))
              cancelAB();
            valid = performanceSnapshots->erase(request.target);
            if (valid) {
              for (unsigned j = 0; j < performanceTargetCount; ++j) {
                auto &p = (*performanceTargets)[j];
                if (p.snapshotId == unsigned(request.target)) {
                  cancelPerformance(p, p.token);
                  p.active = false;
                }
              }
              if (performanceTargetSnapshot == unsigned(request.target)) {
                *snapHostRead = *snapHostWrite;
                performanceMorphSeconds = 0;
              }
            }
          } else if (request.op == 24)
            valid = performanceSnapshots->move(request.target,
                                               request.arg ? 1 : -1);
          else if (request.op == 25 || request.op == 27) {
            const auto *r = performanceSnapshots->find(request.target);
            if (r) {
              auto draft = *r;
              std::memcpy(draft.name, request.snapshotName, 49);
              if (request.op == 27) {
                draft.seconds = request.snapshotSeconds;
                draft.ease = controller::Ease(request.snapshotEase);
                draft.switching = controller::Switch(request.snapshotSwitch);
              }
              bool known = true;
              const auto &mask = request.snapshotConfig.records[0].state;
              for (unsigned j = 0; j < mask.count; ++j) {
                bool found = false;
                for (unsigned k = 0; k < draft.state.count; ++k)
                  if (draft.state.values[k].key == mask.values[j].key) {
                    draft.state.values[k].included = mask.values[j].included;
                    found = true;
                  }
                if (!found)
                  known = false;
              }
              valid = known && performanceSnapshots->commit(
                                   draft, performanceSnapshots->revision);
            }
          } else if (request.op == 28) {
            bool exists = false;
            for (unsigned si = 0; si < model.switchCapacity; ++si)
              if (*model.sw[si][0] && *model.sw[si][1] == request.target)
                exists = true;
            performance::SwitchAction a;
            a.switchId = request.target;
            a.gesture = request.arg;
            a.action = request.ch;
            a.snapshotId = request.module;
            valid = exists && performanceSnapshots->setAction(a);
          } else if (request.op == 26) {
            valid = recallSnapshot(request.target, request.arg, nullptr) == 0;
            if (!valid)
              reply.status = lastRecallStatus;
          }
          if (valid) {
            if (request.op == 20 || request.op == 21)
              performanceSkipped = 0;
            if (request.op != 29)
              ++state.revision;
          } else if (reply.status == 0)
            reply.status = 3;
        } else if (request.op >= 14) {
          if (request.op == 14) {
            cancelAB();
            controller::Source source;
            source.id = request.target;
            source.kind = request.arg;
            source.channel = request.ch;
            source.number = request.note;
            if (source.kind &&
                (source.kind == 2 &&
                     (source.number == 64 || source.number >= 120) ||
                 matchesLegacy(source.kind, source.channel, source.number, -1)))
              reply.status = 3;
            else if (!controllers.source(source))
              reply.status = 3;
            else
              ++state.revision;
          } else if (request.op == 15) {
            bool valid = true;
            if (request.arg == 0) {
              NSEEL_code_execute(cancelLearn);
              valid = controllers.learn(request.target);
            } else if (request.arg == 1)
              controllers.cancel();
            else if (request.arg == 2) {
              cancelAB();
              valid = controllers.learnTarget() == unsigned(request.target) &&
                      controllers.confirm();
            } else {
              cancelAB();
              valid = controllers.forget(request.target);
            }
            if (!valid)
              reply.status = 3;
            else
              ++state.revision;
          } else if (request.op == 16) {
            if (request.binding.kind != 16)
              cancelAB();
            auto b = request.binding;
            auto legacy=request.arg?model.legacyAssignment(b):nullptr;
            const double oldLegacy=legacy?*legacy:0;
            if(legacy)*legacy=0;
            auto address = model.bindingValue(b);
            if (!address)
              reply.status = 2;
            else {
              // A new target captures its committed value; clients cannot
              // invent a base.
              bool found = false;
              for (auto &existing : controllers.configuration().bindings)
                if (existing.policy.id &&
                    existing.policy.target == b.policy.target) {
                  b.base = existing.base;
                  found = true;
                }
              if (!found)
                b.base = normalizedBase(b.kind, model.bindingBase(b));
              if (!controllers.bind(b))
                reply.status = 3;
              else {
                for (unsigned j = 0; j < performanceTargetCount; ++j) {
                  auto &p = (*performanceTargets)[j];
                  if (p.key.instrument == b.instrument &&
                      p.key.module == b.module && p.key.kind == b.kind) {
                    cancelPerformance(p, p.token);
                    p.active = false;
                  }
                }
                ++state.revision;
              }
            }
            if(reply.status && legacy)*legacy=oldLegacy;
          } else if (request.op == 17) {
            if (!controllers.remove(request.target))
              reply.status = 2;
            else
              ++state.revision;
          } else if (request.op == 18) {
            if (!(request.arg ? controllers.capture(request.target)
                              : controllers.returnCommand(request.target)))
              reply.status = 3;
          } else {
            uint8_t data[] = {uint8_t(176 | request.ch), uint8_t(request.note),
                              uint8_t(request.value)};
            auto before = controllers.learnTarget();
            if (!captureSwitch(data,3) && !controllers.midi(data, 3,
                                  (state.samples + frames) / double(sampleRate),
                                  conflicts)) {
              auto &physical=movementPhysical[movementPhysicalCount++];physical.offset=0;physical.ch=request.ch;physical.cc=request.note;physical.value=request.value;
              *snapHostRead = *snapHostWrite = 0;
              ysfx_midi_event_t event{};
              event.size = 3;
              event.data = data;
              if (!ysfx_send_midi(fx, &event))
                reply.status = 3;
            }
            if (before && !controllers.learnTarget()) {
              cancelAB();
              ++state.revision;
            }
          }
        } else if (request.op == 13) {
          publishPerformance();
          model.snapshot(state);
          unsigned i = 0;
          for (; i < 8; ++i)
            if (state.instruments[i].id == request.target)
              break;
          if (i == 8)
            reply.status = 2;
          else {
            auto &inst = state.instruments[i];
            int slot = -1;
            for (int j = 0; j < inst.transformerCount; ++j)
              if (inst.transformerIds[j] == request.module)
                slot = j;
            if (request.arg == 1) {
              bool duplicate = false;
              for (int j = 0; j < inst.transformerCount; ++j)
                if (inst.transformerTypes[j] == request.note)
                  duplicate = true;
              if (request.note < 1 || request.note > 6 ||
                  inst.transformerCount >= 6 ||
                  ((request.note == 3 || request.note == 5) && duplicate))
                reply.status = 3;
            } else if (slot < 0)
              reply.status = 2;
            if (!reply.status) {
              if (request.arg >= 4) {
                int destination = slot + (request.arg == 4 ? -1 : 1);
                if (destination < 0 || destination >= inst.transformerCount ||
                    !inst.serialPitch ||
                    (inst.transformerTypes[slot] != 1 && inst.transformerTypes[slot] != 2) ||
                    (inst.transformerTypes[destination] != 1 && inst.transformerTypes[destination] != 2))
                  reply.status = 3;
                else {
                  NSEEL_code_execute(panic_bridge);
                  std::swap(*model.tfCodes[i][slot],
                            *model.tfCodes[i][destination]);
                  ++state.revision;
                }
              } else {
                *editI = i;
                *editOp = request.arg;
                *editArg = request.arg == 1 ? request.note : slot;
                NSEEL_code_execute(structure);
                if (*editResult != 1)
                  reply.status = 3;
                else
                  ++state.revision;
              }
            }
          }
        } else if (request.op == 11 || request.op == 12) {
          unsigned i = 0;
          for (; i < 8; ++i)
            if (*model.inst[i][0] && int(*model.inst[i][1]) == request.target)
              break;
          if (i == 8)
            reply.status = 2;
          else if (request.op == 11) {
            NSEEL_code_execute(panic_bridge);
            *model.inst[i][2] = request.arg;
            *model.inst[i][3] = request.ch;
            *model.inst[i][4] = request.note;
            *model.inst[i][5] = request.value;
            controllers.recall(request.target, 0, 1, request.value / 127.);
            ++state.revision;
          } else {
            publishPerformance();
            model.snapshot(state);
            int slot = -1;
            for (int j = 0; j < state.instruments[i].transformerCount; ++j)
              if (state.instruments[i].transformerIds[j] == request.module)
                slot = j;
            if (slot < 0)
              reply.status = 2;
            else {
              auto &inst = state.instruments[i];
              std::array<int, 5> rows{};
              bool valid = true;
              for (int j = 0; j < request.count; ++j) {
                auto &change = request.parameters[j];
                int row = -1;
                for (int r = 0; r < inst.parameterCounts[slot]; ++r)
                  if (inst.transformerKinds[slot][r] == change.kind)
                    row = r;
                if (row < 0 || inst.transformerAssignments[slot][row])
                  valid = false;
                else
                  rows[j] = row;
                const auto &definition=performance::parameters[change.kind];
                double low=definition.low,high=definition.high;
                if (change.value < low || change.value > high)
                  valid = false;
                for (int prior = 0; prior < j; ++prior)
                  if (request.parameters[prior].kind == change.kind)
                    valid = false;
              }
              if (!valid)
                reply.status = 3;
              else {
                *editI = i;
                *editCode = std::abs(int(*model.tfCodes[i][slot]));
                for (int j = 0; j < request.count; ++j) {
                  *editKind = request.parameters[j].kind;
                  *editValue = request.parameters[j].value;
                  *editRow = rows[j];
                  NSEEL_code_execute(edit);
                }
                for (int j = 0; j < request.count; ++j)
                  controllers.recall(
                      request.target, request.module,
                      request.parameters[j].kind,
                      normalizedBase(request.parameters[j].kind,
                                     request.parameters[j].value));
                ++state.revision;
              }
            }
          }
        } else if (request.op >= 9) {
          unsigned i = 0;
          for (; i < 8; ++i)
            if (*model.inst[i][0] && int(*model.inst[i][1]) == request.target)
              break;
          if (i == 8)
            reply.status = 2;
          else {
            NSEEL_code_execute(panic_bridge);
            *model.inst[i][request.op == 10 ? 2 : 3 + request.arg] =
                request.value;
            if (request.op == 9 && request.arg == 2)
              controllers.recall(request.target, 0, 1, request.value / 127.);
            ++state.revision;
          }
        } else if (request.op >= 6) {
          if (chainMode) {
            if (!chain.command(request.op == 6   ? 1
                               : request.op == 7 ? 2
                                                 : 3,
                               request.target))
              reply.status = 3;
            else if (jack && request.op != 8) jack_transport_start(jack);
          } else {
            *phraseTarget = request.target;
            NSEEL_code_execute(request.op == 6   ? phrasePlay
                               : request.op == 7 ? phraseRecord
                                                 : phraseStop);
          }
        } else if (request.op == 1) {
          *target = request.target;
          *gesture = request.arg;
          NSEEL_code_execute(bridge);
          if (*ok != 1)
            reply.status = 2;
        } else if (request.op == 2) {
          expressiveCancelPending=true;
          if(chainMode)panicSweep.begin();
          if(echoProtocol){echoRuntime.configure(echoRuntime.configuration(),true);echoRecovering=true;}
          state.switchLearnTarget=0;state.switchLearnConflict=false;chain.cancel();
          *snapHostRead = *snapHostWrite;
          performanceMorphSeconds = 0;
          cancelAB();
          movementOutputCount=0;reveals.panic();movements.panic();
          controllers.panic();
          ysfx_midi_clear(fx->midi.in.get());
          state.midiDropped+=inputWrite-inputRead;
          inputRead = inputWrite;
          NSEEL_code_execute(panic_bridge);
          if (request.id == 9007199254740991ULL)
            muted = true;
        } else if (request.op == 3) {
          uint8_t data[] = {uint8_t(144 | request.ch), uint8_t(request.note),
                            uint8_t(request.value)};
          *snapHostRead = *snapHostWrite = 0;
          ysfx_midi_event_t event{};
          event.size = 3;
          event.data = data;
          auto before = controllers.learnTarget();
          if (captureSwitch(data,3) || controllers.midi(data, 3,
                               (state.samples + frames) / double(sampleRate),
                               conflicts)) {
            if (before && !controllers.learnTarget()) {
              cancelAB();
              ++state.revision;
            }
          } else if (!ysfx_send_midi(fx, &event))
            reply.status = 3;
        }
      }
      trace.value.commands=count;
      trace.mark(2);
      for (unsigned j = 0; j < performanceTargetCount;) {
        auto &p = (*performanceTargets)[j];
        if (!model.bindingValue(p.binding, true)) {
          cancelAB();
          cancelPerformance(p, p.token);
          controllers.retirePerformanceTarget(p.id);
          (*performanceTargets)[j] =
              (*performanceTargets)[--performanceTargetCount];
        } else
          ++j;
      }
      if (model.abRestorePending.exchange(false, std::memory_order_acq_rel))
        abRequested = true;
      controller::Source triggerCapture;
      if (controllers.takeCommandCapture(triggerCapture)) {
        *phraseTarget = triggerCapture.id - 1;
        *learnNum = triggerCapture.number;
        *learnCh = triggerCapture.channel;
        NSEEL_code_execute(phraseAssign);
        ++state.revision;
      }
      if (controllers.tick((state.samples + frames) / double(sampleRate),
                           resolveBinding, applyBinding))
        ++state.revision;
      if (chainMode) {
        if(chain.gridCapture)tickChain();
        state.chain = true;state.chainPhrase=chain.phrase;state.chainErrorPhrase=chain.errorPhrase;
        state.chainGridCapture=chainGridCapture;
        state.chainTimingVersion=chainTimingVersion;
        state.chainRun = chain.run;
        state.chainArmed = chain.armed;
        state.chainRecord = chain.recording;
        state.chainError = chain.error;
        state.chainErrorCode=int(chain.errorReason);state.captureRejected=chain.captureRejected;state.captureOverflows=chain.captureOverflows;
        state.chainFrame = frame;
        state.chainLength = chain.length;
        state.chainBpm = chain.bpm;
        state.chainFrameGap = chain.lastFrameGap;
        state.chainClockGap = chain.lastClockGap;
        ysfx_time_info_t time{};
        time.tempo = chain.bpm;
        time.playback_state =
            rolling ? ysfx_playback_playing : ysfx_playback_paused;
        time.time_signature[0] = 4;
        time.time_signature[1] = 4;
        ysfx_set_time_info(fx, &time);
      }
      if(state.echoAvailable && !echoProtocol && echoRuntime.hasConfiguration()){
        echoProtocol=true;*echoHost=1;*echoRead=*echoWrite=*echoOverflow=0;
      }
      trace.mark(3);
      movements.render(state.samples+frames,emitMovement,applyMovement,false,true);
      trace.mark(4);
      for (unsigned j = 0; j < performanceTargetCount; ++j) {
        auto &p = (*performanceTargets)[j];
        if (!p.active)
          continue;
        auto target = controllers.target(p.id);
        if (!target) {
          p.active = false;
          continue;
        }
        if (target->owner == UINT32_MAX && target->token == p.token)
          applyBinding(p.binding, target->effective);
        else if (target->owner == 0 &&
                 std::abs(target->effective - p.goal) < 1e-8) {
          applyBinding(p.binding, target->effective);
          // Legacy expression remains suspended after recall until its pedal
          // moves.
          if (p.legacyCurve >= 0)
            p.token =
                controllers.acquirePerformanceTarget(p.id, target->effective);
          p.active = false;
        } else
          p.active = false;
      }
      updateAB();
      syncSwitchActions();
      for (unsigned j = 288; j < snapHostCells.size(); ++j)
        *snapHostCells[j] = 0;
      for (unsigned j = 0; j < performanceTargetCount; ++j) {
        const auto &p = (*performanceTargets)[j];
        auto t = controllers.target(p.id);
        if (p.legacyCurve >= 0 && p.legacyCurve < 232 && t &&
            t->owner == UINT32_MAX && t->token == p.token)
          *snapHostCells[288 + p.legacyCurve] = 1;
      }
      if (chainMode && outBuffer && *panicPending > .5)
        cleanupChain();
      chain.finishSwitchStop();
      trace.mark(5);
      controllers.rawCCMasks(revealMasks);for(unsigned cc=0;cc<128;++cc){*revealMaskCells[cc]=revealMasks[cc];*revealMaskCells[128+cc]=0;}*revealExisting=revealMasks[7];*revealReserved=0;*revealFree=controllers.freeTargets();*nativeControlCount=0;
      if(nativeClearCursor==nativeClearPages.size())
        ysfx_process_float(fx, nullptr, nullptr, 0, 0, frames);
      trace.mark(6);
      // The shared output buffer rejected an owned event: cancel queued attacks
      // through the existing native emergency recovery on the next callback.
      if(*model.instanceFault>.5){++state.outputOverflow;overflowRecovery=true;}
      chain.finishSwitchStop();
      if(chainMode && !chain.gridCapture) {
        chain.observe();
        state.chainRun=chain.run;state.chainArmed=chain.armed;
        state.chainRecord=chain.recording;state.chainError=chain.error;
        state.chainErrorPhrase=chain.errorPhrase;state.chainErrorCode=int(chain.errorReason);
        state.captureRejected=chain.captureRejected;state.captureOverflows=chain.captureOverflows;
        state.chainLength=chain.length;
      }
      for (unsigned j = 0; j < performanceTargetCount; ++j) {
        auto &p = (*performanceTargets)[j];
        if (p.legacyCurve >= 0 && p.legacyCurve < 232 &&
            !*snapHostCells[288 + p.legacyCurve]) {
          cancelPerformance(p, p.token);
          p.active = false;
        }
      }
      if (*snapHostCancel) {
        cancelAB();
        if(*snapHostCancel==2){movementOutputCount=0;reveals.panic();movements.panic();controllers.panic();}
        else for(unsigned j=0;j<performanceTargetCount;++j){auto &p=(*performanceTargets)[j];if(p.active)cancelPerformance(p,p.token);}
        for (unsigned j = 0; j < performanceTargetCount; ++j)
          (*performanceTargets)[j].active = false;
        performanceMorphSeconds = 0;
        *snapHostRead = *snapHostWrite;
        *snapHostCancel = 0;
      }
      // Preflight was computed before DSP. Stage its bounded CC7 reservations
      // before Snapshot/MOVEMENT commands can allocate any additional targets.
      for(unsigned cc=0;cc<128;++cc)if(*revealMaskCells[128+cc]>0&&!reveals.reserve(unsigned(*revealMaskCells[128+cc]),cc)){++state.outputOverflow;overflowRecovery=true;}
      unsigned controlCount=0;
      auto addControl=[&](unsigned offset,unsigned order,unsigned kind,unsigned slot,uint64_t id,unsigned mask){
        if(controlCount>=nativeControls->size()){++state.outputOverflow;overflowRecovery=true;return;}
        auto &c=(*nativeControls)[controlCount];c.sequence=controlCount++;c.offset=offset;c.order=order;c.kind=kind;c.slot=slot;c.id=id;c.mask=mask;
      };
      while (*snapHostRead < *snapHostWrite) {
        unsigned at = 96 + (unsigned(*snapHostRead) % 64) * 3;
        unsigned action = unsigned(*snapHostCells[at]);
        uint32_t id = uint32_t(*snapHostCells[at + 1]);
        ++*snapHostRead;
        if(action==213){addControl(0,1,13,unsigned(*snapHostCells[at+2]),uint64_t(*snapHostCells[at+1]),0);continue;}
        if(action==9){addControl(std::min(unsigned(*snapHostCells[at+2]),unsigned(frames-1)),1,9,0,id,0);continue;}
        if (action != 3 && action != 4)id = performanceSnapshots->navigate(action);
        if (id && recallSnapshot(id, action == 4 || action == 6 || action == 7,nullptr) == 0)++state.revision;
      }
      *snapHostRead = *snapHostWrite = 0;
      for(unsigned j=0;j<movementPhysicalCount;++j){auto &p=movementPhysical[j];addControl(p.offset,0,1,p.ch,p.value,p.cc);}
      unsigned outputCount=0,nativeOrdinal=0;
      if(echoProtocol)echoOrders.fill(0);
      ysfx_midi_event_t event{};
      while(ysfx_receive_midi(fx,&event)){
        ++nativeOrdinal;
        if(echoProtocol && event.bus!=15 && event.size==3 && ((event.data[0]&240)==128 || (event.data[0]&240)==144))continue;
        if(outputCount>=8192||event.size>256){if(event.bus!=15){++state.midiGenerated;++state.midiDropped;}++state.outputOverflow;overflowRecovery=true;continue;}
        auto &m=(*outputBatch)[outputCount];m.size=event.size;m.offset=std::min(event.offset,frames-1);m.order=nativeOrdinal*4;m.bus=event.bus;
        std::memcpy(m.data.data(),event.data,event.size);(*outputOrder)[outputCount]=outputCount;
        if(event.bus==15){
          if(m.size!=17||m.data[0]!=240||m.data[1]!=125||m.data[2]!=77||m.data[16]!=247){++state.outputOverflow;overflowRecovery=true;m.size=0;}
          else{
            uint64_t id=0;unsigned mask=0;for(int k=7;k>=0;--k)id=id*128+m.data[5+k];for(int k=2;k>=0;--k)mask=mask*128+m.data[13+k];
            if(m.data[3]==18){
              if(!echoProtocol || id>=echoOrders.size() || m.data[4] || mask){++state.outputOverflow;overflowRecovery=true;}
              else echoOrders[id]=m.order;
              continue;
            }
            addControl(m.offset,m.order,m.data[3],m.data[4],id,mask);m.size=0;
          }
        }else if(m.size==3&&(m.data[0]&240)==176)addControl(m.offset,m.order,2,m.data[0]&15,m.data[2],m.data[1]);
        ++outputCount;
      }
      // Raw EEL packets keep stable order; generated CCs append to the same
      // preallocated batch. Only the existing producer sorts MIDI timestamps.
      movementOutputCount=outputCount;
      reveals.flush(state.samples,emitControlled);
      std::sort(nativeControls->begin(),nativeControls->begin()+controlCount,[](const NativeControl&a,const NativeControl&b){if(a.offset!=b.offset)return a.offset<b.offset;if(a.order!=b.order)return a.order<b.order;return a.sequence<b.sequence;});
      std::array<double,64> movementCharge;movementCharge.fill(-1);
      for(unsigned j=0;j<controlCount;++j){const auto &c=(*nativeControls)[j];uint64_t sample=state.samples+c.offset;
        generatedAt=UINT64_MAX;generatedOrder=0;
        movements.render(sample,emitMovement,applyMovement,true);reveals.render(sample,emitControlled);
        if(c.kind==1){movements.physical(c.slot,c.mask,unsigned(c.id),sample);reveals.physical(c.slot,c.mask,unsigned(c.id),sample);continue;}
        // Cadence due exactly here precedes this control; a newly started
        // MOVEMENT emits its initial CC immediately at its own marker order.
        // Adjacent PRESS starts at one timestamp retain the established
        // latest-owner-before-first-emission rule. Do not flush a losing
        // initial CC between those starts. Other controls remain barriers.
        bool coalescedStart=c.kind==9&&j>0&&(*nativeControls)[j-1].kind==9&&(*nativeControls)[j-1].offset==c.offset;
        if(!coalescedStart)movements.render(sample+1,emitMovement,applyMovement,true);
        generatedAt=sample;generatedOrder=c.order;
        if(c.kind==2)reveals.observe(c.slot,c.mask,unsigned(c.id));
        else if(c.kind==9){movements.start(unsigned(c.id),sample,resolveMovement,c.slot,c.mask,c.slot<model.switchCapacity?movementCharge[c.slot]:-1);
          bool nextStart=j+1<controlCount&&(*nativeControls)[j+1].kind==9&&(*nativeControls)[j+1].offset==c.offset;
          if(!nextStart)movements.render(sample+1,emitMovement,applyMovement,true);}
        else if(c.kind==17){if(c.slot<model.switchCapacity)movementCharge[c.slot]=c.mask?controller::clamp(c.id/1000000.):-1;}
        else if(c.kind==16){reveals.configure(c.slot,unsigned(c.id),c.mask/1000.);}
        else if(c.kind==10){if(!reveals.start(c.slot,c.id,c.mask,sample,emitControlled)){++state.outputOverflow;overflowRecovery=true;}}
        else if(c.kind==11||c.kind==12)reveals.mask(c.slot,c.id,c.kind==12,sample,emitControlled);
        else if(c.kind==13)reveals.close(c.slot,c.id,sample,emitControlled);
        else if(c.kind==15){movements.release(c.slot,c.id,sample,c.mask!=0);}
        else if(c.kind==14){reveals.panic();movements.panic();reveals.flush(sample,emitControlled);}
        else{++state.outputOverflow;overflowRecovery=true;}
      }
      generatedAt=UINT64_MAX;generatedOrder=0;
      movements.render(state.samples+frames,emitMovement,applyMovement);
      reveals.render(state.samples+frames,emitControlled);reveals.collectIdle();
      if(echoProtocol){
        unsigned echoOrder=0;
        auto emitEcho=[&](uint64_t sample,bool on,uint8_t ch,uint8_t pitch,uint8_t velocity,bool retrigger){
          const unsigned needed=on && retrigger?2:1;
          if(movementOutputCount+needed>outputBatch->size())return false;
          const unsigned offset=unsigned(std::min<uint64_t>(frames-1,sample>state.samples?sample-state.samples:0));
          for(unsigned k=0;k<needed;++k){auto &m=(*outputBatch)[movementOutputCount++];m.size=3;m.offset=offset;m.bus=0;m.order=echoOrder;
            const bool attack=on && (!retrigger || k==1);m.data[0]=uint8_t((attack?144:128)|ch);m.data[1]=pitch;m.data[2]=attack?velocity:0;
          }
          return true;
        };
        echoRuntime.begin(state.samples,emitEcho);
        unsigned echoCount=0;
        for(unsigned j=0;j<movementOutputCount;++j){auto &m=(*outputBatch)[j];m.order=m.order*4+2;
          if(m.size==3 && (m.data[0]&240)==176 && (m.data[1]==120 || m.data[1]==123)){
            auto &e=(*echoTimeline)[echoCount];e=echocity::SourceEvent{};e.action=echocity::SourceAction::ChannelClear;
            e.key.channel=m.data[0]&15;e.offset=m.offset;e.order=m.order;e.sequence=echoCount;++echoCount;
          }
        }
        const bool validJournal=echoRecovering || (!*model.instanceFault && !overflowRecovery && echoJournal->consume(*echoRead,*echoWrite,*echoOverflow,frames,
          [&](size_t j){return *(*echoCells)[j];},[&](const echocity::SourceEvent&e){
            auto &target=(*echoTimeline)[echoCount];target=e;target.order=echoOrders[e.journalIndex]?echoOrders[e.journalIndex]*4+2:1;target.sequence=echoCount;++echoCount;
          }));
        if(validJournal && !echoRecovering){
          std::sort(echoTimeline->begin(),echoTimeline->begin()+echoCount,[](const echocity::SourceEvent&a,const echocity::SourceEvent&b){
            if(a.offset!=b.offset)return a.offset<b.offset;if(a.order!=b.order)return a.order<b.order;return a.sequence<b.sequence;
          });
          uint64_t cursor=state.samples;
          for(unsigned j=0;j<echoCount;++j){const auto &e=(*echoTimeline)[j];const uint64_t sample=state.samples+e.offset;
            echoOrder=0;if(sample>=cursor){echoRuntime.render(cursor,unsigned(sample-cursor+1),emitEcho);cursor=sample+1;}
            echoOrder=e.order;echoRuntime.source(e,sample,chainMode?chain.bpm:bpm,emitEcho);
            echoOrder=e.order+1;echoRuntime.render(sample,1,emitEcho);
          }
          echoOrder=0;if(cursor<state.samples+frames)echoRuntime.render(cursor,unsigned(state.samples+frames-cursor),emitEcho);
        }
        if(validJournal)*echoRead=*echoWrite=0;
        if(!echoRecovering && (!validJournal || echoRuntime.failed)){
          echoRuntime.cancel(state.samples+frames-1,[](const native_notes::SourceKey&){return true;},emitEcho);
          overflowRecovery=true;panicSweep.begin();echoRecovering=true;*echoRead=*echoWrite=*echoOverflow=0;
        }
        auto alive=echoRuntime.configuration();bool removed=false;
        for(auto &c:alive)if(c.id){bool found=false;for(unsigned j=0;j<8;++j)found|=*model.inst[j][0]>.5 && *model.inst[j][1]==c.instrument;
          if(!found){c=echocity::Configuration{};removed=true;}}
        if(removed)echoRuntime.configure(alive);
      }
      state.echoConfig=echoRuntime.configuration();state.echoPending=echoRuntime.pending();state.echoSources=echoRuntime.sources();state.echoRejected=echoRuntime.rejected;
      state.expressivePending=unsigned(expressiveStream->pending());state.expressiveRejected=expressiveStream->rejected;state.expressiveClamped=expressiveStream->clamped;
      outputCount=movementOutputCount;
      // Apply per-instrument HUMANIZER and VELOCITY CURVES after the native
      // transformer chain and before JACK. Disabled modules take the exact
      // original packet path. The fixed stream table pairs overlapping voices
      // and schedules attacks/releases without callback allocation or locks.
      auto expressiveSettings=model.expressiveConfiguration();
      bool expressiveActive=false;
      for(const auto &setting:expressiveSettings)
        expressiveActive|=setting.instrument &&
          ((setting.humanizerModule && setting.humanizer.enabled) ||
           (setting.curveModule && setting.curve.enabled));
      if(expressiveActive || expressiveStream->pending() || expressiveCancelPending){
        bool ordered=true;
        for(unsigned j=1;j<outputCount;++j){const auto&a=(*outputBatch)[j-1],&b=(*outputBatch)[j];if(a.offset>b.offset||(a.offset==b.offset&&a.order>b.order)){ordered=false;break;}}
        for(unsigned j=0;j<outputCount;++j)(*outputOrder)[j]=j;
        if(!ordered)std::sort(outputOrder->begin(),outputOrder->begin()+outputCount,[&](unsigned a,unsigned b){const auto&x=(*outputBatch)[a];const auto&y=(*outputBatch)[b];return x.offset!=y.offset?x.offset<y.offset:(x.order!=y.order?x.order<y.order:a<b);});
        unsigned expressiveCount=0;uint64_t expressiveIdentity=state.samples+state.blocks*uint64_t(frames);
        auto copyExpressive=[&](const MidiPacket&src){if(expressiveCount>=expressiveBatch->size()){++state.outputOverflow;overflowRecovery=true;return false;}(*expressiveBatch)[expressiveCount++]=src;return true;};
        if(expressiveCancelPending){
          if(!expressiveStream->cancel(state.samples,0,0,[&](uint64_t sample,bool on,uint8_t ch,uint8_t pitch,uint8_t velocity){
            if(expressiveCount>=expressiveBatch->size()){++state.outputOverflow;overflowRecovery=true;return false;}
            auto&m=(*expressiveBatch)[expressiveCount++];m.size=3;m.offset=unsigned(std::min<uint64_t>(frames-1,sample>state.samples?sample-state.samples:0));m.bus=0;m.order=expressiveCount*4;m.data[0]=uint8_t((on?144:128)|ch);m.data[1]=pitch;m.data[2]=velocity;return true;
          })) {++state.outputOverflow;overflowRecovery=true;}
          expressiveCancelPending=false;
        }
        for(unsigned j=0;j<outputCount;++j){const auto &src=(*outputBatch)[(*outputOrder)[j]];
          if(src.size==3 && (src.data[0]&240)==176 && (src.data[1]==120 || src.data[1]==123))expressiveStream->channelCleared(src.data[0]&15);
          if(src.size!=3 || ((src.data[0]&240)!=128 && (src.data[0]&240)!=144)){if(!copyExpressive(src))break;continue;}
          const unsigned channel=src.data[0]&15,pitch=src.data[1]&127,kind=src.data[0]&240,velocity=src.data[2]&127;
          // An explicit MIDI OUT channel identifies the instrument at this
          // post-routing point. ORIGINAL and ambiguous shared channels pass
          // through until the source bridge can provide an instrument ID.
          int instrument=-1;
          for(unsigned k=0;k<8;++k)if(*model.inst[k][0]>.5&&*model.inst[k][2]>.5&&unsigned(*model.inst[k][4])==channel+1){if(instrument!=-1){instrument=-2;break;}instrument=int(k);}
          const expressive::InstrumentSettings *setting=nullptr;
          if(instrument>=0){const unsigned id=unsigned(*model.inst[instrument][1]);for(const auto &candidate:expressiveSettings)if(candidate.instrument==id){setting=&candidate;break;}}
          if(!setting || !((setting->humanizerModule&&setting->humanizer.enabled)||(setting->curveModule&&setting->curve.enabled))){if(!copyExpressive(src))break;continue;}
          native_notes::SourceKey key{};key.instrument=setting->instrument;key.origin=native_notes::Origin::Live;key.instance=0;key.channel=uint8_t(channel);key.pitch=uint8_t(pitch);
          expressive::Identity identity{};identity.instrument=setting->instrument;identity.note=uint32_t(pitch);
          auto humanizer=setting->humanizer;if(!setting->humanizerModule)humanizer.enabled=false;
          auto curve=setting->curve;if(!setting->curveModule)curve.enabled=false;
          const uint64_t sourceSample=state.samples+src.offset;
          if(humanizer.variation==expressive::Variation::Evolving){identity.iteration=uint32_t(state.blocks);identity.group=uint32_t(sourceSample);identity.instance=sourceSample;}
          else{identity.iteration=0;identity.group=channel;identity.instance=0;}
          if(kind==144&&velocity>0){
            const bool accepted=expressiveStream->attack(key,setting->humanizerModule?setting->humanizerModule:setting->curveModule,state.samples+src.offset,uint8_t(velocity),identity,humanizer,curve,[](uint64_t,bool,uint8_t,uint8_t,uint8_t){return true;});
            if(!accepted&&!copyExpressive(src))break;
          }else{
            const bool accepted=expressiveStream->release(key,state.samples+src.offset,uint8_t(velocity),[](uint64_t,bool,uint8_t,uint8_t,uint8_t){return true;});
            if(!accepted&&!copyExpressive(src))break;
          }
        }
        expressiveStream->render(state.samples,frames,[&](uint64_t sample,bool on,uint8_t ch,uint8_t pitch,uint8_t velocity){
          if(expressiveCount>=expressiveBatch->size()){++state.outputOverflow;overflowRecovery=true;return false;}
          auto &m=(*expressiveBatch)[expressiveCount++];m.size=3;m.offset=unsigned(std::min<uint64_t>(frames-1,sample>state.samples?sample-state.samples:0));m.bus=0;m.order=expressiveCount*4;m.data[0]=uint8_t((on?144:128)|ch);m.data[1]=pitch;m.data[2]=velocity;return true;
        });
        if(expressiveStream->recoveryNeeded){++state.outputOverflow;overflowRecovery=true;}
        outputCount=expressiveCount;
        for(unsigned j=0;j<outputCount;++j)(*outputBatch)[j]=(*expressiveBatch)[j];
      }
      bool outputSorted=true;
      for(unsigned j=1;j<outputCount;++j){const auto &a=(*outputBatch)[j-1],&b=(*outputBatch)[j];if(a.offset>b.offset||(a.offset==b.offset&&a.order>b.order)){outputSorted=false;break;}}
      for(unsigned j=0;j<outputCount;++j)(*outputOrder)[j]=j;
      trace.mark(7);
      {
        trace.mark(8);
        if (!outputSorted)
          std::sort(outputOrder->begin(), outputOrder->begin() + outputCount,
                    [&](unsigned a, unsigned b) {
                      auto first = (*outputBatch)[a].offset,
                           second = (*outputBatch)[b].offset;
                      if(first!=second)return first<second;
                      auto x=(*outputBatch)[a].order,y=(*outputBatch)[b].order;return x==y?a<b:x<y;
                    });
        trace.mark(9);
        for (unsigned j = 0; j < outputCount; ++j) {
          const auto &source = (*outputBatch)[(*outputOrder)[j]];
          if(!source.size)continue; // private control marker never leaves host
          ++state.midi;
          ++state.midiGenerated;
          if(source.size>=3){unsigned type=source.data[0]&240,key=(source.data[0]&15)*128+(source.data[1]&127);
            if(type==144&&source.data[2]>0){if(!held[key]){held[key]=true;++state.active;}}
            else if(type==128||(type==144&&!source.data[2])){if(held[key]){held[key]=false;--state.active;}}
            else if(type==176&&(source.data[1]==120||source.data[1]==123)){for(unsigned note=0;note<128;++note){unsigned k=(source.data[0]&15)*128+note;if(held[k]){held[k]=false;--state.active;}}}
            state.last_sample=state.samples+source.offset;state.last_status=source.data[0];state.last_note=source.data[1];state.last_value=source.data[2];
          }
          if(!outBuffer)continue;
          if (outputWrite - outputRead >= 8192) {
            ++state.midiDropped;
            ++state.outputOverflow;
            overflowRecovery = true;
            continue;
          }
          ++state.midiQueued;
          auto &destination = (*outputQueue)[outputWrite++ % 8192];
          destination.size = source.size;
          destination.offset = source.offset;
          std::memcpy(destination.data.data(), source.data.data(), source.size);
        }
        if(outBuffer)flushOutput(outBuffer, frames);
        for (unsigned q = outputRead; q != outputWrite; ++q)
          (*outputQueue)[q % 8192].offset = 0;
      }
      if (useJack)
        state.late = xruns.load(std::memory_order_relaxed);
      drainPanic();
      if(recovering&&expressiveStream->recoveryNeeded)expressiveStream->recovered();
      state.pendingOutput = outputWrite - outputRead + panicSweep.remaining() + expressiveStream->pending();
      outputPending.store(state.pendingOutput, std::memory_order_release);
      if (muted)
        finalAcknowledged.store(true, std::memory_order_release);
      state.revealCount=0;reveals.observeState([&](uint64_t id,bool hidden,unsigned mask,const std::array<unsigned,16>& volume){unsigned j=state.revealCount++;state.revealIds[j]=id;state.revealHidden[j]=hidden;state.revealMasks[j]=mask;state.revealVolumes[j]=volume;});
      state.movementRunningCount=0;movements.observe(state.samples+frames,[&](const char *id,double progress){unsigned j=state.movementRunningCount++;std::memcpy(state.movementIds[j].data(),id,36);state.movementIds[j][36]=0;state.movementProgress[j]=progress;});
      state.movementActive=movements.active;state.movementRejected=movements.rejected;state.movementEmitted=movements.emitted;state.movementCancelled=movements.cancelled;
      state.samples += frames;
      ++state.blocks;
      if (count) {
        if (maintenance)
          paused.store(true, std::memory_order_release);
        publishPerformance();
        model.snapshot(state);
        state.controllerConfig = controllers.configuration();
        state.learnTarget = controllers.learnTarget();
        state.learnCommand = controllers.learnsCommand();
        state.learnCandidate = controllers.learnCandidate();
        state.learnConflict = controllers.learnConflict();
        for (unsigned j = 0; j < 32; ++j) {
          auto t = controllers.target(
              state.controllerConfig.bindings[j].policy.target);
          state.effective[j] = t ? t->effective : 0;
          state.owners[j] = t ? t->owner : 0;
          state.returning[j] = t && t->returning;
          state.pickup[j] = t && t->takeoverPending;
        }
        for (unsigned i = 0; i < count; ++i) {
          pending[i].state = state;
          replies.push(pending[i]);
        }
      }
      auto duration = std::chrono::duration<double, std::micro>(
                          std::chrono::steady_clock::now() - start)
                          .count();
      state.max_us = std::max(state.max_us, duration);
      trace.value.xruns=xruns.load(std::memory_order_relaxed);
      trace.value.pending=state.pendingOutput;trace.value.active=movements.active;
      trace.value.rejected=movements.rejected;trace.value.overflow=state.outputOverflow;
      if(rtTrace){
        trace.value.noteEvents=tracedNotes-noteStart;trace.value.noteOns=tracedNoteOns-noteOnStart;trace.value.ccEvents=tracedCCs-ccStart;
        trace.value.orderErrors=tracedOrderErrors-orderStart;
        trace.value.instanceRejected=uint64_t(*model.instanceRejected);
        for(unsigned j=0;j<12;++j)if(*model.voiceActive[j]>.5){++trace.value.phraseInstances;int layer=int(*model.voiceLayer[j]);if(layer>=0&&layer<16)trace.value.phraseSourcesMask|=1u<<layer;}
        for(unsigned j=0;j<16;++j)if(*model.musicalState==3&&*model.phrase[j][0]>0&&*model.phrase[j][1]<.5&&*model.phraseTriggers[j]>.5){++trace.value.phraseInstances;trace.value.phraseSourcesMask|=1u<<j;}
      }
      return 0;
    };
    if (useJack) {
      jack_set_process_callback(
          jack,
          [](jack_nframes_t n, void *p) {
            return (*static_cast<std::function<int(jack_nframes_t)> *>(p))(n);
          },
          &process);
      jack_on_shutdown(jack, [](void *) { running = 0; }, nullptr);
      jack_set_xrun_callback(
          jack,
          [](void *p) {
            ++*static_cast<std::atomic<uint64_t> *>(p);
            return 0;
          },
          &xruns);
      if (jack_activate(jack))
        throw std::runtime_error("JACK activate");
      if (!inputPort.empty() &&
          jack_connect(jack, inputPort.c_str(), jack_port_name(midiIn)))
        std::cerr << "Could not connect input; use jack_connect\n";
      if (!outputPort.empty() &&
          jack_connect(jack, jack_port_name(midiOut), outputPort.c_str()))
        std::cerr << "Could not connect output; use jack_connect\n";
    }
    io = std::thread(control, listener, std::ref(commands), std::ref(replies),
                     std::ref(shutdown), std::ref(paused), std::ref(loading),
                     std::ref(patch), std::ref(model), std::ref(controllers),
                     std::ref(*performanceSnapshots), std::cref(conflicts), std::ref(movements),std::ref(echoRuntime));
    while (running) {
      if (!useJack)
        process(blockSize);
      deadline += period;
      if (std::chrono::steady_clock::now() > deadline)
        if (!useJack)
          ++state.late;
      std::this_thread::sleep_until(deadline);
    }
    shutdown = true;
    io.join(); // Retire the original queue producer before main submits
               // shutdown.
    loading = false;
    paused = false;
    Reply discarded;
    while (replies.pop(discarded)) {
    }
    // Last callback owns PANIC/output while JACK is still active.
    Request finalPanic;
    finalPanic.id = 9007199254740991ULL;
    finalPanic.op = 2;
    finalPanic.revision = -1;
    if (useJack) {
      commands.push(finalPanic);
      auto drainDeadline =
          std::chrono::steady_clock::now() +
          std::chrono::milliseconds(
              unsigned(1000.0 * (8192.0 / 64 + 8) * blockSize / sampleRate) +
              200);
      while (std::chrono::steady_clock::now() < drainDeadline &&
             (!finalAcknowledged.load(std::memory_order_acquire) ||
              outputPending.load(std::memory_order_acquire)))
        std::this_thread::sleep_for(std::chrono::milliseconds(2));
      jack_deactivate(jack);
    } else {
      paused = false;
      NSEEL_code_execute(panic_bridge);
      process(blockSize);
    }

    NSEEL_code_free(bridge);
    NSEEL_code_free(switchReset);
    NSEEL_code_free(panic_bridge);
    NSEEL_code_free(chainRecovery);
    NSEEL_code_free(phrasePlay);
    NSEEL_code_free(phraseRecord);
    NSEEL_code_free(phraseStop);NSEEL_code_free(phraseClear);
    NSEEL_code_free(edit);
    NSEEL_code_free(structure);
    NSEEL_code_free(instrumentLifecycle);
    NSEEL_code_free(phraseAssign);
    // Existing bridges are owned until processing/control threads have stopped.
    NSEEL_code_free(controllerApply);
    NSEEL_code_free(legacyConflict);
    NSEEL_code_free(cancelLearn);
    NSEEL_code_free(safeApply);
    NSEEL_code_free(cancelPending);
  } catch (const std::exception &e) {
    std::cerr << e.what() << '\n';
    if (listener >= 0)
      close(listener);
    if (bound)
      unlink(argv[2]);
    if (jack)
      jack_client_close(jack);
    if (fx)
      ysfx_free(fx);
    if (config)
      ysfx_config_free(config);
    return 1;
  }
  close(listener);
  if (bound)
    unlink(argv[2]);
  if (jack)
    jack_client_close(jack);
  ysfx_free(fx);
  ysfx_config_free(config);
  return 0;
}
