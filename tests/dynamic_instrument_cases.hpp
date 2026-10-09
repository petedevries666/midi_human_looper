static void dynamic_instrument_tests(Host &h) {
  h.run("panic_pending=0;ui_scroll=0;state=STATE_STOPPED;");
  click(h, 880, 445);
  h.eq("mem[I_EXISTS_BASE+3]", 1, "ADD INSTRUMENT publishes fourth full panel");
  h.eq("mem[I_IDS_BASE+3]", 4, "fourth instrument stable ID");
  h.eq("mem[engine_addr(INST_LEVEL_BASE,3)]", 127,
       "independent default volume");
  h.run("transform_add(3,1);transform_add(3,1);transform_add(3,6);transform_"
        "add(3,6);");
  h.block();
  h.events();
  h.eq("mem[engine_addr(INST_TRANSFORM_COUNT_BASE,3)]", 4,
       "new instrument owns its Transformer chain");
  h.run("mem[engine_addr(INST_TRANSPOSE_BASE,3)]=12;mem[cc_cfg(15)+2]=-5;"
        "mem[engine_addr(INST_ENABLED_BASE,3)]=1;mem[engine_addr(INST_OUT_BASE,"
        "3)]=2;"
        "mem[engine_addr(PARAM_MOD_CC_BASE,3)]=74;mem[engine_addr(INST_MOD_"
        "BASE,3)]=45;"
        "mem[cc_cfg(16)+1]=75;mem[cc_cfg(16)+2]=67;"
        "mem[exp_assign_addr(param_ti(3,EXP_T_LEVEL))]=1;ctrl_val0=.5;");
  h.block();
  auto cc = h.events();
  bool primary = false, extra = false;
  for (auto e : cc) {
    if (e[0] == 177 && e[1] == 74 && e[2] == 45)
      primary = true;
    if (e[0] == 177 && e[1] == 75 && e[2] == 67)
      extra = true;
  }
  check(primary && extra,
        "new panel's independent CC outputs reach its own channel");
  h.eq("mem[engine_addr(INST_LEVEL_BASE,3)]", 64,
       "new panel expression mapping works");
  h.eq("param_gi(param_ti(3,PARAM_RANGE_HIGH))", 3,
       "new primary expression identity");
  h.eq("param_gi(cc_ti(16,2))", 3, "new tertiary expression identity");
  h.midi(144, 60, 90);
  auto on = h.events();
  bool fourth = false;
  for (auto e : on)
    if (e[0] == 145 && e[1] == 67)
      fourth = true;
  check(fourth, "new panel serial transpose stack routes its own Note On");
  h.eq("mem[engine_addr(SW_LIVE_OUT_BASE,3*2048+128+67)]", 1,
       "new panel records output ownership");
  h.run("save_patch(1);i_submit(2,3,4);");
  h.block();
  auto off = h.events();
  bool release = false;
  for (auto e : off) {
    if (e[0] == 129 && e[1] == 67)
      release = true;
    check(!(e[0] == 128 && e[1] == 60),
          "remove does not release another instrument's note");
  }
  check(release, "remove releases selected instrument's active note");
  h.eq("mem[SW_LIVE_OUT_BASE+60]", 1,
       "other instrument ownership survives deletion");
  h.midi(128, 60, 0);
  h.events();
  h.run("current_patch=2;load_patch(1);");
  h.block();
  h.events();
  h.eq("mem[I_EXISTS_BASE+3]", 1, "patch restores additional visible panel");
  h.eq("mem[I_IDS_BASE+3]", 4, "patch preserves stable instrument identity");
  h.eq("mem[cc_cfg(16)+1]", 75, "patch preserves new CC instance assignment");
  h.eq("mem[exp_assign_addr(param_ti(3,EXP_T_LEVEL))]", 1,
       "patch preserves appended expression mapping");
  h.run("i_remove(3,4);transform_add(3,1);i_add();");
  h.block();
  h.events();
  h.eq("mem[I_IDS_BASE+3]", 5, "slot reuse receives fresh instrument ID");
  h.eq("mem[engine_addr(INST_TRANSFORM_COUNT_BASE,3)]", 0,
       "stale queued Transformer command cannot edit replacement");
  h.run("mem[engine_addr(INST_ENABLED_BASE,3)]=1;mem[engine_addr(INST_OUT_BASE,"
        "3)]=1;");
  h.midi(144, 61, 90);
  h.events();
  h.run("i_submit(2,3,5);");
  h.block();
  off = h.events();
  for (auto e : off)
    check(!(e[0] == 128 && e[1] == 61),
          "shared destination pitch stays held by surviving panel");
  h.midi(128, 61, 0);
  off = h.events();
  release = false;
  for (auto e : off)
    if (e[0] == 128 && e[1] == 61)
      release = true;
  check(release, "last surviving owner sends Note Off");
  h.run("k=0;loop(5,i_add();k+=1;);");
  h.eq("i_add()", 8, "bounded capacity rejects ninth instrument safely");
  for (int gi = 3; gi < 8; ++gi) {
    std::string g = std::to_string(gi);
    h.run("mem[engine_addr(INST_LEVEL_BASE," + g + ")]=70+" + g +
          ";mem[exp_count_addr(param_ti(" + g + ",PARAM_TRANSPOSE))]=3;");
    h.eq("param_gi(param_ti(" + g + ",PARAM_TRANSPOSE))", gi,
         "all panels own independent primary parameters");
  }
  h.run("save_patch(2);i_remove(7,mem[I_IDS_BASE+7]);current_patch=1;load_"
        "patch(2);");
  h.block();
  h.events();
  h.eq("mem[I_EXISTS_BASE+7]", 1, "second patch restores eighth panel");
  h.eq("mem[engine_addr(INST_LEVEL_BASE,7)]", 77,
       "eighth panel configuration survives patch switching");
  h.run("ui_scroll=0;ui_i_delete_slot=-1;");
  h.frame();
  click(h, 1004, 473);
  h.eq("ui_i_delete_slot", 0, "panel X opens safe delete confirmation");
  click(h, 100, 100);
  h.eq("ui_i_delete_slot", -1, "outside dismisses instrument confirmation");
  h.eq("mem[I_EXISTS_BASE]", 1, "dismissal does not remove panel");
}
