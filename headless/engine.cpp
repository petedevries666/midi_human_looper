// Native JACK MIDI host. All EEL and ownership run on one processing thread.
// Disk, sockets and JSON are confined to the control worker.
#include "ysfx.hpp"
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
struct Request {
  uint64_t id = 0;
  int op = 0, target = 0, arg = 0, revision = 1, ch = 0, note = 0, value = 0;
};
struct Switch {
  int id = 0, on = 0, type = 0, kind = 0, ch = 0, num = 0, length = 0, step = 0;
  char name[17]{};
};
struct Instrument {
  int id = 0, on = 0, input = 0, output = 0, level = 0;
  char name[17]{};
  std::array<int, 6> transformerIds{}, transformerTypes{}, transformerOn{};
  int transformerCount = 0;
};
struct Phrase {
  int events = 0, mode = 0;
  double time = 1;
};
struct Snapshot {
  uint64_t samples = 0, blocks = 0, midi = 0, late = 0, last_sample = 0;
  int revision = 1;
  unsigned pendingOutput = 0;
  int backend = 0, sampleRate = 48000, blockSize = 128;
  uint64_t outputOverflow = 0;
  int active = 0, last_status = 0, last_note = 0, last_value = 0;
  double max_us = 0;
  std::array<Switch, 16> switches{};
  std::array<Instrument, 8> instruments{};
  std::array<Phrase, 16> phrases{};
};
struct Reply {
  uint64_t id = 0;
  int status = 0;
  Snapshot state;
};
static std::atomic<bool> running{true};
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
  std::array<std::array<double *, 3>, 16> phrase;
  std::array<double *, 8> tfCount;
  std::array<std::array<double *, 6>, 8> tfCodes;
  std::array<std::array<double *, 12>, 8> tfIds, tfTypes;
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
    << r.id << ",\"engineSessionId\":" << getpid()
    << ",\"status\":" << quote(status[r.status])
    << ",\"backend\":" << quote(s.backend ? "jack" : "mock")
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
          << ",\"enabled\":" << v.transformerOn[j] << '}';
      }
      o << "]}";
    }
  o << "],\"phrases\":[";
  for (unsigned i = 0; i < 16; ++i) {
    if (i)
      o << ',';
    o << "{\"id\":" << i + 1 << ",\"events\":" << s.phrases[i].events
      << ",\"mode\":" << s.phrases[i].mode
      << ",\"timeDecay\":" << s.phrases[i].time << '}';
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
  std::string save(std::atomic<bool> &paused) {
    for (unsigned i = 0; i < 9; ++i)
      snapshot[i] = *globals[i];
    for (unsigned i = 0; i < memory.size(); ++i)
      snapshot[9 + i] = *memory[i];
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
    o << "]}\n";
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
                    PatchModel &patch) {
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
                 request.op >= 0 && request.op <= 10 && request.arg >= 0 &&
                 request.arg <= 2 && request.ch >= 0 && request.ch < 16 &&
                 request.note >= 0 && request.note < 128 &&
                 request.value >= 0 && request.value < 128;
    if (valid && request.op == 5) {
      double x;
      while (input >> x)
        patchValues.push_back(x);
      valid =
          input.eof() && patch.validate(unsigned(request.target), patchValues);
    } else if (valid && (input >> extra))
      valid = false;
    if (valid && request.op >= 6 && request.op <= 8)
      valid = request.target >= 0 && request.target < 16;
    if (valid && request.op >= 9)
      valid = request.target > 0 && request.target <= 16777215 &&
              (request.arg == 2 || request.value <= 16);
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
          auto document = patch.save(paused);
          paused.store(false, std::memory_order_release);
          send_line(fd, document, shutdown);
        } else {
          if (reply.status == 0 && request.op == 5)
            patch.load(unsigned(request.target), patchValues);
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
  bool useJack = false, demo = false;
  std::string inputPort, outputPort;
  for (int i = 3; i < argc; ++i) {
    std::string a = argv[i];
    if (a == "--jack")
      useJack = true;
    else if (a == "--demo")
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
    config = ysfx_config_new();
    fx = ysfx_new(config);
    if (!ysfx_load_file(fx, argv[1], 0) ||
        !ysfx_compile(fx, ysfx_compile_no_gfx))
      throw std::runtime_error("JSFX compilation");
    if (useJack) {
      jack_status_t status;
      jack = jack_client_open("midi_human_looper", JackNoStartServer, &status);
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
    Model model(fx);
    PatchModel patch(fx);
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
    unsigned outputRead = 0, outputWrite = 0;
    std::atomic<unsigned> outputPending{0};
    std::atomic<bool> finalAcknowledged{false};
    bool muted = false;
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
      if (outBuffer) {
        jack_midi_clear_buffer(outBuffer);
        flushOutput(outBuffer, frames);
      }
      if (useJack && !muted) {
        void *in = jack_port_get_buffer(midiIn, frames);
        unsigned n = jack_midi_get_event_count(in);
        for (unsigned i = 0; i < n; ++i) {
          jack_midi_event_t e;
          if (!jack_midi_event_get(&e, in, i) &&
              !loading.load(std::memory_order_acquire)) {
            if (inputWrite - inputRead >= 8192 || e.size > 256)
              ++state.outputOverflow;
            else {
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
      while (inputRead != inputWrite) {
        auto &m = (*inputQueue)[inputRead++ % 8192];
        ysfx_midi_event_t e{};
        e.offset = std::min(m.offset, frames - 1);
        e.size = m.size;
        e.data = m.data.data();
        if (!ysfx_send_midi(fx, &e))
          ++state.outputOverflow;
      }
      auto start = std::chrono::steady_clock::now();
      std::array<Reply, 8> pending{};
      unsigned count = 0;
      bool maintenance = false;
      Request request;
      while (count < 8 && replies.free() > count && commands.pop(request)) {
        auto &reply = pending[count++];
        reply.id = request.id;
        if (request.op != 0 && request.revision != state.revision &&
            request.revision != -1)
          reply.status = 1;
        else if (request.op == 4 || request.op == 5) {
          if (request.op == 5)
            NSEEL_code_execute(panic_bridge);
          if (request.op == 5) {
            ++state.revision;
            loading.store(true, std::memory_order_release);
          }
          maintenance = true;
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
            ++state.revision;
          }
        } else if (request.op >= 6) {
          *phraseTarget = request.target;
          NSEEL_code_execute(request.op == 6   ? phrasePlay
                             : request.op == 7 ? phraseRecord
                                               : phraseStop);
        } else if (request.op == 1) {
          *target = request.target;
          *gesture = request.arg;
          NSEEL_code_execute(bridge);
          if (*ok != 1)
            reply.status = 2;
        } else if (request.op == 2) {
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
          if (!ysfx_send_midi(fx, &event))
            reply.status = 3;
        }
      }
      ysfx_process_float(fx, nullptr, nullptr, 0, 0, frames);
      ysfx_midi_event_t event{};
      while (ysfx_receive_midi(fx, &event)) {
        ++state.midi;
        if (outBuffer) {
          if (outputWrite - outputRead >= 8192 || event.size > 256)
            ++state.outputOverflow;
          else {
            auto &m = (*outputQueue)[outputWrite++ % 8192];
            m.size = event.size;
            m.offset = event.offset;
            std::memcpy(m.data.data(), event.data, event.size);
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
                     std::ref(patch));
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
