// M0 desktop proof only: actual JSFX scheduler, no @gfx, no physical MIDI
// ports.
#include "ysfx.hpp"
#include <array>
#include <atomic>
#include <chrono>
#include <csignal>
#include <cstring>
#include <fcntl.h>
#include <iostream>
#include <poll.h>
#include <sstream>
#include <string>
#include <sys/socket.h>
#include <sys/un.h>
#include <thread>
#include <unistd.h>

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
};
struct Phrase {
  int events = 0, mode = 0;
  double time = 1;
};
struct Snapshot {
  uint64_t samples = 0, blocks = 0, midi = 0, late = 0, last_sample = 0;
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
static volatile std::sig_atomic_t running = 1;
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
  explicit Model(ysfx_t *fx) {
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
  o << "{\"protocolVersion\":1,\"schemaVersion\":7,\"revision\":1,"
       "\"requestId\":"
    << r.id << ",\"engineSessionId\":" << getpid()
    << ",\"status\":" << quote(status[r.status])
    << ",\"sampleClock\":" << s.samples << ",\"blocks\":" << s.blocks
    << ",\"midiCount\":" << s.midi << ",\"activeNotes\":" << s.active
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
        << ",\"output\":" << v.output << ",\"level\":" << v.level << '}';
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
static void control(int listener, Queue<Request, 64> &commands,
                    Queue<Reply, 64> &replies, std::atomic<bool> &shutdown) {
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
    auto end = std::chrono::steady_clock::now() + std::chrono::seconds(2);
    while (!shutdown && line.size() < 2048 &&
           std::chrono::steady_clock::now() < end) {
      pollfd q{fd, POLLIN, 0};
      if (poll(&q, 1, 20) <= 0)
        continue;
      char b[256];
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
    bool valid = complete &&
                 bool(input >> request.id >> request.op >> request.target >>
                      request.arg >> request.revision >> request.ch >>
                      request.note >> request.value) &&
                 !(input >> extra) && request.id > 0 &&
                 request.id <= 9007199254740991ULL && request.op >= 0 &&
                 request.op <= 3 && request.arg >= 0 && request.arg <= 2 &&
                 request.ch >= 0 && request.ch < 16 && request.note >= 0 &&
                 request.note < 128 && request.value >= 0 &&
                 request.value < 128;
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
      if (received)
        send_line(fd, json(reply), shutdown);
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
  if (argc != 3) {
    std::cerr << "usage: engine source.jsfx /tmp/control.sock\n";
    return 2;
  }
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
    ysfx_set_sample_rate(fx, 48000);
    ysfx_set_block_size(fx, 128);
    ysfx_set_midi_capacity(fx, 65536, false);
    ysfx_init(fx);
    if (variable(fx, "IO_SCHEMA") != 7)
      throw std::runtime_error("spike requires audited schema 7");
    execute(
        fx,
        "gmem[0]=0;panic_pending=0;state="
        "STATE_STOPPED;slider9=1;loop_len_samples=24000;"
        "store_event(0,0,144,60,90,0);store_event(0,9600,128,60,0,0);mem[LEN_"
        "BASE]=24000;mem[MODE_BASE]=0;mem[DECAY_BASE]=1;"
        "store_event(1,0,144,64,90,0);store_event(1,9600,128,64,0,0);mem[LEN_"
        "BASE+1]=24000;mem[MODE_BASE+1]=1;mem[DECAY_BASE+1]=1;"
        "sw_assign(0,1,0,72,127,0);sw_assign(1,1,0,73,127,0);mem[sw_cfg(0)]=1;"
        "mem[sw_cfg(1)]=1;mem[sw_cfg(0)+11]=1;mem[sw_cfg(0)+SW_LIST]=0;"
        "mem[sw_cfg(1)+11]=1;mem[sw_cfg(1)+SW_LIST]=1;mem[sw_cfg(0)+15]=SW_"
        "NEXT;mem[sw_cfg(0)+16]=SW_RESET;"
        "mem[sw_cfg(0)+SW_NAME]=86;mem[sw_cfg(0)+SW_NAME+1]=69;mem[sw_cfg(0)+"
        "SW_NAME+2]=82;mem[sw_cfg(0)+SW_NAME+3]=83;mem[sw_cfg(0)+SW_NAME+4]=69;"
        "mem[sw_cfg(1)+SW_NAME]=67;mem[sw_cfg(1)+SW_NAME+1]=72;mem[sw_cfg(1)+"
        "SW_NAME+2]=79;mem[sw_cfg(1)+SW_NAME+3]=82;mem[sw_cfg(1)+SW_NAME+4]=85;"
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
    Model model(fx);
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
    if (listen(listener, 16) < 0)
      throw std::runtime_error("socket listen");
    std::signal(SIGINT, stop);
    std::signal(SIGTERM, stop);
    std::signal(SIGPIPE, SIG_IGN);
    Queue<Request, 64> commands;
    Queue<Reply, 64> replies;
    std::atomic<bool> shutdown{false};
    std::thread io(control, listener, std::ref(commands), std::ref(replies),
                   std::ref(shutdown));
    Snapshot state;
    std::array<bool, 2048> held{};
    auto deadline = std::chrono::steady_clock::now();
    const auto period = std::chrono::nanoseconds(2666667);
    std::cout << "READY " << argv[2] << std::endl;
    while (running) {
      auto start = std::chrono::steady_clock::now();
      std::array<Reply, 8> pending{};
      unsigned count = 0;
      Request request;
      while (count < 8 && replies.free() > count && commands.pop(request)) {
        auto &reply = pending[count++];
        reply.id = request.id;
        if (request.revision != 1)
          reply.status = 1;
        else if (request.op == 1) {
          *target = request.target;
          *gesture = request.arg;
          NSEEL_code_execute(bridge);
          if (*ok != 1)
            reply.status = 2;
        } else if (request.op == 2)
          NSEEL_code_execute(panic_bridge);
        else if (request.op == 3) {
          uint8_t data[] = {uint8_t(144 | request.ch), uint8_t(request.note),
                            uint8_t(request.value)};
          ysfx_midi_event_t event{};
          event.size = 3;
          event.data = data;
          if (!ysfx_send_midi(fx, &event))
            reply.status = 3;
        }
      }
      ysfx_process_float(fx, nullptr, nullptr, 0, 0, 128);
      ysfx_midi_event_t event{};
      while (ysfx_receive_midi(fx, &event)) {
        ++state.midi;
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
      state.samples += 128;
      ++state.blocks;
      if (count) {
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
      deadline += period;
      if (std::chrono::steady_clock::now() > deadline)
        ++state.late;
      std::this_thread::sleep_until(deadline);
    }
    NSEEL_code_execute(panic_bridge);
    ysfx_process_float(fx, nullptr, nullptr, 0, 0, 128);
    shutdown = true;
    io.join();
    NSEEL_code_free(bridge);
    NSEEL_code_free(panic_bridge);
  } catch (const std::exception &e) {
    std::cerr << e.what() << '\n';
    if (listener >= 0)
      close(listener);
    if (bound)
      unlink(argv[2]);
    if (fx)
      ysfx_free(fx);
    if (config)
      ysfx_config_free(config);
    return 1;
  }
  close(listener);
  if (bound)
    unlink(argv[2]);
  ysfx_free(fx);
  ysfx_config_free(config);
  return 0;
}
