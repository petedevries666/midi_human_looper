struct TimedMidi {
  int sample, st, note, value;
};
static std::vector<TimedMidi> timed_events(Host &h, int start) {
  std::vector<TimedMidi> events;
  ysfx_midi_event_t e{};
  while (ysfx_receive_midi(h.f, &e))
    if (e.size == 3)
      events.push_back(
          {start + int(e.offset), e.data[0], e.data[1], e.data[2]});
  return events;
}
static std::vector<TimedMidi> time_pass(Host &h, double factor) {
  h.run("trigger_request=0;");
  h.block();
  auto events = timed_events(h, 0);
  int blocks = int(std::ceil(h.val("srate") * .26 * factor / 128)) + 1;
  for (int i = 1; i < blocks; i++) {
    h.block();
    auto next = timed_events(h, i * 128);
    events.insert(events.end(), next.begin(), next.end());
  }
  return events;
}
static void check_time_pass(Host &h, double factor, int velocity) {
  auto events = time_pass(h, factor);
  int ons = 0, offs = 0, ccs = 0;
  for (auto e : events) {
    if (e.st == 144) {
      check(e.note >= 60 && e.note <= 63, "time playback keeps note identity");
      check(std::abs(e.sample -
                     h.val("srate") * .05 * (e.note - 60) * factor) <= 1,
            "staggered chord onset scales original offset");
      check(e.value == velocity, "TIME and VEL decay remain independent");
      ons++;
    } else if (e.st == 128) {
      check(std::abs(e.sample - h.val("srate") * (.05 * (e.note - 60) + .02) *
                                    factor) <= 1,
            "note duration/off scales with onset");
      offs++;
    } else if (e.st == 176 && e.note == 74) {
      check(std::abs(e.sample - h.val("srate") * .075 * factor) <= 1,
            "timestamped CC scales consistently");
      ccs++;
    }
  }
  check(ons == 4 && offs == 4 && ccs == 1,
        "all scaled MIDI events emitted once");
}
static void time_decay_tests(Host &h) {
  h.run("sw_defaults();sw_runtime_reset();panic_pending=0;state=STATE_STOPPED;"
        "slider9=1;"
        "mem[INST_ENABLED_BASE]=1;mem[INST_ENABLED_BASE+1]=0;mem[INST_ENABLED_"
        "BASE+2]=0;mem[INST_TRANSFORM_COUNT_BASE]=0;"
        "mem[COUNT_BASE]=0;mem[MODE_BASE]=1;mem[VEL_BASE]=1;mem[DECAY_BASE]=.8;"
        "mem[LEN_BASE]=srate*10;"
        "i=0;loop(4,store_event(0,srate*.05*i,144,60+i,100,0);store_event(0,"
        "srate*(.05*i+.02),128,60+i,0,0);i+=1;);"
        "store_event(0,srate*.075,176,74,64,0);mem[phrase_time_addr(0)]=1.2;");
  h.eq("phrase_time_ratio(1)", 1, "other phrase TIME defaults neutral");
  check_time_pass(h, 1, 100);
  check_time_pass(h, 1.2, 80);
  check_time_pass(h, 1.44, 64);
  h.eq("mem[layer_base(0,2)]", h.val("srate") * .05,
       "TIME playback never rewrites recorded offsets");
  h.run("mem[COUNT_BASE+1]=0;store_event(1,0,144,80,100,0);store_event(1,20,"
        "128,80,0,0);mem[LEN_BASE+1]=64;mem[MODE_BASE+1]=1;trigger_request=1;");
  h.block();
  h.events();
  h.eq("mem[REPEAT_BASE]", 0,
       "changing phrase resets shared retrigger counter");
  check_time_pass(h, 1, 100);
  h.run(
      "mem[phrase_time_addr(0)]=.8;last_trigger_layer=-1;mem[REPEAT_BASE]=0;");
  check_time_pass(h, 1, 100);
  check_time_pass(h, .8, 80);
  check_time_pass(h, .64, 64);
  h.run("mem[phrase_time_addr(0)]=1;last_trigger_layer=-1;");
  check_time_pass(h, 1, 100);
  check_time_pass(h, 1, 80);
  h.run("sw_stop_phrases();mem[LEN_BASE]=srate*.25;mem[phrase_time_addr(0)]=1."
        "2;");
  check_time_pass(h, 1, 100);
  check_time_pass(h, 1, 100);
  h.eq("last_trigger_layer", -1,
       "natural ONCE completion resets history exactly like VEL decay");
  h.run("sw_stop_phrases();mem[LEN_BASE]=srate*10;");
  // A per-voice snapshot remains stable when another retrigger or UI edit
  // occurs.
  h.run(
      "mem[phrase_time_addr(0)]=1.2;last_trigger_layer=-1;trigger_request=0;");
  h.block();
  h.events();
  h.eq("mem[VOICE_TIME_BASE]", 1, "first overlapping voice has neutral factor");
  h.run("trigger_request=0;");
  h.block();
  h.events();
  h.eq("mem[VOICE_TIME_BASE+1]", 1.2,
       "second overlapping voice snapshots its own factor");
  h.eq("mem[VOICE_TIME_BASE]", 1, "retrigger cannot retime older voice");
  h.run("mem[phrase_time_addr(0)]=2;");
  h.block();
  h.events();
  h.eq("mem[VOICE_TIME_BASE+1]", 1.2,
       "live slider edit cannot retime active voice");
  h.run("mem[sw_cfg(0)]=1;mem[sw_cfg(0)+14]=SW_STOP;sw_submit(0,0,0,0);");
  h.block();
  h.events();
  h.eq("mem[VOICE_ACTIVE_BASE]+mem[VOICE_ACTIVE_BASE+1]", 0,
       "STOP cancels overlapping timed voices");
  for (int i = 0; i < 80; i++) {
    h.block();
    check(h.events().empty(), "STOP leaves no delayed attacks");
  }
  h.run("last_trigger_layer=-1;trigger_request=0;");
  h.block();
  h.events();
  h.run("mem[sw_cfg(0)+14]=SW_PANIC;sw_submit(0,0,0,0);");
  h.block();
  h.events();
  for (int i = 0; i < 80; i++) {
    h.block();
    check(h.events().empty(), "PANIC leaves no delayed attacks");
  }
  h.run("mem[REPEAT_BASE]=1000000000;mem[phrase_time_addr(0)]=2;");
  h.eq("phrase_time_factor(0)", 64, "slow growth capped before exponentiation");
  h.run("mem[phrase_time_addr(0)]=.5;");
  h.eq("phrase_time_factor(0)", 1.0 / 64, "fast compression safely capped");
  h.run("mem[phrase_time_addr(0)]=1.2;mem[phrase_time_addr(1)]=.8;external_"
        "patch_save_request(1);sw_defaults();external_patch_apply();");
  h.eq("phrase_time_ratio(0)", 1.2, "patch restores slow phrase TIME ratio");
  h.eq("phrase_time_ratio(1)", .8,
       "patch restores independent fast phrase TIME ratio");
  h.run("save_patch(1);sw_defaults();current_patch=2;load_patch(1);");
  h.eq("phrase_time_ratio(0)", 1.2, "internal bank restores TIME ratio");
  h.eq("phrase_time_ratio(1)", .8,
       "internal bank preserves independent TIME ratio");
  h.run("sw_submit(0,3,6,0);sw_queue_process();mem[phrase_time_addr(0)]=1.5;sw_"
        "submit(0,7,0,0);sw_queue_process();");
  h.eq("phrase_time_ratio(0)", 1.5,
       "switch-list UNDO cannot revert independent phrase TIME settings");
  h.run("gmem[2]=2;gmem[3]=SW_LEGACY_PAYLOAD;external_patch_apply();");
  h.eq("phrase_time_ratio(0)", 1, "schema2 patch migrates TIME to neutral");
  h.run("sw_defaults();mem[sw_cfg(0)+112]=0;sw_validate();");
  h.eq("phrase_time_ratio(0)", 1,
       "older schema3 reserved zero migrates to neutral");
  h.run("mem[phrase_time_addr(0)]=1.2;mem[REPEAT_BASE]=5;clear_layer(0);");
  h.eq("mem[REPEAT_BASE]", 0,
       "clear uses existing velocity-decay counter reset");
  h.eq("phrase_time_ratio(0)", 1.2,
       "clear preserves ratio just like VEL decay setting");
  h.run("mem[COUNT_BASE]=0;store_event(0,0,144,60,90,0);mem[LEN_BASE]=1000;mem["
        "phrase_time_addr(1)]=.8;ui_"
        "scroll=0;");
  click(h, 430, 219);
  h.frame(430, 219, 1);
  h.frame(430, 219, 0);
  h.block();
  h.events();
  h.eq("phrase_time_ratio(0)", 1, "double-click TIME rail resets to unity");
  h.eq("phrase_time_ratio(1)", .8,
       "TIME rail reset does not affect another phrase");
  h.run("ui_td_last_click=0;");
  click(h, 401, 219);
  h.eq("phrase_time_ratio(0)", 1, "TIME center pixel selects exact unity");
  h.run("ui_td_last_click=0;");
  click(h, 369, 219);
  h.eq("phrase_time_ratio(0)", .5,
       "TIME left endpoint selects exact faster limit");
  h.run("ui_td_last_click=0;");
  click(h, 433, 219);
  h.eq("phrase_time_ratio(0)", 2,
       "TIME right endpoint selects exact slower limit");
  h.eq("VOICE_TIME_BASE+MAX_ONCE_VOICES<8388608", 1,
       "timing snapshots remain inside EEL2 RAM ceiling");
}
