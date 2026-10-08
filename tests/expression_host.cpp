// Executes the complete JSFX in ysfx/WDL EEL2, including real MIDI and LICE
// frames.
#include "ysfx.hpp"
#include <atomic>
#include <cmath>
#include <cstdio>
#include <cstdlib>
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
  Host(const char *path) : pixels(1040 * 1510 * 4) {
    c = ysfx_config_new();
    ysfx_set_log_reporter(c, log);
    f = ysfx_new(c);
    check(ysfx_load_file(f, path, 0) && ysfx_compile(f, 0),
          "compile full JSFX");
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
static void configure(Host &h) {
  h.run("mem[INST_TRANSFORM_COUNT_BASE]=6;i=0;loop(6,mem[INST_TRANSFORM_TYPE_"
        "BASE+i]=i+1;i+=1;);mem[INST_ARP_ENABLED_BASE]=0;");
}
static void assignment(Host &h) {
  std::set<int> ids;
  for (int gi = 0; gi < 3; gi++)
    for (int k = 0; k < 14; k++) {
      std::string ti =
          "param_ti(" + std::to_string(gi) + "," + std::to_string(k) + ")";
      ids.insert(int(h.eval(ti)));
      h.eq("param_gi(" + ti + ")", gi, "instrument identity");
      h.eq("param_kind(" + ti + ")", k, "parameter identity");
      for (int c = 1; c <= 4; c++) {
        h.run("param_runtime_reset();mem[exp_assign_addr(" + ti +
              ")]=" + std::to_string(c) + ";controller_set_value(" +
              std::to_string(c - 1) + ",0);param_expression_tick();");
        std::string value = "mem[param_addr(" + std::to_string(gi) + "," +
                            std::to_string(k) + ")]";
        h.eq(value, h.eval("param_min(" + std::to_string(k) + ")"),
             "controller minimum for every parameter");
        h.run("controller_set_value(" + std::to_string(c - 1) +
              ",1);param_expression_tick();");
        h.eq(value, h.eval("param_max(" + std::to_string(k) + ")"),
             "controller maximum for every parameter");
        h.run("mem[exp_assign_addr(" + ti + ")]=0;controller_set_value(" +
              std::to_string(c - 1) + ",0);param_expression_tick();");
        h.eq(value, h.eval("param_max(" + std::to_string(k) + ")"),
             "NONE retains last sounding value");
      }
    }
  check(ids.size() == 42, "42 independent IDs");
  check(h.val("PARAM_MOD_ON_LAST_BASE") + 3 < 1048576,
        "memory below JSFX ceiling");
  h.run(
      "param_extension_reset();ti=param_ti(0,EXP_T_VEL);mem[exp_assign_addr(ti)"
      "]=1;curve_factory(ti,4);ti=param_ti(1,EXP_T_VEL);mem[exp_assign_addr(ti)"
      "]=1;curve_factory(ti,3);ctrl_val0=.25;param_expression_tick();");
  h.eq("mem[INST_VEL_BASE]", 2.3, "independent inverse curve");
  h.eq("mem[INST_VEL_BASE+1]", .9, "independent linear curve");
  h.run("ti=param_ti(0,PARAM_TRANSPOSE);curve_factory(ti,1);");
  h.eq("exp_curve_value(ti,0)", 0, "multipoint minimum");
  h.eq("exp_curve_value(ti,.5)", .4, "multipoint middle interpolation");
  h.eq("exp_curve_value(ti,1)", .8, "multipoint plateau");
  h.run("curve_factory(ti,3);mem[exp_bend_addr(ti)]=.5;");
  h.eq("exp_curve_value(ti,.5)", std::pow(.5, 3.5), "positive segment bend");
  h.run("mem[exp_bend_addr(ti)]=-.5;");
  h.eq("exp_curve_value(ti,.5)", 1 - std::pow(.5, 3.5),
       "negative segment bend");
  h.run("param_extension_reset();mem[exp_assign_addr(param_ti(0,EXP_T_VEL))]=1;"
        "mem[exp_assign_addr(param_ti(0,EXP_T_MOD))]=2;curve_factory(param_ti("
        "0,EXP_T_VEL),3);curve_factory(param_ti(0,EXP_T_MOD),3);ctrl_val0=.2;"
        "ctrl_val1=.8;param_expression_tick();");
  h.eq("mem[INST_VEL_BASE]", .76, "velocity on controller1");
  h.eq("mem[INST_MOD_BASE]", 102, "modulation on independent controller2");
  h.run("mem[exp_assign_addr(param_ti(0,EXP_T_VEL))]=0;mem[exp_assign_addr("
        "param_ti(0,EXP_T_MOD))]=0;");
  h.eq("param_scale(EXP_T_ARP_MODE,.33332)", 0, "enum lower boundary");
  h.eq("param_scale(EXP_T_ARP_MODE,1/3)", 1, "enum upper boundary");
  h.eq("param_scale(PARAM_ARP_HOLD,.49999)", 0, "hold below threshold");
  h.eq("param_scale(PARAM_ARP_HOLD,.5)", 1, "hold threshold");
  h.eq("param_scale(EXP_T_VEL,.501)", 1.6, "continuous resolution");
  h.run("param_extension_reset();mem[INST_ARP_ENABLED_BASE]=0;ti=param_ti(0,"
        "PARAM_ARP_HOLD);mem[exp_assign_addr(ti)]=1;ctrl_val0=1;param_"
        "expression_tick();");
  h.eq("mem[INST_ARP_HOLD_BASE]", 1, "HOLD assigned");
  h.eq("mem[INST_ARP_ENABLED_BASE]", 0, "HOLD does not enable ARP");
  h.eq("param_ti(-1,0)", -1, "reject invalid instrument");
  h.eq("param_ti(0,14)", -1, "reject invalid parameter");
  h.eq("param_ti(.5,0)", -1, "reject fractional instrument");
  h.eq("param_ti(0,.5)", -1, "reject fractional kind");
}
static void persistence(Host &h, const char *baseline) {
  Host old(baseline);
  const char *names[] = {"WORK_MEM_SIZE",        "PATCH1_BASE",
                         "PATCH2_BASE",          "VOICE_ACTIVE_BASE",
                         "INST_EXP_ASSIGN_BASE", "INST_EXP_X_BASE",
                         "PHRASE_NOTE_BASE",     "MONO_ACTIVE_CH_BASE"};
  for (auto n : names)
    check(h.val(n) == old.val(n), "frozen memory offsets");
  h.run("param_extension_reset();mem[17]=12345;mem[exp_assign_addr(param_ti(2,"
        "PARAM_TRANSPOSE))]=4;mem[exp_y_addr(param_ti(2,PARAM_TRANSPOSE))]=.25;"
        "save_patch(1);mem[17]=54321;mem[exp_assign_addr(param_ti(2,PARAM_"
        "TRANSPOSE))]=2;save_patch(2);current_patch=2;load_patch(1);");
  h.eq("mem[17]", 12345, "bank1 phrase material");
  h.eq("mem[exp_assign_addr(param_ti(2,PARAM_TRANSPOSE))]", 4,
       "bank1 extended assignment");
  h.run("load_patch(2);");
  h.eq("mem[17]", 54321, "bank2 phrase material");
  h.eq("mem[exp_assign_addr(param_ti(2,PARAM_TRANSPOSE))]", 2,
       "bank2 extended assignment");
  h.run("external_patch_save_request(2);j=0;loop(PATCH_PAYLOAD_SIZE,mem["
        "payload_addr(j)]=0;j+=1;);external_patch_apply();");
  h.eq("mem[17]", 54321, "JSON complete payload restores phrases");
  h.eq("mem[exp_assign_addr(param_ti(2,PARAM_TRANSPOSE))]", 2,
       "JSON extended assignment");
  h.eq("mem[exp_y_addr(param_ti(2,PARAM_TRANSPOSE))]", .25,
       "JSON extended curve");
  h.run("gmem[2]=1;gmem[3]=WORK_MEM_SIZE;gmem[IO_PAYLOAD_BASE+17]=777;gmem[IO_"
        "PAYLOAD_BASE+INST_EXP_ASSIGN_BASE]=3;gmem[IO_PAYLOAD_BASE+INST_EXP_Y_"
        "BASE]=.7;external_patch_apply();");
  h.eq("mem[17]", 777, "schema1 phrase migration");
  h.eq("mem[INST_EXP_ASSIGN_BASE]", 3, "schema1 assignment preserved");
  h.eq("mem[INST_EXP_Y_BASE]", .7, "schema1 curve preserved");
  h.eq("mem[PARAM_MOD_CC_BASE]", 1, "legacy modulation CC default");
  h.eq("mem[exp_assign_addr(param_ti(2,PARAM_TRANSPOSE))]", 0,
       "legacy appended targets unassigned");
  h.run("gmem[2]=2;gmem[3]=PATCH_PAYLOAD_SIZE;gmem[IO_PAYLOAD_BASE+WORK_MEM_"
        "SIZE]=0;external_patch_apply();");
  h.eq("io_status", 5, "reject wrong extension marker");
  h.eq("mem[17]", 777, "invalid extension cannot change phrase material");
  h.run("gmem[2]=2;gmem[3]=WORK_MEM_SIZE;external_patch_apply();");
  h.eq("io_status", 5, "reject truncated schema2 payload");
  h.eq("mem[17]", 777, "invalid import cannot change phrase material");
}
static void gui(Host &h) {
  configure(h);
  h.run("param_extension_reset();param_runtime_reset();panic_pending=0;exp_"
        "editor_ti=-1;ui_scroll=0;");
  // Exercise actual clicks for all 12 transformer parameters, rather than only
  // calling setters.
  int counts[] = {1, 3, 1, 1, 4, 2};
  for (int gi = 0; gi < 3; gi++) {
    h.run("mem[INST_TRANSFORM_COUNT_BASE+" + std::to_string(gi) +
          "]=6;i=0;loop(6,mem[INST_TRANSFORM_TYPE_BASE+" + std::to_string(gi) +
          "*6+i]=i+1;i+=1;);");
    for (int slot = 0; slot < 6; slot++)
      for (int row = 0; row < counts[slot]; row++) {
        h.run("selected_transform_gi=" + std::to_string(gi) +
              ";selected_transform_slot=" + std::to_string(slot) + ";");
        h.frame();
        int ey = int(h.val("exp_y")) - 216 + 60 + row * 34;
        h.frame(200, ey, 2);
        h.frame(200, ey, 0);
        double ti =
            h.eval("param_ti(" + std::to_string(gi) + ",param_editor_kind(" +
                   std::to_string(slot + 1) + "," + std::to_string(row) + "))");
        h.eq("controller_assign_ti", ti,
             "right click captures exact parameter");
        int ax = int(h.val("ax")), ay = int(h.val("ay"));
        h.frame(ax + 10, ay + 35, 1);
        h.eq("exp_editor_ti", ti, "assignment immediately selects its curve");
        h.eq("exp_drag_point", -1, "assignment clears stale curve capture");
        h.frame();
        check(h.val("cy") > ey + 24, "auto-opened curve below taller rails");
        h.eq("mem[exp_assign_addr(" + std::to_string(int(ti)) + ")]", 1,
             "popup assigns exact parameter");
        h.frame(200, ey, 1);
        h.frame();
        h.eq("exp_editor_ti", ti, "assigned click opens exact curve");
        check(h.val("cy") > ey + 20, "curve below shared sliders");
        h.frame(920, int(h.val("exp_y")) + 15, 1);
        h.frame();
        h.eq("exp_editor_ti", -1, "close curve");
      }
  }
  h.run("transform_add(0,1);mem[INST_TRANSFORM_TYPE_BASE]=-1;transform_add(0,1)"
        ";");
  h.eq("mem[INST_TRANSFORM_COUNT_BASE]", 6,
       "bypassed transformer cannot duplicate identity");
  h.run("mem[INST_TRANSFORM_TYPE_BASE]=1;");
  // UI-assigned legacy ARP enable remains separate from HOLD.
  h.run("selected_transform_gi=0;selected_transform_slot=4;ui_scroll=0;");
  h.frame();
  int header_y = int(h.val("exp_y")) - 216 + 35;
  h.frame(520, header_y, 2);
  h.frame();
  h.eq("controller_assign_ti", h.eval("param_ti(0,EXP_T_ARP_ON)"),
       "ARP enable right click");
  int header_ax = int(h.val("ax")), header_ay = int(h.val("ay"));
  h.frame(header_ax + 10, header_ay + 35, 1);
  h.frame();
  h.eq("mem[exp_assign_addr(param_ti(0,EXP_T_ARP_ON))]", 1,
       "ARP enable can be assigned independently");
  auto before = h.payload();
  for (int gi = 0; gi < 3; gi++)
    for (int slot = 0; slot < 6; slot++) {
      h.run("ui_scroll=200;");
      h.frame();
      int y = 190 + 6 * 38 + 18 + 30 + gi * 124 + 72 - 200;
      h.frame(54 + slot * 150 + 40, y, 1);
      h.frame();
      h.eq("selected_transform_gi", gi, "block click selects instrument");
      h.eq("selected_transform_slot", slot, "block click selects slot");
    }
  check(h.payload() == before,
        "selection and scrolled redraw leave persistent payload unchanged");
  h.run("ui_scroll=200;selected_transform_gi=0;selected_transform_slot=0;");
  h.frame();
  int ey = int(h.val("exp_y")) - 216 + 60 - 200;
  h.frame(200, ey, 2);
  h.frame();
  check(h.val("controller_assign_ti") >= 0, "scrolled hit test");
  h.frame(60, 100, 1);
  h.frame();
  h.eq("controller_assign_ti", -1, "outside click dismisses popup");
  check(h.payload() == before, "popup dismissal consumes click");
  h.run("ui_scroll=0;selected_transform_slot=0;");
  h.frame();
  ey = int(h.val("exp_y")) - 216 + 60;
  h.frame(200, ey, 2);
  h.frame();
  int ax = int(h.val("ax")), ay = int(h.val("ay"));
  h.frame(ax + 10, ay + 10, 1);
  h.frame();
  h.eq("mem[exp_assign_addr(param_ti(0,PARAM_TRANSPOSE))]", 0,
       "NONE removes assignment");
  h.frame(399, ey, 1);
  h.block();
  h.frame();
  h.eq("mem[INST_TRANSPOSE_BASE]", 48, "manual control after NONE");
}
static void musical(Host &h) {
  configure(h);
  h.run("param_extension_reset();param_runtime_reset();i=0;loop(EXP_TOTAL,mem["
        "INST_EXP_ASSIGN_BASE+i]=0;i+=1;);mem[INST_TRANSPOSE_BASE]=0;mem[INST_"
        "RANGE_MODE_BASE]=0;mem[INST_NOTE_MODE_BASE]=0;mem[INST_ARP_ENABLED_"
        "BASE]=0;mem[INST_VEL_BASE]=1;state=STATE_IDLE;panic_pending=0;");
  h.block();
  h.events();
  h.midi(0x90, 60, 100);
  auto e = h.events();
  check(e.size() == 1 && e[0][0] == 0x90 && e[0][1] == 60, "original note on");
  h.run(
      "ti=param_ti(0,PARAM_TRANSPOSE);mem[exp_assign_addr(ti)]=1;ctrl_val0=1;");
  h.block();
  h.eq("mem[INST_TRANSPOSE_BASE]", 0, "held note defers transpose");
  check(h.events().empty(), "modulation produces no panic burst");
  h.midi(0x80, 60, 0);
  e = h.events();
  check(e.size() == 1 && e[0][1] == 60 && e[0][0] == 0x80,
        "matching original note off");
  h.block();
  h.eq("mem[INST_TRANSPOSE_BASE]", 48, "transpose applies after release");
  h.midi(0x90, 60, 90);
  e = h.events();
  check(e.size() == 1 && e[0][1] == 108, "next note uses new transpose");
  h.midi(0x80, 60, 0);
  e = h.events();
  check(e.size() == 1 && e[0][1] == 108, "new transpose matching note off");
  h.run("mem[exp_assign_addr(param_ti(0,PARAM_TRANSPOSE))]=0;mem[INST_"
        "TRANSPOSE_BASE]=0;mem[INST_RANGE_MODE_BASE]=3;mem[INST_RANGE_LOW_BASE]"
        "=0;mem[INST_RANGE_HIGH_BASE]=127;");
  h.midi(0x90, 60, 90);
  h.events();
  h.run("mem[PARAM_PENDING_BASE+param_ti(0,PARAM_RANGE_LOW)]=100;");
  h.block();
  h.eq("mem[INST_RANGE_LOW_BASE]", 0, "held note defers filter");
  h.events();
  h.midi(0x80, 60, 0);
  e = h.events();
  check(e.size() == 1 && e[0][1] == 60, "filter retains original note off");
  h.block();
  h.eq("mem[INST_RANGE_LOW_BASE]", 100, "filter applies after release");
  h.midi(0x90, 60, 90);
  check(h.events().empty(), "new notes filtered");
  h.midi(0x80, 60, 0);
  check(h.events().empty(), "filtered note off filtered");
  h.run("mem[PARAM_PENDING_BASE+param_ti(0,PARAM_MOD_CC)]=64;mem[PARAM_PENDING_"
        "BASE+param_ti(0,EXP_T_MOD)]=127;");
  h.block();
  e = h.events();
  check(e.size() == 1 && e[0][1] == 64 && e[0][2] == 127,
        "modulation uses assigned CC destination");
  h.block();
  check(h.events().empty(), "unchanged CC not flooded");
  h.run("mem[PARAM_PENDING_BASE+param_ti(0,PARAM_MOD_CC)]=1;");
  h.block();
  e = h.events();
  check(e.size() == 2 && e[0][1] == 64 && e[0][2] == 0 && e[1][1] == 1,
        "leaving sustain destination releases CC64 once");
  h.run("mem[INST_RANGE_MODE_BASE]=0;mem[INST_NOTE_MODE_BASE]=0;");
  h.midi(0x90, 60, 90);
  h.events();
  h.run("mem[PARAM_PENDING_BASE+param_ti(0,PARAM_NOTE_MODE)]=1;");
  h.block();
  h.events();
  h.eq("mem[INST_NOTE_MODE_BASE]", 0, "held note defers polyphony mode");
  h.midi(0x80, 60, 0);
  e = h.events();
  check(e.size() == 1 && e[0][1] == 60, "polyphony change preserves note off");
  h.block();
  h.eq("mem[INST_NOTE_MODE_BASE]", 1, "polyphony updates after release");
  h.run("mem[INST_NOTE_MODE_BASE]=0;mem[INST_TRANSFORM_TYPE_BASE+5]=-6;mem["
        "PARAM_PENDING_BASE+param_ti(0,EXP_T_MOD)]=77;");
  h.block();
  check(h.events().empty(), "CC transformer bypass suppresses output");
  h.run("mem[INST_TRANSFORM_TYPE_BASE+5]=6;");
  h.block();
  e = h.events();
  check(e.size() == 1 && e[0][1] == 1 && e[0][2] == 77,
        "CC reenable sends latest value once");
  h.run("mem[CONTROLLER_CC_BASE+3]=11;");
  h.midi(176, 11, 95);
  h.events();
  h.eq("ctrl_val3", 95.0 / 127, "fourth controller receives mapped MIDI CC");
  h.run("mem[INST_RANGE_MODE_BASE]=0;mem[INST_ARP_ENABLED_BASE]=1;mem[INST_ARP_"
        "HOLD_BASE]=1;mem[INST_ARP_MODE_BASE]=1;mem[INST_ARP_RATE_BASE]=16;mem["
        "INST_ARP_GATE_BASE]=.5;");
  h.midi(0x90, 60, 90);
  e = h.events();
  bool arp_note = false;
  for (auto m : e)
    if (m[0] == 144 && m[1] == 60)
      arp_note = true;
  check(arp_note, "running ARP emits note");
  h.midi(0x80, 60, 0);
  h.events();
  h.eq("mem[ARP_HELD_COUNT_BASE+60]", 1, "ARP HOLD latches source note");
  h.run("mem[PARAM_PENDING_BASE+param_ti(0,PARAM_ARP_HOLD)]=0;mem[PARAM_"
        "PENDING_BASE+param_ti(0,EXP_T_ARP_RATE)]=8;mem[PARAM_PENDING_BASE+"
        "param_ti(0,EXP_T_ARP_GATE)]=.25;");
  h.block();
  h.events();
  h.eq("mem[ARP_HELD_COUNT_BASE+60]", 0, "HOLD OFF removes released latch");
  h.eq("mem[ARP_ACTIVE_NOTE_BASE]", -1, "latch release stops ARP note");
  h.eq("mem[INST_ARP_ENABLED_BASE]", 1, "HOLD OFF preserves ARP enabled");
  h.eq("mem[INST_ARP_RATE_BASE]", 8, "live ARP rate updates");
  h.eq("mem[INST_ARP_GATE_BASE]", .25, "live ARP gate updates");
  h.run("mem[INST_ARP_ENABLED_BASE]=0;");
  // Existing recording/overdub/once paths remain exercised by real incoming
  // MIDI.
  h.run("mem[INST_RANGE_MODE_BASE]=0;record_layer=0;state=STATE_READY;mem["
        "COUNT_BASE]=0;");
  h.midi(0x90, 64, 88);
  h.events();
  h.midi(0x80, 64, 0);
  h.events();
  h.eq("mem[COUNT_BASE]", 2, "record phrase note on/off");
  h.eq("mem[1]", 144, "recorded status intact");
  h.eq("mem[2]", 64, "recorded note intact");
  h.run("mem[LEN_BASE]=256;state=STATE_STOPPED;trigger_request=0;");
  h.block();
  e = h.events();
  bool note = false;
  for (auto m : e)
    if (m[0] == 144 && m[1] == 64)
      note = true;
  check(note, "one-shot phrase plays recorded note");
  h.block();
  h.events();
  h.eq("mem[COUNT_BASE]", 2, "one-shot preserves phrase material");
  h.run("overdub_layer=0;overdub_active=1;overdub_pos=0;mem[MODE_BASE]=1;mem["
        "LEN_BASE]=1024;");
  h.midi(0x90, 67, 90);
  h.events();
  h.midi(0x80, 67, 0);
  h.events();
  h.eq("mem[COUNT_BASE]", 4, "overdub appends note pair");
  h.eq("mem[2]", 64, "overdub preserves original phrase");
  h.run(
      "overdub_active=0;overdub_armed=0;mem[MODE_BASE]=0;mem[TRIG_BASE]=1;"
      "state=STATE_PLAYING;loop_len_samples=256;play_sample_pos=0;slider5=0;");
  h.block();
  e = h.events();
  bool loop_note = false;
  for (auto m : e)
    if (m[0] == 144 && m[1] == 64)
      loop_note = true;
  check(loop_note, "LOOP plays recorded phrase");
  h.block();
  h.events();
  h.eq("play_sample_pos", 0, "LOOP wraps at phrase boundary");
  h.eq("mem[COUNT_BASE]", 4, "LOOP preserves overdub data");
}
static std::vector<uint8_t> rail_pixels(Host &h, int x, int y, int w,
                                        int height) {
  std::vector<uint8_t> out;
  for (int yy = y; yy < y + height; ++yy)
    for (int xx = x; xx < x + w; ++xx)
      for (int c = 0; c < 3; ++c)
        out.push_back(h.pixels[(yy * 1040 + xx) * 4 + c]);
  return out;
}
static bool preview_pixel(Host &h, int x, double y) {
  for (int yy = int(y) - 1; yy <= int(y) + 1; ++yy) {
    size_t i = (yy * 1040 + x) * 4;
    if (h.pixels[i] > 80 && h.pixels[i + 1] > 170 && h.pixels[i + 2] > 180)
      return true;
  }
  return false;
}
static void editor_ux(Host &h) {
  configure(h);
  h.run("selected_transform_gi=0;selected_transform_slot=0;ui_scroll=0;exp_"
        "editor_ti=-1;");
  h.frame();
  int top = int(h.val("exp_y")) - 216;
  // Test the actual rendered empty rail against VOLUME, including its bottom
  // edge.
  auto volume = rail_pixels(h, 550, 190 + 6 * 38 + 18 + 30 + 19, 1, 19);
  auto editor = rail_pixels(h, 390, top + 62, 1, 19);
  auto flat_height = [](const std::vector<uint8_t> &column) {
    int height = 1;
    while (height < 19 && column[height * 3] == column[0] &&
           column[height * 3 + 1] == column[1] &&
           column[height * 3 + 2] == column[2])
      ++height;
    return height;
  };
  check(flat_height(volume) == 18 && flat_height(editor) == 18,
        "editor rail matches VOLUME's 18px height and proportions");
  int rows[] = {1, 3, 1, 1, 4, 2};
  for (int slot = 0; slot < 6; ++slot)
    for (int row = 0; row < rows[slot]; ++row) {
      h.run("selected_transform_slot=" + std::to_string(slot) +
            ";exp_editor_ti=-1;");
      std::string ti = "param_ti(0,param_editor_kind(" +
                       std::to_string(slot + 1) + "," + std::to_string(row) +
                       "))";
      h.run("mem[exp_assign_addr(" + ti + ")]=1;curve_factory(" + ti + ",0);");
      h.frame();
      int ey = top + 60 + row * 34;
      check(preview_pixel(h, 260, ey + 11),
            "every assigned transformer rail draws its own flat curve");
      check(ey + 20 < top + 205, "last rail remains inside editor panel");
      auto flat = rail_pixels(h, 125, ey + 2, 275, 18);
      auto gap = rail_pixels(h, 125, ey + 20, 275, 14);
      h.run("curve_factory(" + ti + ",1);");
      h.frame();
      check(rail_pixels(h, 125, ey + 2, 275, 18) != flat,
            "multipoint edits update inline preview");
      for (int x : {150, 262, 375}) {
        double position = (x - 127) / 271.0;
        double value = position <= 1.0 / 3   ? 0
                       : position >= 2.0 / 3 ? .8
                                             : (position - 1.0 / 3) * 2.4;
        check(preview_pixel(h, x, ey + 18 - 14 * value),
              "preview follows multipoint interpolation in rail coordinates");
      }
      check(rail_pixels(h, 125, ey + 20, 275, 14) == gap,
            "preview does not paint into row gap");
      h.run("curve_factory(" + ti + ",3);mem[exp_bend_addr(" + ti + ")]=.5;");
      h.frame();
      auto positive = rail_pixels(h, 125, ey + 2, 275, 18);
      check(preview_pixel(h, 262, ey + 18 - 14 * std::pow(135.0 / 271, 3.5)),
            "preview follows positive bend");
      h.run("mem[exp_bend_addr(" + ti + ")]=-.5;");
      h.frame();
      check(rail_pixels(h, 125, ey + 2, 275, 18) != positive,
            "bend edits refresh preview without reselection");
      check(preview_pixel(h, 262,
                          ey + 18 - 14 * (1 - std::pow(136.0 / 271, 3.5))),
            "preview follows negative bend");
      h.run("mem[exp_assign_addr(" + ti + ")]=0;");
      h.frame();
      auto manual = rail_pixels(h, 125, ey + 2, 275, 18);
      h.run("curve_factory(" + ti + ",0);");
      h.frame();
      check(rail_pixels(h, 125, ey + 2, 275, 18) == manual,
            "unassigned rails do not render curves");
      // Expanded bottom hitbox reaches this row, never its neighbor.
      h.frame(200, ey + 22, 2);
      h.frame();
      h.eq("controller_assign_ti", h.eval(ti),
           "taller rail bottom hitbox selects correct row");
      h.frame(int(h.val("ax")) + 10, int(h.val("ay")) + 35, 1);
      h.eq("exp_editor_ti", h.eval(ti),
           "popup opens curve before another click");
      h.frame();
      h.frame(200, ey, 2);
      h.frame();
      h.frame(int(h.val("ax")) + 10, int(h.val("ay")) + 10, 1);
      h.frame();
      h.eq("exp_editor_ti", -1,
           "NONE closes this parameter's auto-opened curve");
    }
  // NONE on a different parameter must not close the current curve.
  h.run("selected_transform_slot=1;exp_editor_ti=param_ti(0,PARAM_TRANSPOSE);");
  h.frame();
  h.frame(200, top + 60, 2);
  h.frame();
  h.frame(int(h.val("ax")) + 10, int(h.val("ay")) + 10, 1);
  h.frame();
  h.eq("exp_editor_ti", h.eval("param_ti(0,PARAM_TRANSPOSE)"),
       "NONE preserves unrelated curve editor");
  h.run("exp_editor_ti=-1;selected_transform_gi=0;selected_transform_slot=1;"
        "mem[exp_assign_addr(param_ti(0,PARAM_RANGE_MODE))]=1;curve_factory("
        "param_ti(0,PARAM_RANGE_MODE),0);mem[exp_assign_addr(param_ti(0,PARAM_"
        "RANGE_LOW))]=1;curve_factory(param_ti(0,PARAM_RANGE_LOW),3);");
  h.frame();
  auto first = rail_pixels(h, 125, top + 62, 275, 18);
  auto second = rail_pixels(h, 125, top + 96, 275, 18);
  h.run("mem[exp_bend_addr(param_ti(0,PARAM_RANGE_LOW))]=.8;");
  h.frame();
  check(rail_pixels(h, 125, top + 96, 275, 18) != second,
        "second parameter updates its independent preview");
  check(rail_pixels(h, 125, top + 62, 275, 18) == first,
        "same-controller curves remain independent across rows");
  h.run("mem[INST_TRANSFORM_COUNT_BASE+1]=1;mem[INST_TRANSFORM_TYPE_BASE+6]=2;"
        "mem[exp_assign_addr(param_ti(1,PARAM_RANGE_MODE))]=1;curve_factory("
        "param_ti(1,PARAM_RANGE_MODE),3);selected_transform_gi=1;selected_"
        "transform_slot=0;");
  h.frame();
  check(rail_pixels(h, 125, top + 62, 275, 18) != first,
        "different instrument shows its own curve");
  h.run("selected_transform_gi=0;selected_transform_slot=1;");
  h.frame();
  check(rail_pixels(h, 125, top + 62, 275, 18) == first,
        "switching instruments preserves preview identity");
  auto before = h.payload();
  h.frame();
  h.frame();
  check(h.payload() == before, "preview redraws do not modify patch data");
}
static void stress(Host &h, bool historical) {
  configure(h);
  h.run("selected_transform_gi=0;selected_transform_slot=3;exp_editor_ti=0;ui_"
        "scroll=0;i=0;loop(EXP_TOTAL,mem[INST_EXP_ASSIGN_BASE+i]=1;mem[INST_"
        "EXP_Y_BASE+i*EXP_POINTS]=i/"
        "EXP_TOTAL;mem[INST_EXP_Y_BASE+i*EXP_POINTS+1]=1-i/"
        "EXP_TOTAL;i+=1;);ctrl_val0=.5;state=STATE_IDLE;panic_pending=0;");
  h.block();
  h.frame();
  std::atomic<bool> stop{false};
  std::thread dsp([&] {
    uint8_t bytes[] = {0xB0, 119, 0};
    ysfx_midi_event_t event{};
    event.size = 3;
    event.data = bytes;
    while (!stop) {
      ysfx_send_midi(h.f, &event);
      h.block();
    }
  });
  std::set<uint64_t> hashes;
  for (int i = 0; i < 200; i++) {
    h.frame();
    hashes.insert(h.hash());
  }
  stop = true;
  dsp.join();
  printf("concurrent fixed-state frames: %zu distinct hashes\n", hashes.size());
  if (!historical)
    check(hashes.size() == 1, "concurrent audio/GFX render is stable");
}
#include "smart_switch_cases.hpp"
int main(int argc, char **argv) {
  if (argc < 2)
    return 2;
  Host h(argv[1]);
  if (argc > 2 && (std::string(argv[2]) == "--historical" ||
                   std::string(argv[2]) == "--isolated")) {
    stress(h, std::string(argv[2]) == "--historical");
    return 0;
  }
  assignment(h);
  persistence(h, argv[2]);
  gui(h);
  musical(h);
  Host ux(argv[1]);
  editor_ux(ux);
  Host smart(argv[1]);
  smart_switch_tests(smart);
  Host stable(argv[1]);
  stress(stable, false);
  printf("PASS: %d EEL2/GUI/MIDI checks\n", checks);
}
