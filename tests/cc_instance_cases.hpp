static void cc_click(Host &h, int x, int y) {
  h.frame(x, y, 1);
  h.frame(x, y, 0);
  h.block();
  h.events();
}
static std::vector<std::vector<int>> cc_block(Host &h) {
  h.block();
  return h.events();
}
static void cc_expect(const std::vector<std::vector<int>> &events,
                      const std::vector<std::vector<int>> &want,
                      const char *label) {
  check(events == want, label);
  if (events != want)
    for (const auto &e : events)
      fprintf(stderr, "event %d %d %d\n", e[0], e[1], e[2]);
}
static void cc_instance_tests(Host &h) {
  h.run("panic_pending=0;state=STATE_IDLE;param_extension_reset();"
        "cc_defaults();cc_runtime_reset();mem[INST_ENABLED_BASE]=1;"
        "mem[INST_ENABLED_BASE+1]=0;mem[INST_ENABLED_BASE+2]=0;"
        "mem[INST_TRANSFORM_COUNT_BASE]=0;mem[INST_OUT_BASE]=2;"
        "mem[INST_IN_BASE]=0;");
  h.frame();
  int row = int(h.val("transform_rows_y"));
  cc_click(h, 90, row + 70);
  h.eq("transform_menu_gi", 0, "ADD opens popup");
  h.frame(440, 95, 2);
  h.eq("transform_menu_gi", -1, "right outside closes ADD popup");
  h.frame(440, 95, 0);
  h.eq("mem[INST_TRANSFORM_COUNT_BASE]", 0,
       "outside dismissal does not create a transformer");
  cc_click(h, 90, row + 70);
  // Left click outside on the instrument power switch is consumed.
  cc_click(h, 40, row + 24);
  h.eq("transform_menu_gi", -1, "left outside closes ADD popup");
  h.eq("mem[INST_ENABLED_BASE]", 1, "dismissal isolates underlying power");
  cc_click(h, 90, row + 70);
  cc_click(h, 182, row + 95);
  h.eq("transform_menu_gi", -1, "visible X closes ADD popup");
  cc_click(h, 90, row + 70);
  ysfx_gfx_add_key(h.f, 0, 27, true);
  h.frame();
  h.eq("transform_menu_gi", -1, "ESC closes ADD popup");
  h.frame();
  // OPTIONS follows the same outside-right dismissal and Learn cancellation.
  cc_click(h, 820, 80);
  h.run("learn_start(SW_COUNT);");
  h.frame(40, row + 24, 2);
  h.frame(40, row + 24, 0);
  h.block();
  h.events();
  h.eq("options_open", 0, "right outside closes OPTIONS consistently");
  h.eq("controller_learn", -1, "dismissal cancels unfinished Learn");
  h.eq("controller_assign_ti", -1,
       "dismissal never opens underlying assignment");
  // Create three real CC blocks using the popup, not synthetic configuration.
  for (int i = 0; i < 3; ++i) {
    cc_click(h, 70 + i * 150, row + 70);
    cc_click(h, 70 + i * 150, row + 94 + 22 + 5 * 24 + 8);
    h.eq("transform_menu_gi", -1, "selection closes ADD popup");
    h.eq("mem[INST_TRANSFORM_COUNT_BASE]", i + 1,
         "CC type can be added repeatedly");
  }
  h.eq("mem[INST_TRANSFORM_TYPE_BASE]", 6, "legacy CC identity retained");
  h.eq("mem[INST_TRANSFORM_TYPE_BASE+1]", 7, "second CC independent slot");
  h.eq("mem[INST_TRANSFORM_TYPE_BASE+2]", 8, "third CC independent slot");
  h.eq("mem[cc_cfg(0)]", 5, "second CC receives unique lifetime ID");
  h.eq("mem[cc_cfg(1)]", 6, "third CC receives unique lifetime ID");
  h.run("mem[PARAM_MOD_CC_BASE]=74;mem[INST_MOD_BASE]=90;"
        "mem[cc_cfg(0)+1]=71;mem[cc_cfg(0)+2]=40;"
        "mem[cc_cfg(1)+1]=1;mem[cc_cfg(1)+2]=60;cc_runtime_reset();");
  cc_expect(cc_block(h), {{177, 74, 90}, {177, 71, 40}, {177, 1, 60}},
            "three independent CC targets emit once in visible order");
  cc_expect(cc_block(h), {}, "unchanged CC instances do not spam events");
  h.run("mem[cc_cfg(0)+3]=4;");
  cc_expect(cc_block(h), {{179, 71, 40}},
            "instance channel overrides instrument");
  h.run("mem[cc_cfg(0)+3]=0;mem[cc_cfg(0)+1]=74;"
        "mem[cc_cfg(1)+1]=74;");
  cc_expect(cc_block(h), {{177, 74, 90}, {177, 74, 40}, {177, 74, 60}},
            "duplicate targets are deterministic last visible writer wins");
  h.eq("cc_ui_duplicate(0,6)", 1, "duplicate warning recognizes active target");
  h.run("transform_add(1,6);mem[INST_ENABLED_BASE+1]=1;mem[INST_OUT_BASE+1]=2;"
        "mem[PARAM_MOD_CC_BASE+1]=74;mem[INST_MOD_BASE+1]=10;");
  cc_expect(cc_block(h),
            {{177, 74, 90}, {177, 74, 40}, {177, 74, 60}, {177, 74, 10}},
            "same target across instruments follows visible instrument order");
  h.run("mem[INST_ENABLED_BASE+1]=0;");
  cc_expect(cc_block(h), {{177, 74, 90}, {177, 74, 40}, {177, 74, 60}},
            "disabling later instrument restores preceding CC writer");
  h.run("mem[INST_MOD_BASE]=95;");
  cc_expect(cc_block(h), {{177, 74, 95}, {177, 74, 40}, {177, 74, 60}},
            "earlier writer update cannot override unchanged last writer");
  h.run("mem[INST_TRANSFORM_TYPE_BASE+2]=-8;");
  cc_expect(cc_block(h), {{177, 74, 95}, {177, 74, 40}},
            "bypass last duplicate restores prior writer");
  h.run("mem[INST_TRANSFORM_TYPE_BASE]=8;mem[INST_TRANSFORM_TYPE_BASE+1]=7;"
        "mem[INST_TRANSFORM_TYPE_BASE+2]=6;cc_runtime_reset();");
  cc_expect(
      cc_block(h), {{177, 74, 60}, {177, 74, 40}, {177, 74, 95}},
      "reordering slots changes winner without changing instance settings");
  h.eq("mem[cc_cfg(1)]", 6, "stable ID survives reorder");
  // Expression curves, pending edits and graphical previews belong to each CC.
  h.run("mem[INST_TRANSFORM_TYPE_BASE]=6;mem[INST_TRANSFORM_TYPE_BASE+1]=7;"
        "mem[INST_TRANSFORM_TYPE_BASE+2]=8;mem[cc_cfg(0)+1]=71;"
        "mem[cc_cfg(1)+1]=1;mem[exp_assign_addr(cc_ti(0,0))]=1;"
        "mem[exp_assign_addr(cc_ti(1,0))]=1;curve_factory(cc_ti(0,0),3);"
        "curve_factory(cc_ti(1,0),4);controller_set_value(0,.25);");
  cc_block(h);
  h.eq("mem[cc_cfg(0)+2]", 32, "second CC own increasing curve");
  h.eq("mem[cc_cfg(1)+2]", 95, "third CC own inverse curve");
  h.run("selected_transform_gi=0;selected_transform_slot=1;exp_editor_ti=-1;");
  h.frame();
  int editor = row + 372 + 6;
  h.frame(200, editor + 68, 2);
  h.frame(200, editor + 68, 0);
  cc_click(h, 220, editor + 68 + 28 + 8);
  h.eq("exp_editor_ti", h.eval("cc_ti(0,0)"),
       "assign extra CC expression immediately opens its own curve");
  h.eq("mem[exp_assign_addr(cc_ti(1,0))]", 1,
       "assignment popup does not affect another instance");
  h.run("exp_editor_ti=-1;");
  h.frame();
  auto before = h.hash();
  h.run("mem[exp_bend_addr(cc_ti(0,0))]=.5;");
  h.frame();
  check(h.hash() != before, "extra CC rail preview updates after bend edit");
  h.eq("mem[exp_bend_addr(cc_ti(1,0))]", 0,
       "bend edit does not affect another CC curve");
  h.run("mem[exp_assign_addr(cc_ti(0,1))]=2;controller_set_value(1,.5);");
  cc_block(h);
  h.eq("mem[cc_cfg(0)+1]", 64,
       "CC-number expression mapping belongs to selected instance");
  h.eq("mem[cc_cfg(1)+1]", 1,
       "CC-number mapping leaves other destination untouched");
  h.run("controller_set_value(1,.6);");
  auto remap = cc_block(h);
  check(remap.size() == 2 && remap[0] == std::vector<int>({177, 64, 0}) &&
            remap[1][1] == 76,
        "expression remap releases stateful previous CC target");
  h.run("controller_set_value(1,71/127);cc_expression_tick();");
  // Save real external payload and both internal banks, including instance IDs.
  h.run("save_patch(1);external_patch_save_request(1);cc_defaults();"
        "external_patch_apply();");
  h.eq("io_status", 3, "schema4 external CC import succeeds");
  h.eq("mem[cc_cfg(1)]", 6, "external patch preserves instance IDs");
  h.eq("mem[cc_cfg(0)+1]", 71, "external patch preserves CC number");
  h.eq("mem[exp_assign_addr(cc_ti(0,1))]", 2,
       "external patch preserves CC-number expression mapping");
  h.eq("mem[exp_bend_addr(cc_ti(0,0))]", .5,
       "external patch preserves per-instance bend");
  h.run("mem[cc_cfg(0)+1]=20;save_patch(2);cc_bank_load(1);");
  h.eq("mem[cc_cfg(0)+1]", 71, "PATCH 1 bank restores extra instance");
  h.run("cc_bank_load(2);");
  h.eq("mem[cc_cfg(0)+1]", 20, "PATCH 2 independent extra configuration");
  h.run("gmem[2]=3;gmem[3]=CC_LEGACY_PAYLOAD;external_patch_apply();");
  h.eq("io_status", 3, "existing schema3 patch accepted");
  h.eq("mem[cc_cfg(0)]", 0,
       "schema3 migration initializes empty extra collection");
  h.eq("mem[PARAM_MOD_CC_BASE]", 74, "schema3 retains legacy CC parameters");
  h.run("gmem[0]=0;mem[cc_cfg(0)]=5;mem[exp_assign_addr(cc_ti(0,0))]=0;"
        "mem[param_pending_addr(cc_ti(0,0))]=81;patch_save_request=1;panic_"
        "pending=0;");
  cc_block(h);
  h.eq("gmem[IO_PAYLOAD_BASE+CC_LEGACY_PAYLOAD+2+INSTRUMENTS+2]", 81,
       "SAVE snapshot includes unapplied extra CC rail edit");
  h.run("gmem[0]=0;");
  // Stateful CC cleanup uses the actual old destination; no blanket note panic.
  h.run("transform_add(0,6);mem[INST_TRANSFORM_COUNT_BASE]=2;"
        "mem[INST_TRANSFORM_TYPE_BASE]=6;mem[INST_TRANSFORM_TYPE_BASE+1]=7;"
        "mem[cc_cfg(0)]=99;mem[cc_cfg(0)+1]=64;mem[cc_cfg(0)+2]=127;"
        "mem[cc_cfg(0)+3]=5;panic_pending=0;cc_runtime_reset();");
  cc_block(h);
  h.run("mem[cc_cfg(0)+3]=6;");
  cc_expect(cc_block(h), {{180, 64, 0}, {181, 64, 127}},
            "channel change releases previous sustain before new target");
  h.midi(144, 60, 100);
  cc_expect(h.events(), {{145, 60, 100}},
            "live note routes normally with stacked CCs");
  h.run("transform_remove_slot(0,1);");
  h.eq("panic_pending", 0, "CC removal does not panic unrelated notes");
  cc_expect(cc_block(h), {{181, 64, 0}}, "CC removal releases owned sustain");
  h.midi(128, 60, 0);
  cc_expect(h.events(), {{129, 60, 0}},
            "live Note Off stays paired after CC removal");
  h.run("transform_add(0,6);");
  check(h.eval("mem[cc_cfg(0)]") != 99,
        "reused storage gets a new creation ID");
  h.eq("mem[exp_assign_addr(cc_ti(0,0))]", 0,
       "new instance never inherits removed curve assignment");
  // The six visible slots are a bounded engine capacity, never silently
  // truncated.
  h.run("transform_add(0,6);transform_add(0,6);transform_add(0,6);"
        "transform_add(0,6);transform_add(0,6);");
  h.eq("mem[INST_TRANSFORM_COUNT_BASE]", 6,
       "six CC instance capacity enforced");
  check(h.eval("CC_PARAM_PENDING_BASE+CC_EXTRA*2") < 8388608,
        "instance extension remains below EEL memory ceiling");
}
