// Complete JSFX host coverage for the Smart Switch control layers.
static void smart_switch_tests(Host &h) {
  h.run("sw_defaults();sw_runtime_reset();panic_pending=0;state=STATE_IDLE;"
        "mem[INST_ENABLED_BASE]=1;mem[INST_ENABLED_BASE+1]=0;mem[INST_ENABLED_"
        "BASE+2]=0;"
        "mem[INST_IN_BASE]=0;mem[INST_OUT_BASE]=0;mem[INST_TRANSFORM_COUNT_"
        "BASE]=0;");
  h.block();
  h.events();
  h.eq("mem[sw_cfg(0)+5]", 0, "command THRU defaults off");
  h.eq("mem[sw_cfg(0)+7]", 300, "double threshold default");
  h.eq("mem[sw_cfg(0)+8]", 800, "hold threshold default");
  h.run("sw_assign(0,1,2,60,127,0);mem[sw_cfg(0)]=1;mem[sw_cfg(0)+14]=SW_RESET_"
        "ALL;");
  h.midi(0x92, 60, 1);
  check(h.events().empty(), "velocity 1 command is silent");
  h.eq("mem[sw_rt(0)+12]", 1, "normal press executes once");
  h.midi(0x92, 60, 127);
  h.events();
  h.eq("mem[sw_rt(0)+12]", 1, "repeated on ignored");
  h.midi(0x82, 60, 64);
  check(h.events().empty(), "note off silent");
  h.eq("mem[sw_rt(0)+12]", 1, "release does not retrigger");
  h.midi(0x91, 60, 90);
  check(!h.events().empty(), "channel mismatch remains normal MIDI");
  h.midi(0x81, 60, 0);
  h.events();
  h.run("mem[sw_cfg(0)+5]=1;");
  h.midi(0x92, 60, 90);
  auto e = h.events();
  check(e.size() == 1 && e[0][0] == 0x92,
        "explicit THRU forwards command once");
  h.midi(0x92, 60, 0);
  e = h.events();
  check(e.size() == 1 && e[0][2] == 0, "velocity zero is release with THRU");
  h.eq("sw_assign(1,1,2,60,127,0)", 0, "duplicate assignment rejected");
  h.eq("sw_assign(1,2,2,4,127,127)", 0, "CC requires distinct release");
  h.run("sw_learn=1;");
  h.midi(0xB3, 12, 100);
  check(h.events().empty(), "learn press consumed");
  h.eq("mem[sw_cfg(1)+2]", 2, "learn CC kind");
  h.eq("mem[sw_cfg(1)+3]", 3, "learn exact channel");
  h.eq("mem[sw_cfg(1)+12]", 100, "learn CC press value");
  h.midi(0xB3, 12, 0);
  check(h.events().empty(), "learn release consumed without action");
  h.eq("mem[sw_rt(1)+12]", 0, "learning does not execute action");
  h.run("mem[sw_cfg(1)+14]=SW_RESET_ALL;");
  h.midi(0xB3, 12, 40);
  h.events();
  h.eq("mem[sw_rt(1)+12]", 0, "intermediate CC value ignored");
  h.midi(0xB3, 12, 100);
  h.events();
  h.midi(0xB3, 12, 100);
  h.events();
  h.eq("mem[sw_rt(1)+12]", 1, "CC repeats ignored");
  h.midi(0xB3, 12, 0);
  h.events();
  // Use sample-clock edge events for deterministic boundaries, then actual
  // blocks above.
  h.run("sw_runtime_reset();mem[sw_cfg(0)+5]=0;mem[sw_cfg(0)+6]=1;"
        "mem[sw_cfg(0)+15]=SW_STOP;mem[sw_cfg(0)+16]=SW_RESET;"
        "sw_edge(0,1,0,0);sw_edge(0,0,.05*srate,0);");
  h.eq("mem[sw_rt(0)+12]", 0, "exclusive tap waits for double window");
  h.run("sw_edge(0,1,.1*srate,0);sw_edge(0,0,.15*srate,0);sw_poll(srate,0);");
  h.eq("mem[sw_rt(0)+12]", 1, "exclusive double one action");
  h.eq("mem[sw_rt(0)+11]", 2, "double action selected");
  h.run("sw_runtime_reset();sw_edge(0,1,0,0);sw_poll(.81*srate,0);sw_edge(0,0,."
        "9*srate,0);sw_poll(2*srate,0);");
  h.eq("mem[sw_rt(0)+12]", 1, "hold excludes delayed tap/double");
  h.eq("mem[sw_rt(0)+11]", 3, "hold action selected");
  h.run("sw_runtime_reset();sw_edge(0,1,0,0);sw_edge(0,0,.05*srate,0);sw_poll(."
        "36*srate,0);");
  h.eq("mem[sw_rt(0)+12]", 1, "exclusive single fires after window");
  h.run("sw_runtime_reset();mem[sw_cfg(0)+6]=0;sw_edge(0,1,0,0);sw_poll(.81*"
        "srate,0);sw_edge(0,0,.9*srate,0);");
  h.eq("mem[sw_rt(0)+12]", 2, "instant tap plus hold");
  h.run("sw_runtime_reset();mem[sw_cfg(0)+6]=1;mem[sw_cfg(0)+15]=0;mem[sw_cfg("
        "0)+16]=0;sw_edge(0,1,0,0);");
  h.eq("mem[sw_rt(0)+12]", 1, "disabled gestures introduce no latency");
  h.run("sw_poll(11*srate,0);");
  h.eq("mem[sw_rt(0)]", 0, "missing release watchdog unlocks");
  h.eq("mem[sw_rt(0)+17]", 3, "watchdog visible status");
  // Real recorded-phrase playback through a silent momentary command.
  h.run("sw_defaults();sw_runtime_reset();state=STATE_STOPPED;last_trigger_"
        "layer=-1;"
        "sw_assign(0,1,0,72,127,0);mem[sw_cfg(0)]=1;mem[sw_cfg(0)+11]=2;"
        "mem[sw_cfg(0)+SW_LIST]=0;mem[sw_cfg(0)+SW_LIST+1]=6;"
        "mem[COUNT_BASE]=0;store_event(0,0,144,50,90,0);store_event(0,500,128,"
        "50,0,0);"
        "mem[LEN_BASE]=1000;mem[MODE_BASE]=1;mem[COUNT_BASE+6]=0;"
        "store_event(6,0,144,56,90,0);store_event(6,500,128,56,0,0);mem[LEN_"
        "BASE+6]=1000;mem[MODE_BASE+6]=1;");
  h.midi(0x90, 72, 5);
  e = h.events();
  int phrase_ons = 0, commands = 0;
  for (auto m : e) {
    if (m[0] == 144 && m[1] == 50)
      phrase_ons++;
    if (m[1] == 72)
      commands++;
  }
  check(phrase_ons == 1 && commands == 0,
        "momentary note plays exactly one existing phrase silently");
  h.midi(0x80, 72, 0);
  h.events();
  h.eq("mem[sw_rt(0)+7]", 0, "release does not advance phrase position");
  h.midi(0x90, 72, 127);
  e = h.events();
  phrase_ons = 0;
  for (auto m : e)
    if (m[0] == 144 && m[1] == 56)
      phrase_ons++;
  check(phrase_ons == 1,
        "next tap routes nonconsecutive phrase to original playback engine");
  h.midi(0x80, 72, 0);
  h.events();
  h.run("mem[sw_cfg(0)+SW_LIST]=15;sw_reset(0);");
  h.midi(0x90, 72, 1);
  h.events();
  h.eq("mem[sw_rt(0)+17]", 2, "deleted or unavailable phrase reported safely");
  h.midi(0x80, 72, 0);
  h.events();
  h.run("sw_submit(0,2,14,SW_STOP);sw_queue_process();sw_submit(0,0,0,0);");
  h.block();
  h.events();
  h.run("sw_learn=1;");
  h.midi(0xB4, 9, 0);
  h.events();
  h.eq("mem[sw_cfg(1)+12]", 0, "learn inverted CC zero press");
  h.eq("mem[sw_cfg(1)+13]", 127, "inverted CC default release");
  h.midi(0xB4, 9, 127);
  h.events();
  h.run("sw_assign(2,1,0,73,127,0);mem[sw_cfg(2)]=1;mem[sw_cfg(2)+14]=SW_RESET_"
        "ALL;");
  h.midi(0x90, 73, 90);
  h.events();
  h.run("sw_defaults();sw_runtime_reset();");
  h.midi(0x80, 73, 0);
  check(h.events().empty(),
        "held command release quarantined across preset remap");
  // Ordered references, including duplicates and nonconsecutive IDs.
  h.run("sw_defaults();sw_runtime_reset();mem[sw_cfg(0)+11]=8;"
        "mem[sw_cfg(0)+SW_LIST]=0;mem[sw_cfg(0)+SW_LIST+1]=1;mem[sw_cfg(0)+SW_"
        "LIST+2]=0;"
        "mem[sw_cfg(0)+SW_LIST+3]=2;mem[sw_cfg(0)+SW_LIST+4]=3;mem[sw_cfg(0)+"
        "SW_LIST+5]=4;"
        "mem[sw_cfg(0)+SW_LIST+6]=0;mem[sw_cfg(0)+SW_LIST+7]=6;");
  int refs[] = {0, 1, 0, 2, 3, 4, 0, 6};
  for (int i = 0; i < 16; i++) {
    h.eq("sw_traverse(0)", i % 8, "forward step position");
    h.eq("mem[sw_rt(0)+10]", refs[i % 8], "exact ordered phrase reference");
  }
  h.run("mem[sw_cfg(0)+9]=1;sw_reset(0);");
  for (int i = 0; i < 10; i++)
    h.eq("sw_traverse(0)", 7 - i % 8, "backward wraps");
  h.run("mem[sw_cfg(0)+9]=2;mem[sw_cfg(0)+11]=3;sw_reset(0);");
  int ping[] = {0, 1, 2, 1, 0, 1, 2, 1};
  for (auto i : ping)
    h.eq("sw_traverse(0)", i, "ping pong without repeated endpoints");
  h.run("mem[sw_cfg(0)+9]=3;mem[sw_cfg(0)+11]=8;sw_reset(0);");
  int previous = -1;
  for (int bag = 0; bag < 20; bag++) {
    std::set<int> positions;
    int zero = 0;
    for (int i = 0; i < 8; i++) {
      int pos = h.eval("sw_traverse(0)");
      int phrase = h.eval("mem[sw_rt(0)+10]");
      positions.insert(pos);
      if (phrase == 0)
        zero++;
      if (i == 0 && bag > 0)
        check(phrase != previous, "shuffle boundary avoids same phrase");
      previous = phrase;
    }
    check(positions.size() == 8, "shuffle bag visits each position once");
    check(zero == 3, "shuffle preserves duplicate weighting");
  }
  h.run("mem[sw_cfg(0)+9]=0;mem[sw_cfg(1)+11]=3;sw_reset(0);sw_reset(1);sw_"
        "last_active=-1;sw_traverse(0);sw_traverse(0);sw_traverse(1);");
  h.eq("sw_traverse(0)", 2, "resume independent saved cursor");
  h.run("mem[sw_cfg(0)+10]=1;sw_traverse(1);");
  h.eq("sw_traverse(0)", 0, "restart on section reentry");
  h.eq("sw_traverse(0)", 1, "repeated active switch does not restart");
  h.run("mem[sw_cfg(0)+9]=1;sw_traverse(1);");
  h.eq("sw_traverse(0)", 0, "backward RESTART begins at first listed position");
  h.run("mem[sw_cfg(0)+9]=3;sw_traverse(1);");
  h.eq("sw_traverse(0)", 0, "shuffle RESTART begins at first listed position");
  h.run("mem[sw_cfg(0)+9]=0;sw_reset(0);sw_traverse(0);sw_traverse(0);");

  h.run("sw_action(2,SW_RESET,1,0);");
  h.eq("sw_last_active", 0, "special does not change section");
  h.eq("mem[sw_rt(1)+6]", -1, "target reset only requested switch");
  h.eq("mem[sw_rt(0)+6]", 1, "reset leaves other cursor");
  h.run("sw_submit(0,5,0,0);sw_queue_process();sw_submit(0,3,6,0);sw_queue_"
        "process();sw_submit(0,3,1,0);sw_queue_process();sw_submit(0,6,0,1);sw_"
        "queue_process();");
  h.eq("mem[sw_cfg(0)+SW_LIST]", 1, "reorder positions");
  h.run("sw_submit(0,7,0,0);sw_queue_process();");
  h.eq("mem[sw_cfg(0)+SW_LIST]", 6, "undo reorder");
  h.run("sw_submit(0,4,0,0);sw_queue_process();");
  h.eq("mem[sw_cfg(0)+11]", 1, "remove step");
  h.run("sw_submit(0,5,0,0);sw_queue_process();sw_submit(0,7,0,0);sw_queue_"
        "process();");
  h.eq("mem[sw_cfg(0)+11]", 1, "undo clear");
  h.run("sw_defaults();sw_runtime_reset();");
  for (int i = 0; i < 65; i++) {
    h.run("sw_submit(0,3," + std::to_string(i % 16) +
          ",0);sw_queue_process();");
  }
  h.eq("mem[sw_cfg(0)+11]", 64, "64 step capacity safely bounded");
  h.run("mem[sw_cfg(3)+11]=1;mem[sw_cfg(3)+SW_LIST]=6;");
  for (int mode = 0; mode < 4; mode++) {
    h.run("mem[sw_cfg(3)+9]=" + std::to_string(mode) + ";sw_reset(3);");
    for (int i = 0; i < 3; i++)
      h.eq("sw_traverse(3)", 0, "one-position traversal is safe");
  }
  h.run("mem[sw_cfg(3)+11]=0;sw_reset(3);");
  h.eq("sw_traverse(3)", -1, "empty traversal is safe");
  h.run("sw_queue_read=0;sw_queue_write=0;i=0;loop(SW_QUEUE_SIZE,sw_submit(3,2,"
        "5,0);i+=1;);");
  h.eq("sw_submit(3,2,5,1)", 0,
       "full GUI queue rejects without overwriting pending commands");
  h.run("sw_queue_process();");
  h.eq("mem[sw_cfg(3)+5]", 0, "queued payload remains intact");
  // Stable module identity, safe deferred changes, live/phrase ownership.
  h.run("mem[INST_TRANSFORM_COUNT_BASE]=2;mem[INST_TRANSFORM_TYPE_BASE]=4;mem["
        "INST_TRANSFORM_TYPE_BASE+1]=1;mem[INST_TRANSPOSE_BASE]=0;");
  h.midi(0x90, 65, 90);
  h.events();
  h.run("sw_action(0,SW_DISABLE,0,0);sw_queue_process();");
  h.eq("mem[INST_TRANSFORM_TYPE_BASE+1]", 1,
       "module disable deferred while source held");
  h.midi(0x80, 65, 0);
  h.events();
  h.block();
  h.events();
  h.eq("mem[INST_TRANSFORM_TYPE_BASE+1]", -1,
       "target type survives reordered chain");
  h.eq("mem[INST_TRANSFORM_TYPE_BASE]", 4, "untargeted module unchanged");
  h.run("sw_action(0,SW_ENABLE,0,0);sw_queue_process();");
  h.eq("mem[INST_TRANSFORM_TYPE_BASE+1]", 1, "module enabled");
  h.run("sw_action(0,SW_TOGGLE,0,0);sw_queue_process();");
  h.eq("mem[INST_TRANSFORM_TYPE_BASE+1]", -1, "module toggled");
  h.run("mem[INST_TRANSFORM_COUNT_BASE]=0;send_to_instruments(0,144,65,90,1);"
        "send_once_to_instruments(0,144,60,90,1);");
  h.block();
  h.events();
  h.run("mem[sw_cfg(0)]=1;mem[sw_cfg(0)+14]=SW_STOP;sw_submit(0,0,0,0);");
  h.block();
  e = h.events();
  bool phrase_off = false, live_off = false;
  for (auto m : e) {
    if (m[0] == 128 && m[1] == 60)
      phrase_off = true;
    if (m[0] == 128 && m[1] == 65)
      live_off = true;
  }
  check(phrase_off && !live_off,
        "STOP releases phrase while live note remains");
  h.run("send_once_to_instruments(0,144,65,90,1);sw_submit(0,0,0,0);");
  h.block();
  e = h.events();
  bool same_off = false;
  for (auto m : e)
    if (m[0] == 128 && m[1] == 65)
      same_off = true;
  check(!same_off, "STOP protects live note at same pitch");
  h.midi(0x80, 65, 0);
  h.events();
  h.run("send_once_to_instruments(0,176,64,127,1);sw_submit(0,0,0,0);");
  h.block();
  e = h.events();
  bool sustain_off = false;
  for (auto m : e)
    if (m[0] == 176 && m[1] == 64 && m[2] == 0)
      sustain_off = true;
  check(sustain_off, "STOP releases phrase sustain");
  h.run("send_to_instruments(0,176,64,127,1);send_once_to_instruments(0,176,64,"
        "127,1);sw_submit(0,0,0,0);");
  h.block();
  e = h.events();
  sustain_off = false;
  for (auto m : e)
    if (m[0] == 176 && m[1] == 64 && m[2] == 0)
      sustain_off = true;
  check(!sustain_off, "STOP protects live sustain");
  h.midi(0xB0, 64, 0);
  h.events();
  // Mono transitions may be caused by a phrase while the selected live note
  // remains held.
  h.run("mem[INST_TRANSFORM_COUNT_BASE]=1;mem[INST_TRANSFORM_TYPE_BASE]=3;mem["
        "INST_NOTE_MODE_BASE]=2;");
  h.midi(0x90, 65, 90);
  h.events();
  h.run("send_once_to_instruments(0,144,80,90,1);sw_submit(0,0,0,0);");
  h.block();
  e = h.events();
  bool restored_live = false;
  for (auto m : e)
    if (m[0] == 144 && m[1] == 65)
      restored_live = true;
  check(restored_live, "STOP restores retained live mono selection");
  h.midi(0x80, 65, 0);
  h.events();
  h.eq("mem[SW_LIVE_OUT_BASE+65]", 0,
       "mono release clears live observation after restoration");
  h.run("send_once_to_instruments(0,144,65,90,1);sw_submit(0,0,0,0);");
  h.block();
  e = h.events();
  bool mono_off = false;
  for (auto m : e)
    if (m[0] == 128 && m[1] == 65)
      mono_off = true;
  check(mono_off, "stale mono ownership cannot suppress later phrase release");
  h.run("mem[INST_NOTE_MODE_BASE]=0;mem[INST_TRANSFORM_COUNT_BASE]=0;");
  // ARP HOLD retains live sources and latches while clearing phrase ownership.
  h.run("mem[INST_TRANSFORM_COUNT_BASE]=1;mem[INST_TRANSFORM_TYPE_BASE]=5;mem["
        "INST_ARP_ENABLED_BASE]=1;"
        "mem[INST_ARP_HOLD_BASE]=1;send_to_instruments(0,144,67,90,1);send_"
        "once_to_instruments(0,144,60,90,1);"
        "send_once_to_instruments(0,128,60,0,1);sw_submit(0,0,0,0);");
  h.block();
  h.events();
  h.eq("mem[ARP_HELD_COUNT_BASE+60]", 0,
       "STOP removes released phrase ARP latch");
  h.eq("mem[ARP_HELD_COUNT_BASE+67]", 1, "STOP keeps live ARP latch");
  h.eq("mem[ARP_SOURCE_COUNT_BASE+67]", 1,
       "STOP keeps physically held live ARP source");
  h.run("mem[INST_ARP_ENABLED_BASE]=0;send_all_notes_off();mem[INST_TRANSFORM_"
        "COUNT_BASE]=0;");
  h.block();
  h.events();
  h.run("sw_defaults();mem[sw_cfg(2)+11]=2;mem[sw_cfg(2)+SW_LIST]=6;mem[sw_cfg("
        "2)+SW_LIST+1]=0;mem[sw_cfg(2)+SW_NAME]=86;save_patch(1);sw_defaults();"
        "current_patch=2;load_patch(1);");
  h.eq("mem[sw_cfg(2)+SW_LIST]", 6, "bank restores switch list");
  h.eq("mem[sw_cfg(2)+SW_NAME]", 86, "bank restores switch name");
  h.eq("mem[sw_rt(2)+7]", -1, "runtime cursor reset on bank load");
  h.run("external_patch_save_request(1);sw_defaults();external_patch_apply();");
  h.eq("mem[sw_cfg(2)+11]", 2, "schema3 external switch round trip");
  h.run("gmem[2]=2;gmem[3]=SW_LEGACY_PAYLOAD;external_patch_apply();");
  h.eq("mem[sw_cfg(2)]", 0, "schema2 migration disables new switches");
  h.eq("mem[sw_cfg(2)+11]", 0, "schema2 migration default empty list");
  h.run("sw_defaults();sw_runtime_reset();ui_scroll=510;ui_sw_selected=0;"
        "controller_assign_ti=-1;transform_menu_gi=-1;options_open=0;");
  h.frame(40, 1138, 1);
  h.frame(40, 1138, 0);
  h.block();
  h.events();
  h.eq("mem[sw_cfg(0)+11]", 1, "GUI pool appends via audio queue");
  h.run("sw_submit(0,3,0,0);sw_queue_process();sw_traverse(0);");
  h.eq("mem[sw_rt(0)+7]", 0, "duplicate references have one active position");
  h.frame();
  h.frame();
  auto pixel = [&](int x, int y) { return h.pixels[(y * 1040 + x) * 4]; };
  check(pixel(25, 1163) != pixel(143, 1163),
        "GUI highlights active position only for duplicate phrase IDs");
  h.run("options_open=1;");
  h.frame(40, 1138, 1);
  h.frame(40, 1138, 0);
  h.block();
  h.events();
  h.eq("mem[sw_cfg(0)+11]", 2, "popup prevents underlying switch pool clicks");
  h.eq("SW_MEMORY_END<8388608", 1,
       "runtime allocation stays inside EEL2 RAM limit");
}
