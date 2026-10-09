static void popup_integration_tests(Host &h) {
  h.run("panic_pending=0;state=STATE_STOPPED;ui_scroll=0;store_event(0,0,144,"
        "60,90,0);");
  h.run("phrase_context=0;phrase_context_y=240;");
  h.frame();
  click(h, 20, 120);
  h.eq("phrase_context", -1, "outside dismisses phrase context");
  h.eq("state", h.val("STATE_STOPPED"),
       "phrase dismissal cannot hit underlying transport");
  h.eq("layer_count(0)", 1, "phrase dismissal cannot clear recorded data");
  h.run("phrase_context=0;phrase_context_y=240;");
  h.frame();
  click(h, 158, 250);
  h.eq("phrase_context", -1, "phrase popup X closes");
  h.eq("layer_count(0)", 1, "phrase popup X retains data");
  h.run("phrase_context=0;phrase_context_y=240;");
  h.frame();
  ysfx_gfx_add_key(h.f, 0, 27, true);
  h.frame();
  ysfx_gfx_add_key(h.f, 0, 27, false);
  h.frame();
  h.eq("phrase_context", -1, "ESC dismisses phrase context");
  h.run(
      "controller_assign_ti=param_ti(0,EXP_T_LEVEL);controller_assign_x=600;"
      "controller_assign_y=300;mem[exp_assign_addr(controller_assign_ti)]=2;");
  h.frame();
  click(h, 775, 310);
  h.eq("controller_assign_ti", -1, "assignment popup X closes");
  h.eq("mem[exp_assign_addr(param_ti(0,EXP_T_LEVEL))]", 2,
       "assignment dismissal retains mapping");
  h.run("ui_scroll=500;options_open=1;learn_start(SW_COUNT);");
  h.frame();
  click(h, 980, 121);
  h.eq("options_open", 0, "OPTIONS X remains usable after scrolling");
  h.eq("controller_learn", -1, "scrolled OPTIONS dismissal cancels Learn");
  h.run("ui_i_delete_slot=0;ui_i_delete_id=1;");
  h.frame();
  ysfx_gfx_add_key(h.f, 0, 27, true);
  h.frame();
  ysfx_gfx_add_key(h.f, 0, 27, false);
  h.frame();
  h.eq("ui_i_delete_slot", -1, "ESC dismisses instrument delete confirmation");
  h.eq("mem[I_EXISTS_BASE]", 1, "delete ESC retains instrument");
}
