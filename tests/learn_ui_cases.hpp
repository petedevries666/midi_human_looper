static void click(Host &h, int x, int y) {
  h.frame(x, y, 1);
  h.frame(x, y, 0);
  h.block();
  h.events();
}
static void open_sw_editor(Host &h, int si) {
  if (h.val("ui_sw_editor_open")) {
    h.run("sw_submit(ui_sw_selected,13,0,0);");
    h.block();
    h.events();
  }
  int ordinal = 0;
  for (int j = 0; j < si; j++)
    if (h.eval("mem[sw_cfg(" + std::to_string(j) + ")+20]") > 0)
      ordinal++;
  click(h, 50 + (ordinal % 4) * 250,
        1490 + 26 + (ordinal / 4) * 84 + 62 - int(h.val("ui_scroll")));
  h.frame();
  h.eq("sw_edit_target", si, "card EDIT opens exactly selected switch");
}
static void sw_editor_click(Host &h, int x, int old_y) {
  click(h, x,
        int(h.val("ui_sw_editor_y")) + old_y - 980 - int(h.val("ui_scroll")));
}
static void sw_editor_done(Host &h) {
  click(h, 750, int(h.val("ui_sw_editor_y")) + 520 - int(h.val("ui_scroll")));
  h.eq("ui_sw_editor_open", 0, "DONE commits and closes editor");
}
static void sw_editor_cancel(Host &h) {
  click(h, 900, int(h.val("ui_sw_editor_y")) + 520 - int(h.val("ui_scroll")));
  h.eq("ui_sw_editor_open", 0, "CANCEL discards and closes editor");
}
static void learn_ui_tests(Host &h) {
  h.run(
      "sw_defaults();sw_runtime_reset();panic_pending=0;state=STATE_STOPPED;"
      "mem[INST_ENABLED_BASE]=1;mem[INST_ENABLED_BASE+1]=0;mem[INST_ENABLED_"
      "BASE+2]=0;"
      "mem[INST_TRANSFORM_COUNT_BASE]=0;mem[INST_IN_BASE]=0;mem[INST_OUT_BASE]="
      "0;"
      "mem[COUNT_BASE]=0;store_event(0,0,144,50,90,0);store_event(0,500,128,50,"
      "0,0);mem[LEN_BASE]=1000;mem[MODE_BASE]=1;"
      "mem[COUNT_BASE+6]=0;store_event(6,0,144,56,90,0);store_event(6,500,128,"
      "56,0,0);mem[LEN_BASE+6]=1000;mem[MODE_BASE+6]=1;"
      "mem[sw_cfg(0)+11]=2;mem[sw_cfg(0)+SW_LIST]=0;mem[sw_cfg(0)+SW_LIST+1]=6;"
      "mem[sw_cfg(1)+11]=2;mem[sw_cfg(1)+SW_LIST]=6;mem[sw_cfg(1)+SW_LIST+1]=0;"
      "ui_scroll=510;");
  open_sw_editor(h, 0);
  sw_editor_click(h, 320, 1046);
  h.eq("sw_learn", 0, "GUI stores precise VERSE learn target");
  h.midi(0x92, 72, 90);
  check(h.events().empty(), "capture does not trigger VERSE");
  h.midi(0x82, 72, 0);
  check(h.events().empty(), "learned release silent");
  sw_editor_done(h);
  open_sw_editor(h, 1);
  sw_editor_click(h, 320, 1046);
  h.eq("sw_learn", 1, "GUI stores precise CHORUS learn target");
  h.midi(0x92, 73, 1);
  check(h.events().empty(), "capture does not trigger CHORUS");
  h.midi(0x82, 73, 0);
  h.events();
  h.eq("sw_learn", -1, "capture exits Learn");
  sw_editor_done(h);
  h.eq("mem[sw_cfg(0)+4]", 72, "VERSE assignment retained");
  h.eq("mem[sw_cfg(1)+4]", 73, "CHORUS independent assignment");
  h.midi(0x92, 72, 90);
  h.events();
  h.midi(0x82, 72, 0);
  h.events();
  h.eq("mem[sw_rt(0)+7]", 0, "A triggers only VERSE");
  h.eq("mem[sw_rt(1)+7]", -1, "A does not trigger CHORUS");
  h.midi(0x92, 73, 90);
  h.events();
  h.midi(0x82, 73, 0);
  h.events();
  h.eq("mem[sw_rt(1)+7]", 0, "B triggers CHORUS");
  h.eq("mem[sw_rt(0)+7]", 0, "B leaves VERSE position");
  open_sw_editor(h, 1);
  // Switch conflicts remain visible and actionable while scrolled to the
  // editor.
  sw_editor_click(h, 320, 1046);
  h.midi(0x92, 72, 90);
  h.events();
  h.eq("learn_conflict", 0, "CHORUS learn warns about existing VERSE input");
  h.eq("mem[sw_cfg(1)+4]", 73, "switch conflict preserves CHORUS input");
  click(h, 580, 385);
  h.eq("learn_candidate", -1,
       "scrolled conflict cancel is visible and operable");
  h.midi(0x82, 72, 0);
  h.events();
  sw_editor_cancel(h);
  h.run("ui_scroll=0;");
  click(h, 825, 80);
  h.eq("options_open", 1, "open OPTIONS");
  click(h, 982, 120);
  h.eq("options_open", 0, "visible close button dismisses OPTIONS");
  click(h, 825, 80);
  h.run("learn_start(SW_COUNT);");
  click(h, 30, 400);
  h.eq("options_open", 0, "outside click dismisses OPTIONS");
  h.eq("controller_learn", -1, "popup close cancels Learn");
  h.eq("state", 4, "outside dismissal does not activate underlying controls");
  h.eq("mem[sw_cfg(0)+4]", 72, "closing preserves VERSE assignment");
  click(h, 825, 80);
  h.run("learn_start(SW_COUNT);");
  ysfx_gfx_add_key(h.f, 0, 27, true);
  h.frame();
  ysfx_gfx_add_key(h.f, 0, 27, false);
  h.block();
  h.events();
  h.eq("options_open", 0, "ESC dismisses OPTIONS");
  h.eq("controller_learn", -1, "ESC cancels Learn without capture");

  click(h, 825, 80);
  click(h, 810, 150);
  h.eq("controller_learn", 0, "OPTIONS starts first controller Learn");
  click(h, 810, 184);
  h.eq("controller_learn", 1, "only most recent controller listening");
  h.eq("sw_learn", -1, "expression Learn clears switch listener");
  h.midi(0xB3, 21, 100);
  check(h.events().empty(), "expression capture consumed");
  h.eq("mem[CONTROLLER_CC_BASE]", -1, "other controller unchanged");
  h.eq("mem[CONTROLLER_CC_BASE+1]", 21, "only target captures CC");
  h.eq("controller_learn", -1, "expression capture exits Learn");
  h.eq("mem[sw_cfg(1)+24]", 4, "exact expression channel stored");
  h.eq("mem[sw_cfg(1)+25]", 2, "exact expression type stored");
  h.midi(0xB3, 21, 0);
  h.events();
  h.midi(0xB2, 21, 20);
  h.events();
  h.eq("ctrl_val1", 0, "wrong channel cannot control expression target");
  h.midi(0xB3, 21, 64);
  h.events();
  h.eq("ctrl_val1", 64.0 / 127,
       "assigned channel updates only expression target");
  click(h, 810, 150);
  h.midi(0xB3, 21, 100);
  check(h.events().empty(), "conflicting learn message consumed");
  h.eq("learn_conflict", h.val("SW_COUNT") + 1,
       "conflict identifies existing expression controller");
  h.eq("mem[CONTROLLER_CC_BASE]", -1, "conflict cannot overwrite target");
  click(h, 580, 385);
  h.eq("learn_candidate", -1, "cancel closes conflict");
  h.eq("mem[CONTROLLER_CC_BASE+1]", 21, "cancel preserves old owner");
  h.midi(0xB3, 21, 0);
  h.events();
  click(h, 810, 150);
  h.midi(0xB3, 21, 100);
  h.events();
  click(h, 410, 385);
  h.eq("mem[CONTROLLER_CC_BASE]", 21,
       "deliberate reassignment captures target");
  h.eq("mem[CONTROLLER_CC_BASE+1]", -1,
       "deliberate reassignment removes previous owner only");
  h.midi(0xB3, 21, 0);
  h.events();
  click(h, 810, 184);
  h.midi(0xB4, 22, 100);
  h.events();
  h.midi(0xB4, 22, 0);
  h.events();
  click(h, 945, 184);
  h.eq("mem[CONTROLLER_CC_BASE+1]", -1,
       "expression FORGET removes only selected mapping");
  h.eq("mem[CONTROLLER_CC_BASE]", 21,
       "expression FORGET preserves other controller");
  click(h, 982, 120);
  h.run("ui_scroll=510;ui_sw_selected=0;");
  open_sw_editor(h, 0);
  sw_editor_click(h, 860, 1078);
  sw_editor_done(h);
  h.eq("mem[sw_cfg(0)+2]", 0, "FORGET A removes only input kind");
  h.eq("mem[sw_cfg(1)+4]", 73, "FORGET A preserves B");
  h.eq("mem[sw_cfg(0)+11]", 2, "FORGET preserves sequence");
  h.eq("mem[sw_cfg(0)+14]", 1, "FORGET preserves gesture action");
  open_sw_editor(h, 0);
  sw_editor_click(h, 320, 1046);
  h.midi(0x92, 72, 90);
  h.events();
  h.midi(0x82, 72, 0);
  h.events();
  sw_editor_done(h);
  h.eq("mem[sw_cfg(0)+2]", 1, "A can be relearned");
  open_sw_editor(h, 0);
  h.run("mem[sw_cfg(0)]=0;sw_reset(0);sw_reset(1);last_trigger_layer=-1;");
  int test_y = int(h.val("ui_sw_editor_y")) + 325 - int(h.val("ui_scroll"));
  h.frame(700, test_y, 1);
  h.frame(700, test_y, 0);
  h.block();
  auto e = h.events();
  bool note = false;
  for (auto m : e)
    if (m[0] == 144 && m[1] == 50)
      note = true;
  check(note, "GUI TEST TAP plays phrase even with hardware input disabled");
  h.eq("mem[sw_rt(0)+12]", 2, "TEST adds exactly one action");
  h.eq("mem[sw_rt(1)+7]", -1, "TEST uses selected switch only");
  h.eq("mem[sw_cfg(0)+4]", 72, "TEST does not alter assignment");
  h.run("mem[sw_edit_cfg(0)+15]=SW_RESET;mem[sw_edit_cfg(0)+17]=0;mem[sw_edit_"
        "cfg(0)+18]=0;"
        "mem[sw_edit_cfg(0)+16]=SW_STOP;");
  sw_editor_click(h, 700, 1335);
  h.eq("mem[sw_rt(0)+7]", -1, "TEST DOUBLE dispatches configured reset");
  sw_editor_click(h, 700, 1365);
  h.eq("mem[sw_rt(0)+11]", 2, "TEST HOLD dispatches configured stop");
  sw_editor_done(h);
  // Include a fifth committed switch in the real GUI SAVE snapshot.
  h.run(
      "sw_submit(0,14,0,0);sw_queue_process();mem[SW_DRAFT_BASE+2]=1;"
      "mem[SW_DRAFT_BASE+3]=2;mem[SW_DRAFT_BASE+4]=75;mem[SW_DRAFT_BASE+11]=2;"
      "mem[SW_DRAFT_BASE+SW_LIST]=0;mem[SW_DRAFT_BASE+SW_LIST+1]=6;sw_commit_"
      "edit();");
  // Include an actual extra CC instance in the native GUI SAVE fixture.
  h.run("mem[INST_TRANSFORM_COUNT_BASE]=2;mem[INST_TRANSFORM_TYPE_BASE]=6;"
        "mem[INST_TRANSFORM_TYPE_BASE+1]=7;mem[cc_cfg(0)]=50;"
        "mem[CC_CFG_BASE+1]=51;mem[cc_cfg(0)+1]=71;mem[cc_cfg(0)+2]=64;"
        "mem[cc_cfg(0)+3]=12;mem[exp_bend_addr(cc_ti(0,0))]=.25;");
  h.run("i_add();transform_add(3,6);transform_add(3,6);");
  h.block();
  h.events();
  h.run("mem[engine_addr(INST_LEVEL_BASE,3)]=93;mem[cc_cfg(15)+1]=76;mem[cc_"
        "cfg(15)+2]=81;"
        "mem[exp_bend_addr(param_ti(3,EXP_T_LEVEL))]=-.375;");
  // Exercise the real SAVE button while an assignment edit is still queued.
  h.run("ui_scroll=0;mem[sw_cfg(0)]=1;sw_submit(0,1,1,74);mem[sw_cfg(0)+SW_"
        "NAME]=86;mem[sw_cfg(1)+SW_NAME]=67;");
  h.frame(115, 120, 1);
  h.frame(115, 120, 0);
  h.eq("gmem[0]", 0,
       "SAVE waits for DSP snapshot rather than reading pending GUI "
       "configuration");
  h.block();
  h.events();
  h.eq("gmem[IO_PAYLOAD_BASE+SW_LEGACY_PAYLOAD+1+4]", 74,
       "SAVE includes queued MIDI assignment");
  h.eq("gmem[IO_PAYLOAD_BASE+SW_LEGACY_PAYLOAD+1+SW_LIST]", 0,
       "SAVE includes phrase list");
  if (const char *fixture = std::getenv("NATIVE_PATCH_FIXTURE")) {
    std::ofstream file(fixture);
    file.precision(17);
    check(bool(file), "open native SAVE snapshot fixture");
    file << "{\"format\":\"MIDI_HUMAN_LOOPER_PATCH\",\"schema\":"
         << int(h.val("IO_SCHEMA"))
         << ",\"work_mem_size\":" << int(h.val("PATCH_PAYLOAD_SIZE"))
         << ",\"globals\":[";
    for (int i = 4; i <= 12; i++) {
      if (i > 4)
        file << ",";
      file << h.eval("gmem[" + std::to_string(i) + "]");
    }
    file << "],\"memory\":[";
    for (int i = 0; i < int(h.val("PATCH_PAYLOAD_SIZE")); i++) {
      if (i)
        file << ",";
      file << h.eval("gmem[IO_PAYLOAD_BASE+" + std::to_string(i) + "]");
    }
    file << "],\"switch_tail_offset\":" << int(h.val("SW_LEGACY_PAYLOAD"))
         << ",\"cc_tail_offset\":" << int(h.val("CC_LEGACY_PAYLOAD"))
         << ",\"dynamic_switch_tail_offset\":"
         << int(h.val("DS_LEGACY_PAYLOAD"))
         << ",\"instrument_tail_offset\":" << int(h.val("I_LEGACY_PAYLOAD"))
         << ",\"instrument_level_offset\":"
         << int(h.eval("I_LEGACY_PAYLOAD+param_addr(3,EXP_T_LEVEL)-I_CFG_BASE"))
         << ",\"instrument_cc_offset\":"
         << int(h.eval("I_LEGACY_PAYLOAD+cc_cfg(15)-I_CFG_BASE")) << "}";
  }
  h.run("sw_defaults();gmem[0]=3;");
  h.block();
  h.events();
  h.eq("mem[sw_cfg(0)+4]", 74, "GUI save/reload restores A");
  h.eq("mem[sw_cfg(1)+4]", 73, "GUI save/reload restores B");
  h.eq("mem[sw_cfg(0)+11]", 2, "GUI save/reload restores sequence");
  h.eq("mem[sw_cfg(0)+15]", 3, "GUI save/reload restores gestures");
  h.eq("mem[CONTROLLER_CC_BASE]", 21,
       "GUI save/reload restores expression number");
  h.eq("mem[sw_cfg(0)+24]", 4,
       "GUI save/reload restores expression exact channel");
  h.run("learn_forget(0);external_patch_save_request(1);sw_defaults();external_"
        "patch_apply();");
  h.eq("mem[sw_cfg(0)+2]", 0, "FORGET persists in external patch");
  h.eq("mem[sw_cfg(1)+4]", 73, "persisted FORGET leaves B untouched");
  h.run("mem[sw_cfg(0)+10]=1;sw_last_active=-1;sw_traverse(0);sw_traverse(0);"
        "sw_traverse(1);");
  h.eq("sw_traverse(0)", 0,
       "RESTART on reentry survives assignment edits and save/reload");
  h.run("learn_start(1);");
  h.midi(0xB5, 23, 127);
  h.events();
  h.midi(0xB5, 23, 63);
  h.events();
  double actions = h.eval("mem[sw_rt(1)+12]");
  h.run("sw_clock+=11*srate;mem[sw_cfg(1)+14]=SW_RESET;mem[sw_cfg(1)+17]=1;");
  h.midi(0xB5, 23, 127);
  h.events();
  h.eq("mem[sw_rt(1)+12]", actions + 1,
       "missing learned CC release cannot quarantine input forever");
  h.run("current_patch=1;gmem[0]=0;ui_scroll=0;");
  click(h, 270, 120);
  h.eq("gmem[1]", 2, "second SAVE button snapshots requested file slot");
  h.eq("current_patch", 1, "saving another slot preserves selected patch");
  h.eq("save_flash", 0,
       "bank snapshot cannot announce file save before Lua acknowledges");
}
