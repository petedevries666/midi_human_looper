// Executes the complete JSFX in ysfx/WDL EEL2, including real MIDI and LICE
// frames.
#include "ysfx.hpp"
#include <atomic>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <map>
#include <set>
#include <string>
#include <thread>
#include <vector>
static int checks = 0;
static void check(bool ok, const char *label) {
  ++checks;
  if (!ok) {
    fprintf(stderr, "FAIL: %s\n", label);
    exit(1);
  }
}
static void log(intptr_t, ysfx_log_level, const char *s) {
  fprintf(stderr, "%s\n", s);
}
struct Host {
  ysfx_config_t *c;
  ysfx_t *f;
  std::vector<uint8_t> pixels;
  Host(const char *path, bool initialize=true) : pixels(1040 * 1510 * 4) {
    c = ysfx_config_new();
    ysfx_set_log_reporter(c, log);
    f = ysfx_new(c);
    check(ysfx_load_file(f, path, 0) && ysfx_compile(f, 0),
          "compile full JSFX");
    NSEEL_VM_setramsize(f->vm.get(),33554432);
    if (!initialize) return;
    ysfx_init(f);
    ysfx_gfx_config_t g{};
    g.pixel_width = 1040;
    g.pixel_height = 1510;
    g.pixels = pixels.data();
    g.scale_factor = 1;
    ysfx_gfx_setup(f, &g);
    frame();
  }
  ~Host() {
    ysfx_free(f);
    ysfx_config_free(c);
  }
  void run(const std::string &s) {
    auto h = NSEEL_code_compile(f->vm.get(), s.c_str(), 0);
    if (!h) {
      fprintf(stderr, "%s\n%s\n", s.c_str(),
              NSEEL_code_getcodeerror(f->vm.get()));
      exit(2);
    }
    NSEEL_code_execute(h);
    NSEEL_code_free(h);
  }
  double val(const char *n) {
    auto *p = ysfx_find_var(f, n);
    return p ? *p : 0;
  }
  double eval(const std::string &s) {
    run("test_result=(" + s + ");");
    return val("test_result");
  }
  void eq(const std::string &s, double want, const char *label) {
    double v = eval(s);
    if (std::abs(v - want) > 1e-7) {
      fprintf(stderr, "%s got %.12g want %.12g\n", s.c_str(), v, want);
    }
    check(std::abs(v - want) < 1e-7, label);
  }
  void block() { ysfx_process_float(f, nullptr, nullptr, 0, 0, 128); }
  void frame(int x = 0, int y = 0, int buttons = 0) {
    ysfx_gfx_update_mouse(
        f, 0, x, y, (buttons & 1) | ((buttons & 2) ? ysfx_button_right : 0), 0,
        0);
    ysfx_gfx_run(f);
  }
  std::vector<std::vector<int>> events() {
    std::vector<std::vector<int>> v;
    ysfx_midi_event_t e{};
    while (ysfx_receive_midi(f, &e)) {
      std::vector<int> m;
      for (unsigned i = 0; i < e.size; i++)
        m.push_back(e.data[i]);
      v.push_back(m);
    }
    return v;
  }
  void midi(int st, int note, int velocity) {
    uint8_t b[] = {uint8_t(st), uint8_t(note), uint8_t(velocity)};
    ysfx_midi_event_t e{};
    e.size = 3;
    e.data = b;
    check(ysfx_send_midi(f, &e), "enqueue MIDI");
    block();
  }
  std::vector<double> payload() {
    std::vector<double> v;
    int n = int(val("PATCH_PAYLOAD_SIZE"));
    for (int i = 0; i < n; ++i)
      v.push_back(eval("mem[payload_addr(" + std::to_string(i) + ")]"));
    return v;
  }
  uint64_t hash() {
    uint64_t h = 0;
    for (auto v : pixels)
      h = h * 131 + v;
    return h;
  }
};
