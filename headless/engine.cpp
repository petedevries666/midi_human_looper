// Native JACK MIDI host. All EEL and ownership run on one processing thread.
// Disk, sockets and JSON are confined to the control worker.
#include "chain_mode.hpp"
#include "controller_wire.hpp"
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
struct Request {
  uint64_t id = 0, session = 0;
  int op = 0, target = 0, arg = 0, revision = 1, ch = 0, note = 0, value = 0;
  int module = 0, count = 0;
  std::array<ParameterChange, 4> parameters{};
  controller::Binding binding;
  controller::Configuration controllerConfig;
};
struct Switch {
  int id = 0, on = 0, type = 0, kind = 0, ch = 0, num = 0, length = 0, step = 0;
  char name[17]{};
};
struct Instrument {
  int id = 0, on = 0, input = 0, output = 0, level = 0;
  char name[17]{};
  std::array<int, 6> transformerIds{}, transformerTypes{}, transformerOn{};
  std::array<std::array<double, 4>, 6> transformerValues{};
  std::array<std::array<int, 4>, 6> transformerKinds{},
      transformerAssignments{};
  std::array<int, 6> parameterCounts{};
  int transformerCount = 0;
};
struct Phrase {
  int events = 0, mode = 0;
  double time = 1, velocityDecay = .8;
};
struct Snapshot {
  uint64_t samples = 0, blocks = 0, midi = 0, late = 0, last_sample = 0;
  int revision = 1;
  unsigned pendingOutput = 0;
  bool chain = false, chainRun = false, chainArmed = false, chainRecord = false,
       chainError = false;
  uint64_t chainFrame = 0, chainLength = 0;
  double chainBpm = 120;
  int backend = 0, sampleRate = 48000, blockSize = 128;
  uint64_t outputOverflow = 0;
  int active = 0, last_status = 0, last_note = 0, last_value = 0;
  double max_us = 0;
  std::array<Switch, 16> switches{};
  std::array<Instrument, 8> instruments{};
  std::array<Phrase, 16> phrases{};
  controller::Configuration controllerConfig;
  uint32_t learnTarget = 0;
  controller::Source learnCandidate;
  int learnConflict = 0;
  std::array<double, 32> effective{};
  std::array<uint32_t, 32> owners{};
  std::array<bool, 32> returning{}, pickup{};
};
struct Reply {
  uint64_t id = 0;
  int status = 0;
  Snapshot state;
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
  std::array<std::array<double *, 26>, 16> sw;
  std::array<std::array<double *, 22>, 8> inst;
  std::array<std::array<double *, 4>, 16> phrase;
  std::array<double *, 8> tfCount, levelAssignment, levelPending;
  std::array<std::array<double *, 6>, 8> tfCodes;
  std::array<std::array<double *, 12>, 8> tfIds, tfTypes;
  std::array<std::array<std::array<double *, 4>, 12>, 8> values, assignments,
      pendingValues;
  std::array<std::array<std::array<int, 4>, 12>, 8> kinds;
  void initParameters(ysfx_t *fx) {
    auto i = NSEEL_VM_regvar(fx->vm.get(), "remote_pi"),
         c = NSEEL_VM_regvar(fx->vm.get(), "remote_pc"),
         r = NSEEL_VM_regvar(fx->vm.get(), "remote_pr"),
         k = NSEEL_VM_regvar(fx->vm.get(), "remote_pk"),
         a = NSEEL_VM_regvar(fx->vm.get(), "remote_pa"),
         b = NSEEL_VM_regvar(fx->vm.get(), "remote_pb"),
         pending = NSEEL_VM_regvar(fx->vm.get(), "remote_pending");
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
    for (unsigned gi = 0; gi < 8; ++gi)
      for (unsigned code = 1; code < 12; ++code)
        for (unsigned row = 0; row < 4; ++row) {
          *i = gi;
          *c = code;
          *r = row;
          NSEEL_code_execute(lookup);
          kinds[gi][code][row] = int(*k);
          values[gi][code][row] = cell(fx, unsigned(*a));
          assignments[gi][code][row] = cell(fx, unsigned(*b));
          pendingValues[gi][code][row] =
              *pending ? cell(fx, unsigned(*pending)) : nullptr;
        }
    NSEEL_code_free(lookup);
    auto level = NSEEL_code_compile(
        fx->vm.get(),
        "remote_pb=exp_assign_addr(param_ti(remote_pi,1));remote_pending=param_"
        "pending_addr(param_ti(remote_pi,1));",
        0);
    if (!level)
      throw std::runtime_error("level assignment bridge");
    for (unsigned gi = 0; gi < 8; ++gi) {
      *i = gi;
      NSEEL_code_execute(level);
      levelAssignment[gi] = cell(fx, unsigned(*b));
      levelPending[gi] = cell(fx, unsigned(*pending));
    }
    NSEEL_code_free(level);
  }
  explicit Model(ysfx_t *fx) {
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
    for (unsigned i = 0; i < 16; ++i) {
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
      sw[i][24] = cell(fx, rt + 7);
      sw[i][25] = cell(fx, rt + 12);
      phrase[i][3] = cell(fx, unsigned(variable(fx, "DECAY_BASE")) + i);
      phrase[i][0] = cell(fx, unsigned(variable(fx, "COUNT_BASE")) + i);
      phrase[i][1] = cell(fx, unsigned(variable(fx, "MODE_BASE")) + i);
      phrase[i][2] = cell(fx, unsigned(variable(fx, "SW_CFG_BASE")) + 1 +
                                  (i / 4) * 128 + 112 + i % 4);
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
  bool resolve(const controller::Binding &b, unsigned &i, int &code,
               int &row) const {
    if (b.kind >= 14) {
      i = b.instrument - 1;
      code = -1;
      row = b.kind == 14 ? 2 : 3;
      return i < 16 && !b.module;
    }
    for (i = 0; i < 8; ++i)
      if (*inst[i][0] && *inst[i][1] == double(b.instrument))
        break;
    if (i == 8)
      return false;
    if (!b.module) {
      code = 0;
      row = 0;
      return b.kind == 1 && !*levelAssignment[i];
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
        int type = c < 7 ? c : int(*tfTypes[i][c]);
        int rows = type == 2 ? 3 : type == 5 ? 4 : type == 6 ? 2 : 1;
        for (row = 0; row < rows; ++row)
          if ((type == 1   ? 7
               : type == 2 ? 8 + row
               : type == 3 ? 11
               : type == 4 ? 0
               : type == 5 ? (row < 3 ? 4 + row : 12)
               : row == 0  ? 2
                           : 13) == b.kind)
            return !*assignments[i][c][row];
      }
    }
    return false;
  }
  double *bindingValue(const controller::Binding &b) const {
    unsigned i;
    int c, r;
    if (!resolve(b, i, c, r))
      return nullptr;
    return c == -1 ? phrase[i][r] : c ? values[i][c][r] : inst[i][5];
  }
  double bindingBase(const controller::Binding &b) const {
    unsigned i;
    int c, r;
    if (!resolve(b, i, c, r))
      return 0;
    auto pending = c == -1 ? nullptr
                   : c     ? pendingValues[i][c][r]
                           : levelPending[i];
    return pending && *pending != -999 ? *pending : *bindingValue(b);
  }
  void snapshot(Snapshot &s) const {
    for (unsigned i = 0; i < 16; ++i) {
      auto &v = s.switches[i];
      v.id = *sw[i][0] ? int(*sw[i][1]) : 0;
      v.on = int(*sw[i][2]);
      v.type = int(*sw[i][3]);
      v.kind = int(*sw[i][4]);
      v.ch = int(*sw[i][5]) + 1;
      v.num = int(*sw[i][6]);
      v.length = int(*sw[i][7]);
      v.step = int(*sw[i][24]) + 1;
      for (unsigned j = 0; j < 16; ++j)
        v.name[j] = char(*sw[i][8 + j]);
      s.phrases[i].events = int(*phrase[i][0]);
      s.phrases[i].mode = int(*phrase[i][1]);
      s.phrases[i].time = *phrase[i][2];
      s.phrases[i].velocityDecay = *phrase[i][3];
    }
    for (unsigned i = 0; i < 8; ++i) {
      auto &v = s.instruments[i];
      v.id = *inst[i][0] ? int(*inst[i][1]) : 0;
      v.on = int(*inst[i][2]);
      v.input = int(*inst[i][3]);
      v.output = int(*inst[i][4]);
      v.level = int(*inst[i][5]);
      v.transformerCount = std::max(0, std::min(6, int(*tfCount[i])));
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
        v.parameterCounts[j] = type == 2   ? 3
                               : type == 5 ? 4
                               : type == 6 ? 2
                                           : 1;
        for (int r = 0; r < v.parameterCounts[j]; ++r) {
          v.transformerValues[j][r] = *values[i][k][r];
          v.transformerAssignments[j][r] = int(*assignments[i][k][r]);
          v.transformerKinds[j][r] = type == 1   ? 7
                                     : type == 2 ? 8 + r
                                     : type == 3 ? 11
                                     : type == 4 ? 0
                                     : type == 5 ? (r < 3 ? 4 + r : 12)
                                     : r == 0    ? 2
                                                 : 13;
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
  o << "{\"protocolVersion\":1,\"schemaVersion\":7,\"revision\":" << s.revision
    << ","
       "\"requestId\":"
    << r.id << ",\"engineSessionId\":" << engineSession
    << ",\"status\":" << quote(status[r.status])
    << ",\"backend\":" << quote(s.backend ? "jack" : "mock")
    << ",\"chainMode\":" << s.chain << ",\"chainRunning\":" << s.chainRun
    << ",\"chainArmed\":" << s.chainArmed
    << ",\"chainRecording\":" << s.chainRecord
    << ",\"chainError\":" << s.chainError << ",\"chainFrame\":" << s.chainFrame
    << ",\"chainLength\":" << s.chainLength << ",\"chainBpm\":" << s.chainBpm
    << ",\"sampleRate\":" << s.sampleRate << ",\"blockSize\":" << s.blockSize
    << ",\"sampleClock\":" << s.samples << ",\"blocks\":" << s.blocks
    << ",\"midiCount\":" << s.midi << ",\"activeNotes\":" << s.active
    << ",\"pendingOutput\":" << s.pendingOutput
    << ",\"outputOverflow\":" << s.outputOverflow
    << ",\"lateBlocks\":" << s.late << ",\"maxCallbackUs\":" << s.max_us
    << ",\"lastEvent\":[" << s.last_sample << "," << s.last_status << ","
    << s.last_note << "," << s.last_value << "],\"switches\":[";
  bool comma = false;
  for (auto &v : s.switches)
    if (v.id) {
      if (comma)
        o << ',';
      comma = true;
      o << "{\"id\":" << v.id << ",\"name\":" << quote(v.name)
        << ",\"enabled\":" << v.on << ",\"type\":" << v.type
        << ",\"kind\":" << v.kind << ",\"channel\":" << v.ch
        << ",\"number\":" << v.num << ",\"length\":" << v.length
        << ",\"step\":" << v.step << '}';
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
            << ",\"assignment\":" << v.transformerAssignments[j][r] << '}';
        }
        o << "]}";
      }
      o << "]}";
    }
  o << "],\"phrases\":[";
  for (unsigned i = 0; i < 16; ++i) {
    if (i)
      o << ',';
    o << "{\"id\":" << i + 1 << ",\"events\":" << s.phrases[i].events
      << ",\"mode\":" << s.phrases[i].mode
      << ",\"timeDecay\":" << s.phrases[i].time
      << ",\"velocityDecay\":" << s.phrases[i].velocityDecay << '}';
  }
  o << "],\"controllerEngine\":"
    << controller::configurationJson(s.controllerConfig)
    << ",\"controllerLearn\":{\"target\":" << s.learnTarget
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
  o << "]}\n";
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
  std::array<unsigned, 8> sizes{};
  std::array<unsigned, 6> markers{};
  std::vector<double> snapshot;
  ysfx_t *fx;
  explicit PatchModel(ysfx_t *f) : fx(f) {
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
    memory.reserve(sizes[7]);
    snapshot.resize(sizes[7] + 9);
    for (unsigned i = 0; i < sizes[7]; ++i) {
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
  }
  bool validate(unsigned schema, const std::vector<double> &v) const {
    if (schema < 1 || schema > 7 || v.size() < 10)
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
    return v[0] >= 0 && v[0] <= 48000.0 * 3600 && v[8] >= 0 && v[8] < 16;
  }
  std::string save(std::atomic<bool> &paused,
                   const controller::Configuration &config,
                   const Model &model) {
    for (unsigned i = 0; i < 9; ++i)
      snapshot[i] = *globals[i];
    for (unsigned i = 0; i < memory.size(); ++i)
      snapshot[9 + i] = *memory[i];
    // Save committed bases, never a transient pedal/return value, in the legacy
    // payload.
    for (auto &b : config.bindings)
      if (b.policy.id) {
        auto address = model.bindingValue(b);
        if (!address)
          continue;
        double v = b.base;
        int k = b.kind;
        double low = k == 7   ? -48
                     : k == 0 ? .2
                     : k == 5 ? .25
                     : k == 6 ? .02
                              : 0;
        double high = k == 7              ? 48
                      : k == 0            ? 3
                      : k == 5            ? 16
                      : k == 6 || k == 12 ? 1
                      : k == 4            ? 2
                      : k == 8 || k == 11 ? 3
                                          : 127;
        bool bins = k == 3 || k == 4 || k == 8 || k == 11 || k == 12;
        double step = k == 0 || k == 6 ? .01 : k == 5 ? .25 : 1;
        double physical =
            bins ? std::min(high, std::floor(v * (high + 1)))
                 : std::floor((low + (high - low) * v) / step + .5) * step;
        if (k >= 14)
          physical = k == 14 ? std::pow(2, 2 * v - 1) : .2 + .8 * v;
        for (unsigned j = 0; j < memory.size(); ++j)
          if (memory[j] == address) {
            snapshot[9 + j] = physical;
            break;
          }
      }
    paused.store(false, std::memory_order_release);
    std::ostringstream o;
    o << std::setprecision(17)
      << "{\"format\":\"MIDI_HUMAN_LOOPER_PATCH\",\"schema\":7,\"work_mem_"
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
static void control(int listener, Queue<Request, 64> &commands,
                    Queue<Reply, 64> &replies, std::atomic<bool> &shutdown,
                    std::atomic<bool> &paused, std::atomic<bool> &loading,
                    PatchModel &patch, Model &model,
                    controller::Host &controllers,
                    const std::function<bool(int, int, int)> &conflicts) {
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
    while (!shutdown && line.size() < 16000000 &&
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
    bool valid = complete &&
                 bool(input >> request.id >> request.op >> request.target >>
                      request.arg >> request.revision >> request.ch >>
                      request.note >> request.value) &&
                 request.id > 0 && request.id <= 9007199254740991ULL &&
                 request.op >= 0 && request.op <= 20 && request.arg >= 0 &&
                 request.arg <= (request.op == 13                       ? 5
                                 : request.op == 15 || request.op == 20 ? 3
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
    if (valid && request.op == 5) {
      double x;
      while (input >> x)
        patchValues.push_back(x);
      valid = patch.validate(unsigned(request.target), patchValues);
      if (!input.eof()) {
        input.clear();
        std::string marker;
        valid = valid && bool(input >> marker) && marker == "controllers" &&
                controller::readConfiguration(input, request.controllerConfig);
        if (input >> extra)
          valid = false;
      }
    } else if (valid && request.op == 16) {
      valid = controller::readBinding(input, request.binding) &&
              request.binding.policy.id == unsigned(request.target) &&
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
              request.count > 0 && request.count <= 4;
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
      valid = request.target >= 0 && request.target < 16;
    if (valid && request.op >= 9 && request.op <= 10)
      valid = request.target > 0 && request.target <= 16777215 &&
              (request.arg == 2 || request.value <= 16);
    if (valid && request.op == 11)
      valid = request.arg <= 1 && request.note <= 16;
    if (valid && request.op >= 11 && request.op <= 18)
      valid = request.target > 0 && request.target <= 16777215;
    if (valid && request.op == 20)
      valid = request.target >= 0 && request.target < 16;
    if (!valid)
      send_line(fd, "{\"status\":\"invalid\"}\n", shutdown);
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
        if (reply.status == 0 && request.op == 4) {
          auto document =
              patch.save(paused, reply.state.controllerConfig, model);
          paused.store(false, std::memory_order_release);
          send_line(fd, document, shutdown);
        } else {
          if (reply.status == 0 && request.op == 5 && reply.state.chain &&
              patchValues[0] != double(reply.state.chainLength))
            reply.status = 3;
          if (reply.status == 0 && request.op == 5) {
            std::vector<double> previous(9 + patch.memory.size());
            for (unsigned j = 0; j < 9; ++j)
              previous[j] = *patch.globals[j];
            for (unsigned j = 0; j < patch.memory.size(); ++j)
              previous[9 + j] = *patch.memory[j];
            patch.load(unsigned(request.target), patchValues);
            bool collision = false;
            for (auto &source : request.controllerConfig.sources)
              if (source.id && source.kind &&
                  conflicts(source.kind, source.channel, source.number))
                collision = true;
            if (collision ||
                !controllers.replace(request.controllerConfig,
                                     [&](const controller::Binding &b) {
                                       return model.bindingValue(b) != nullptr;
                                     })) {
              patch.load(7, previous);
              reply.status = 3;
            }
          }
          send_line(fd, json(reply), shutdown);
        }
      }
      if (request.op == 4 || request.op == 5) {
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
  bool useJack = false, demo = false, chainMode = false;
  std::string clientName = "midi_human_looper";
  std::string inputPort, outputPort;
  for (int i = 3; i < argc; ++i) {
    std::string a = argv[i];
    if (a == "--jack")
      useJack = true;
    else if (a == "--chain")
      chainMode = true;
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
  try {
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
    ysfx_init(fx);
    if (variable(fx, "IO_SCHEMA") != 7)
      throw std::runtime_error("spike requires audited schema 7");
    if (chainMode)
      execute(fx, "ext_noinit=1;gmem[0]=0;slider9=1;remote_ci=0;loop(INST_CAP,"
                  "mem[engine_addr(INST_ENABLED_BASE,remote_ci)]=remote_ci==0;"
                  "remote_ci+=1;);mem[engine_addr(INST_IN_BASE,0)]=0;mem["
                  "engine_addr(INST_OUT_BASE,0)]=0;");
    ChainMode chain(fx, chainMode);
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
    for (unsigned i = 0; i < unsigned(variable(fx, "I_RUNTIME_END")); i += 4096)
      cell(fx, i);
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
    auto panic_bridge = NSEEL_code_compile(
        fx->vm.get(), "sw_stop_phrases();reset_note_runtime();panic_pending=1;",
        0);
    if (!panic_bridge)
      throw std::runtime_error("panic bridge compilation");
    auto phraseTarget = NSEEL_VM_regvar(fx->vm.get(), "remote_phrase");
    auto phrasePlay = NSEEL_code_compile(
        fx->vm.get(),
        "trigger_request=remote_phrase;process_phrase_trigger(0,0);", 0);
    auto phraseRecord = NSEEL_code_compile(
        fx->vm.get(), "select_phrase_record(remote_phrase);", 0);
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
    auto legacyConflict = NSEEL_code_compile(
        fx->vm.get(),
        "remote_learn_conflict=0;remote_learn_j=0;loop(SW_COUNT+CONTROLLERS+"
        "LAYERS,learn_matches(remote_learn_j,remote_learn_kind,remote_learn_ch,"
        "remote_learn_num)?remote_learn_conflict=1;remote_learn_j+=1;);",
        0);
    auto cancelLearn = NSEEL_code_compile(fx->vm.get(), "learn_cancel();", 0);
    if (!controllerApply || !legacyConflict || !cancelLearn)
      throw std::runtime_error("controller bridge");
    Model model(fx);
    PatchModel patch(fx);
    controller::Host controllers;
    std::function<bool(int, int, int)> conflicts = [&](int kind, int ch,
                                                       int num) {
      *learnKind = kind;
      *learnCh = ch;
      *learnNum = num;
      NSEEL_code_execute(legacyConflict);
      return *learnConflict != 0;
    };
    auto resolveBinding = [&](const controller::Binding &b) {
      return model.bindingValue(b) != nullptr;
    };
    auto normalizedBase = [](int k, double v) {
      if (k >= 14)
        return controller::clamp(k == 14 ? (std::log2(v <= 0 ? 1 : v) + 1) / 2
                                         : (v - .2) / .8);
      double low = k == 7 ? -48 : k == 0 ? .2 : k == 5 ? .25 : k == 6 ? .02 : 0;
      double high = k == 7              ? 48
                    : k == 0            ? 3
                    : k == 5            ? 16
                    : k == 6 || k == 12 ? 1
                    : k == 4            ? 2
                    : k == 8 || k == 11 ? 3
                                        : 127;
      bool bins = k == 3 || k == 4 || k == 8 || k == 11 || k == 12;
      return controller::clamp(bins ? (v + .5) / (high + 1)
                                    : (v - low) / (high - low));
    };
    auto applyBinding = [&](const controller::Binding &b, double value) {
      unsigned i;
      int code, row;
      if (!model.resolve(b, i, code, row))
        return;
      if (code == -1) {
        *model.phrase[i][row] =
            b.kind == 14 ? std::pow(2, 2 * value - 1) : .2 + .8 * value;
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
    Queue<Request, 64> commands;
    Queue<Reply, 64> replies;
    std::atomic<bool> shutdown{false}, paused{false}, loading{false};
    std::thread io;
    Snapshot state;
    state.backend = useJack;
    state.sampleRate = sampleRate;
    state.blockSize = blockSize;
    std::array<bool, 2048> held{};
    struct MidiPacket {
      unsigned size = 0, offset = 0;
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
    unsigned outputRead = 0, outputWrite = 0;
    std::atomic<unsigned> outputPending{0};
    std::atomic<bool> finalAcknowledged{false};
    bool muted = false, overflowRecovery = false;
    std::unique_ptr<std::array<MidiPacket, 8192>> inputQueue(
        new std::array<MidiPacket, 8192>());
    unsigned inputRead = 0, inputWrite = 0;
    std::atomic<uint64_t> xruns{0};
    auto flushOutput = [&](void *buffer, jack_nframes_t frames) {
      unsigned budget = 64;
      while (outputRead != outputWrite && budget--) {
        auto &m = (*outputQueue)[outputRead % 8192];
        if (jack_midi_event_write(buffer, std::min(m.offset, frames - 1),
                                  m.data.data(), m.size))
          break;
        ++outputRead;
      }
    };
    auto deadline = std::chrono::steady_clock::now();
    const auto period =
        std::chrono::nanoseconds(uint64_t(1e9 * blockSize / sampleRate));
    std::cout << "READY " << argv[2] << std::endl;
    std::function<int(jack_nframes_t)> process = [&](jack_nframes_t frames) {
      void *outBuffer =
          useJack ? jack_port_get_buffer(midiOut, frames) : nullptr;
      bool recovering = overflowRecovery;
      overflowRecovery = false;
      if (outBuffer) {
        jack_midi_clear_buffer(outBuffer);
        if (recovering) {
          controllers.panic();
          outputRead = outputWrite;
          inputRead = inputWrite;
          ysfx_midi_clear(fx->midi.in.get());
          NSEEL_code_execute(panic_bridge);
          for (unsigned ch = 0; ch < 16; ++ch)
            for (unsigned cc : {64u, 123u, 120u}) {
              uint8_t data[] = {uint8_t(176 | ch), uint8_t(cc), 0};
              if (jack_midi_event_write(outBuffer, 0, data, 3))
                overflowRecovery = true;
            }
        } else
          flushOutput(outBuffer, frames);
      }
      if (useJack && !muted && !recovering) {
        void *in = jack_port_get_buffer(midiIn, frames);
        unsigned n = jack_midi_get_event_count(in);
        for (unsigned i = 0; i < n; ++i) {
          jack_midi_event_t e;
          if (!jack_midi_event_get(&e, in, i) &&
              !loading.load(std::memory_order_acquire)) {
            if (inputWrite - inputRead >= 8192 || e.size > 256) {
              ++state.outputOverflow;
              overflowRecovery = true;
            } else {
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
      unsigned inputBudget = 128;
      while (inputRead != inputWrite && inputBudget--) {
        auto &m = (*inputQueue)[inputRead++ % 8192];
        ysfx_midi_event_t e{};
        e.offset = std::min(m.offset, frames - 1);
        e.size = m.size;
        e.data = m.data.data();
        auto before = controllers.learnTarget();
        if (controllers.midi(e.data, e.size,
                             (state.samples + e.offset) / double(sampleRate),
                             conflicts)) {
          if (before && !controllers.learnTarget())
            ++state.revision;
          continue;
        }
        if (!ysfx_send_midi(fx, &e)) {
          ++state.outputOverflow;
          overflowRecovery = true;
        }
      }
      for (unsigned q = inputRead; q != inputWrite; ++q)
        (*inputQueue)[q % 8192].offset = 0;
      auto start = std::chrono::steady_clock::now();
      std::array<Reply, 8> pending{};
      unsigned count = 0;
      bool maintenance = false;
      Request request;
      while (count < 8 && replies.free() > count && commands.pop(request)) {
        auto &reply = pending[count++];
        reply.id = request.id;
        if (request.op != 0 &&
            ((request.session && request.session != engineSession) ||
             (request.revision != state.revision && request.revision != -1)))
          reply.status = 1;
        else if (request.op == 4 || request.op == 5) {
          if (chainMode) {
            chain.cancel();
            NSEEL_code_execute(panic_bridge);
          }
          if (request.op == 5)
            NSEEL_code_execute(panic_bridge);
          if (request.op == 5) {
            chain.cancel();
            controllers.panic();
            ++state.revision;
            loading.store(true, std::memory_order_release);
          }
          maintenance = true;
        } else if (request.op == 20) {
          if (!chainMode)
            reply.status = 3;
          else {
            if (request.arg == 0) {
              controllers.panic();
              NSEEL_code_execute(panic_bridge);
            }
            if (request.arg == 1 || request.arg == 2) {
              if (jack)
                jack_transport_start(jack);
            }
            if (!chain.command(request.arg, request.target))
              reply.status = 3;
          }
        } else if (request.op >= 14) {
          if (request.op == 14) {
            controller::Source source;
            source.id = request.target;
            source.kind = request.arg;
            source.channel = request.ch;
            source.number = request.note;
            if (source.kind &&
                (source.kind == 2 &&
                     (source.number == 64 || source.number >= 120) ||
                 conflicts(source.kind, source.channel, source.number)))
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
            else if (request.arg == 2)
              valid = controllers.learnTarget() == unsigned(request.target) &&
                      controllers.confirm();
            else
              valid = controllers.forget(request.target);
            if (!valid)
              reply.status = 3;
            else
              ++state.revision;
          } else if (request.op == 16) {
            auto b = request.binding;
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
              else
                ++state.revision;
            }
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
            if (!controllers.midi(data, 3,
                                  (state.samples + frames) / double(sampleRate),
                                  conflicts)) {
              ysfx_midi_event_t event{};
              event.size = 3;
              event.data = data;
              if (!ysfx_send_midi(fx, &event))
                reply.status = 3;
            }
            if (before && !controllers.learnTarget())
              ++state.revision;
          }
        } else if (request.op == 13) {
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
                if (destination < 0 || destination >= inst.transformerCount)
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
            model.snapshot(state);
            int slot = -1;
            for (int j = 0; j < state.instruments[i].transformerCount; ++j)
              if (state.instruments[i].transformerIds[j] == request.module)
                slot = j;
            if (slot < 0)
              reply.status = 2;
            else {
              auto &inst = state.instruments[i];
              std::array<int, 4> rows{};
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
                double low = change.kind == 7   ? -48
                             : change.kind == 0 ? .2
                             : change.kind == 5 ? .25
                             : change.kind == 6 ? .02
                                                : 0;
                double high = change.kind == 7                        ? 48
                              : change.kind == 0                      ? 3
                              : change.kind == 5                      ? 16
                              : change.kind == 6 || change.kind == 12 ? 1
                              : change.kind == 4                      ? 2
                              : change.kind == 8 || change.kind == 11 ? 3
                                                                      : 127;
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
            if (jack && request.op != 8)
              jack_transport_start(jack);
            if (!chain.command(request.op == 6   ? 1
                               : request.op == 7 ? 2
                                                 : 3,
                               request.target))
              reply.status = 3;
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
          chain.cancel();
          controllers.panic();
          ysfx_midi_clear(fx->midi.in.get());
          inputRead = inputWrite;
          NSEEL_code_execute(panic_bridge);
          if (request.id == 9007199254740991ULL)
            muted = true;
        } else if (request.op == 3) {
          uint8_t data[] = {uint8_t(144 | request.ch), uint8_t(request.note),
                            uint8_t(request.value)};
          ysfx_midi_event_t event{};
          event.size = 3;
          event.data = data;
          auto before = controllers.learnTarget();
          if (controllers.midi(data, 3,
                               (state.samples + frames) / double(sampleRate),
                               conflicts)) {
            if (before && !controllers.learnTarget())
              ++state.revision;
          } else if (!ysfx_send_midi(fx, &event))
            reply.status = 3;
        }
      }
      if (controllers.tick((state.samples + frames) / double(sampleRate),
                           resolveBinding, applyBinding))
        ++state.revision;
      if (chainMode) {
        jack_position_t position{};
        bool rolling =
            jack ? jack_transport_query(jack, &position) == JackTransportRolling
                 : true;
        auto frame = jack ? uint64_t(position.frame) : state.samples;
        double bpm =
            position.valid & JackPositionBBT ? position.beats_per_minute : 120.;
        if (!std::isfinite(bpm) || bpm < 30 || bpm > 240)
          bpm = 120.;
        if (chain.tick(frame, frames, sampleRate, rolling, bpm,
                       jack ? uint64_t(jack_last_frame_time(jack)) : 0)) {
          controllers.panic();
          if (chain.run)
            *ysfx_find_var(fx, "panic_pending") = 1;
          else
            NSEEL_code_execute(panic_bridge);
        }
        state.chain = true;
        state.chainRun = chain.run;
        state.chainArmed = chain.armed;
        state.chainRecord = chain.recording;
        state.chainError = chain.error;
        state.chainFrame = frame;
        state.chainLength = chain.length;
        state.chainBpm = chain.bpm;
        ysfx_time_info_t time{};
        time.tempo = chain.bpm;
        time.playback_state =
            rolling ? ysfx_playback_playing : ysfx_playback_paused;
        time.time_signature[0] = 4;
        time.time_signature[1] = 4;
        ysfx_set_time_info(fx, &time);
      }
      ysfx_process_float(fx, nullptr, nullptr, 0, 0, frames);
      ysfx_midi_event_t event{};
      unsigned outputCount = 0;
      bool outputSorted = true;
      while (ysfx_receive_midi(fx, &event)) {
        ++state.midi;
        if (outBuffer) {
          if (outputCount >= 8192 || event.size > 256) {
            ++state.outputOverflow;
            overflowRecovery = true;
          } else {
            auto &m = (*outputBatch)[outputCount];
            m.size = event.size;
            m.offset = std::min(event.offset, frames - 1);
            std::memcpy(m.data.data(), event.data, event.size);
            if (outputCount &&
                (*outputBatch)[outputCount - 1].offset > m.offset)
              outputSorted = false;
            (*outputOrder)[outputCount] = outputCount;
            ++outputCount;
          }
        }
        if (event.size >= 3) {
          int type = event.data[0] & 240,
              key = (event.data[0] & 15) * 128 + (event.data[1] & 127);
          if (type == 144 && event.data[2] > 0) {
            if (!held[key]) {
              held[key] = true;
              ++state.active;
            }
          } else if (type == 128 || (type == 144 && event.data[2] == 0)) {
            if (held[key]) {
              held[key] = false;
              --state.active;
            }
          }
          state.last_sample = state.samples + event.offset;
          state.last_status = event.data[0];
          state.last_note = event.data[1];
          state.last_value = event.data[2];
        }
      }
      if (outBuffer) {
        if (!outputSorted)
          std::sort(outputOrder->begin(), outputOrder->begin() + outputCount,
                    [&](unsigned a, unsigned b) {
                      auto first = (*outputBatch)[a].offset,
                           second = (*outputBatch)[b].offset;
                      return first == second ? a < b : first < second;
                    });
        for (unsigned j = 0; j < outputCount; ++j) {
          if (outputWrite - outputRead >= 8192) {
            ++state.outputOverflow;
            overflowRecovery = true;
            continue;
          }
          auto &destination = (*outputQueue)[outputWrite++ % 8192];
          const auto &source = (*outputBatch)[(*outputOrder)[j]];
          destination.size = source.size;
          destination.offset = source.offset;
          std::memcpy(destination.data.data(), source.data.data(), source.size);
        }
        flushOutput(outBuffer, frames);
        for (unsigned q = outputRead; q != outputWrite; ++q)
          (*outputQueue)[q % 8192].offset = 0;
      }
      if (useJack)
        state.late = xruns.load(std::memory_order_relaxed);
      state.pendingOutput = outputWrite - outputRead;
      outputPending.store(state.pendingOutput, std::memory_order_release);
      if (muted)
        finalAcknowledged.store(true, std::memory_order_release);
      state.samples += frames;
      ++state.blocks;
      if (count) {
        if (maintenance)
          paused.store(true, std::memory_order_release);
        model.snapshot(state);
        state.controllerConfig = controllers.configuration();
        state.learnTarget = controllers.learnTarget();
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
                     std::cref(conflicts));
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
    NSEEL_code_free(panic_bridge);
    NSEEL_code_free(phrasePlay);
    NSEEL_code_free(phraseRecord);
    NSEEL_code_free(phraseStop);
    NSEEL_code_free(edit);
    NSEEL_code_free(structure);
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
