static void project_state_tests(const char *path) {
  Host source(path);
  source.run(
      "panic_pending=0;i_add();i_add();mem[engine_addr(INST_LEVEL_BASE,4)]=87;"
      "mem[exp_bend_addr(param_ti(4,EXP_T_LEVEL))]=.123456789012345;"
      "store_event(0,16777217,144,65,97,0);mem[LEN_BASE]=16777300;loop_len_"
      "samples=16777300;"
      "mem[sw_cfg(0)+SW_LIST]=5;sw_submit(0,14,0,0);sw_queue_process();sw_"
      "commit_edit();"
      "mem[sw_cfg(4)+SW_LIST]=7;save_patch(1);"
      "mem[engine_addr(INST_LEVEL_BASE,4)]=99;save_patch(2);"
      "mem[engine_addr(INST_LEVEL_BASE,4)]=101;current_patch=1;"
      "learn_start(0);sw_submit(1,11,0,0);sw_queue_process();mem[SW_DRAFT_BASE+"
      "SW_LIST]=12;");
  auto *state = ysfx_save_state(source.f);
  check(state && state->data_size > 0,
        "project has actual serialized configuration");
  source.eq("mem[engine_addr(INST_LEVEL_BASE,4)]", 101,
            "project capture leaves working configuration unchanged");
  source.eq("mem[sw_cfg(1)+SW_LIST]", 0,
            "project capture never commits switch draft");
  Host reopened(path);
  ysfx_load_state(reopened.f, state);
  reopened.block();
  reopened.events();
  reopened.eq("mem[I_EXISTS_BASE+4]", 1, "project reopen restores fifth panel");
  reopened.eq(
      "mem[engine_addr(INST_LEVEL_BASE,4)]", 101,
      "reopen preserves unsaved working configuration separately from banks");
  reopened.eq("mem[sw_cfg(4)+SW_LIST]", 7,
              "project restores dynamic Smart Switch sequence");
  check(reopened.eval("mem[exp_bend_addr(param_ti(4,EXP_T_LEVEL))]") ==
            .123456789012345,
        "project codec preserves exact double curve bend");
  reopened.eq(
      "mem[layer_base(0,0)]", 16777217,
      "project codec preserves sample offset beyond float32 integer precision");
  reopened.eq("sw_learn", -1, "reopen cancels MIDI Learn");
  reopened.eq("ui_sw_editor_open", 0, "reopen excludes uncommitted editor");
  reopened.eq("mem[sw_cfg(1)+SW_LIST]", 0, "reopen discards draft settings");
  reopened.eq("mem[VOICE_ACTIVE_BASE]", 0,
              "reopen does not resume sounding phrase voices");
  reopened.run("current_patch=2;restore_current_patch_raw();");
  reopened.eq("mem[engine_addr(INST_LEVEL_BASE,4)]", 99,
              "project includes second bank");
  reopened.run("current_patch=1;restore_current_patch_raw();");
  reopened.eq("mem[engine_addr(INST_LEVEL_BASE,4)]", 87,
              "project includes first bank");
  // REAPER may call @init after @serialize. The staged snapshot survives that
  // order.
  ysfx_load_state(reopened.f, state);
  ysfx_init(reopened.f);
  reopened.block();
  reopened.events();
  reopened.eq("mem[engine_addr(INST_LEVEL_BASE,4)]", 101,
              "re-init after project restore retains working state");
  reopened.eq("mem[I_EXISTS_BASE+4]", 1,
              "re-init preserves dynamic collection");
  Host cold(path, false);
  ysfx_load_state(cold.f, state);
  ysfx_init(cold.f);
  cold.block();
  cold.events();
  cold.eq(
      "mem[engine_addr(INST_LEVEL_BASE,4)]", 101,
      "serialize before first init restores complete working configuration");
  auto truncated = *state;
  truncated.data_size -= 16;
  Host rejected(path);
  ysfx_load_state(rejected.f, &truncated);
  rejected.block();
  rejected.events();
  rejected.eq(
      "mem[I_EXISTS_BASE+4]", 0,
      "truncated project snapshot never partially changes configuration");
  ysfx_state_free(state);
}
