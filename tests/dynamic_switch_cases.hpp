static void dynamic_switch_tests(Host &h) {
  for (int i=0;i<4;++i) {
    h.eq("mem[sw_committed_cfg("+std::to_string(i)+")+20]",1,"fresh startup publishes every legacy switch");
    h.eq("mem[sw_committed_cfg("+std::to_string(i)+")+21]",i+1,"fresh startup preserves stable switch IDs");
  }
  h.run(
      "sw_defaults();sw_runtime_reset();panic_pending=0;state=STATE_STOPPED;"
      "slider9=1;"
      "mem[INST_ENABLED_BASE]=1;mem[INST_ENABLED_BASE+1]=0;mem[INST_ENABLED_"
      "BASE+2]=0;"
      "mem[INST_TRANSFORM_COUNT_BASE]=0;mem[INST_OUT_BASE]=1;ui_scroll=510;"
      "k=0;loop(5,mem[COUNT_BASE+k]=0;store_event(k,0,144,70+k,80,0);"
      "store_event(k,256,128,70+k,0,0);mem[LEN_BASE+k]=8000;mem[MODE_BASE+k]=1;"
      "mem[DECAY_BASE+k]=1;k+=1;);k=0;loop(4,b=sw_cfg(k);mem[b]=1;mem[b+2]=1;"
      "mem[b+3]=2;mem[b+4]=60+k;mem[b+11]=1;mem[b+SW_LIST]=k;k+=1;);");
  h.frame();
  click(h, 90, 1108);
  h.frame();
  h.eq("sw_edit_target", 4, "ADD creates fifth independent switch editor");
  h.eq("mem[sw_cfg(4)+20]", 0, "new switch remains an uncommitted draft");
  sw_editor_click(h, 320, 1046);
  h.midi(146, 64, 100);
  check(h.events().empty(), "fifth Learn capture is silent");
  h.midi(130, 64, 0);
  h.events();
  h.eq("mem[SW_DRAFT_BASE+2]", 1, "fifth draft captures exact MIDI kind");
  h.eq("mem[sw_cfg(4)+2]", 0,
       "Learn cannot leak draft assignment into runtime");
  h.run("sw_submit(4,3,4,0);");
  h.block();
  h.events();
  sw_editor_done(h);
  h.eq("mem[sw_cfg(4)+20]", 1, "DONE publishes fifth switch to actual engine");
  h.eq("mem[sw_cfg(4)+21]", 5, "new switch receives stable unique ID");
  for (int i = 0; i < 5; i++) {
    double other = h.eval("mem[sw_rt(" + std::to_string((i + 1) % 5) + ")+12]");
    h.midi(146, 60 + i, 100);
    auto events = h.events();
    bool selected = false;
    for (auto e : events)
      if ((e[0] & 240) == 144) {
        check(e[1] == 70 + i, "input triggers only corresponding phrase");
        selected = true;
      }
    check(selected, "all five actual engine switches operate");
    h.midi(130, 60 + i, 0);
    h.events();
    h.eq("mem[sw_rt(" + std::to_string((i + 1) % 5) + ")+12]", other,
         "switch capture/action isolation");
  }
  open_sw_editor(h, 4);
  sw_editor_click(h, 850, 1018);
  h.eq("mem[SW_DRAFT_BASE+1]", 1, "TYPE edits the selected draft");
  h.eq("mem[sw_cfg(4)+1]", 0, "TYPE never changes playing switch before DONE");
  sw_editor_cancel(h);
  h.eq("mem[sw_cfg(4)+1]", 0, "CANCEL discards changed switch type");
  open_sw_editor(h, 4);
  sw_editor_click(h, 320, 1046);
  h.midi(146, 80, 100);
  h.events();
  h.midi(130, 80, 0);
  h.events();
  sw_editor_cancel(h);
  h.eq("mem[sw_cfg(4)+4]", 64,
       "cancel after successful Learn preserves old assignment");
  h.eq("sw_learn", -1, "cancel leaves no Learn listener");
  // Conflict acceptance must also remain uncommitted until DONE.
  open_sw_editor(h, 4);
  sw_editor_click(h, 320, 1046);
  h.midi(146, 60, 100);
  h.events();
  h.eq("learn_conflict", 0,
       "draft warns before reassigning existing MIDI input");
  click(h, 410, 385);
  h.eq("mem[sw_cfg(0)+2]", 1,
       "REASSIGN confirmation does not mutate committed other switch");
  h.midi(130, 60, 0);
  h.events();
  sw_editor_cancel(h);
  h.eq("mem[sw_cfg(0)+2]", 1, "cancel reassign preserves previous owner");
  h.eq("mem[sw_cfg(4)+4]", 64, "cancel reassign preserves edited switch");
  open_sw_editor(h, 4);
  sw_editor_click(h, 320, 1046);
  h.midi(146, 60, 100);
  h.events();
  click(h, 410, 385);
  h.midi(130, 60, 0);
  h.events();
  sw_editor_done(h);
  h.eq("mem[sw_cfg(0)+2]", 0,
       "DONE deliberately reassigns exactly the conflicting MIDI input");
  h.eq("mem[sw_cfg(0)+11]", 1,
       "reassignment preserves previous owner's phrase list");
  h.eq("mem[sw_cfg(4)+4]", 60,
       "DONE commits learned candidate to exact edited switch");
  open_sw_editor(h, 4);
  h.run("sw_submit(4,1,1,64);");
  h.block();
  h.events();
  sw_editor_done(h);
  h.run("sw_assign(0,1,2,60,127,0);");
  double position = h.eval("mem[sw_rt(4)+7]");
  open_sw_editor(h, 4);
  h.run("mem[SW_DRAFT_BASE+SW_NAME]=70;");
  sw_editor_done(h);
  h.eq("mem[sw_rt(4)+7]", position,
       "name-only DONE preserves live phrase cursor");
  open_sw_editor(h, 4);
  sw_editor_click(h, 320, 1046);
  // Outside-right dismissal cancels unfinished Learn and consumes the whole
  // frame.
  h.frame(825, 80, 2);
  h.frame(825, 80, 0);
  h.block();
  h.events();
  h.eq("ui_sw_editor_open", 0, "right outside dismisses Smart Switch editor");
  h.eq("sw_learn", -1, "outside dismissal cancels Learn");
  h.eq("options_open", 0, "dismissal cannot open underlying OPTIONS");
  open_sw_editor(h, 4);
  sw_editor_click(h, 320, 1046);
  ysfx_gfx_add_key(h.f, 0, 27, true);
  h.frame();
  ysfx_gfx_add_key(h.f, 0, 27, false);
  h.block();
  h.events();
  h.eq("ui_sw_editor_open", 0, "ESC discards Smart Switch editor");
  h.eq("sw_learn", -1, "ESC cancels Learn");
  // Deletion of a legacy record must preserve unrelated data embedded alongside
  // it.
  h.run("mem[sw_cfg(0)+24]=4;mem[sw_cfg(0)+25]=2;mem[CONTROLLER_CC_BASE]=21;"
        "mem[learn_phrase_channel(0)]=3;mem[phrase_time_addr(0)]=1.2;");
  h.midi(146, 60, 100);
  h.events();
  click(h, 242, 1068);
  h.frame();
  h.eq("ui_sw_delete_slot", 0,
       "card X opens deletion safeguard for exact slot");
  click(h, 350, int(h.val("ui_sw_delete_y")) + 90 - int(h.val("ui_scroll")));
  h.eq("mem[sw_cfg(0)+20]", 0, "DELETE removes only selected switch");
  h.eq("mem[sw_cfg(4)+21]", 5,
       "deleting earlier card preserves fifth stable ID");
  h.eq("mem[sw_cfg(0)+24]", 4,
       "switch deletion preserves expression channel metadata");
  h.eq("mem[learn_phrase_channel(0)]", 3,
       "switch deletion preserves phrase trigger channel");
  h.eq("phrase_time_ratio(0)", 1.2, "switch deletion preserves TIME DECAY");
  h.midi(130, 60, 0);
  check(h.events().empty(), "deleted held switch release is quarantined");
  h.run("sw_submit(0,14,0,0);");
  h.block();
  h.events();
  h.frame();
  h.eq("sw_edit_target", 0,
       "ADD reuses sparse free storage without compacting others");
  h.eq("mem[SW_DRAFT_BASE+21]", 6, "reused slot receives a fresh stable ID");
  sw_editor_cancel(h);
  h.eq("mem[sw_cfg(0)+20]", 0, "cancel new switch removes its draft entirely");
  // Restore five and exercise all practical engine slots, rejecting a
  // seventeenth.
  h.run("sw_submit(0,14,0,0);sw_queue_process();sw_commit_edit();"
        "j=0;loop(11,sw_submit(0,14,0,0);sw_queue_process();sw_commit_edit();j+"
        "=1;);");
  h.eq("mem[sw_cfg(15)+20]", 1,
       "sixteen slots are actual independently persisted engine records");
  h.run("sw_submit(0,14,0,0);sw_queue_process();");
  h.eq("ui_sw_editor_open", 0,
       "capacity exhaustion never creates a GUI-only switch");
  h.run("save_patch(1);mem[sw_cfg(15)+SW_NAME]=90;save_patch(2);"
        "current_patch=2;load_patch(1);");
  h.eq("mem[sw_cfg(15)+SW_NAME]", 0,
       "internal PATCH 1 restores dynamic switch tail");
  h.run("load_patch(2);");
  h.eq("mem[sw_cfg(15)+SW_NAME]", 90,
       "internal PATCH 2 preserves dynamic switch name");
  h.run("external_patch_save_request(2);sw_defaults();external_patch_apply();");
  h.eq("mem[sw_cfg(15)+SW_NAME]", 90,
       "external patch restores complete dynamic collection");
  h.eq("mem[sw_cfg(4)+21]", 5, "external patch preserves fifth stable ID");
  h.run("gmem[2]=5;gmem[3]=DS_LEGACY_PAYLOAD;external_patch_apply();");
  h.eq("io_status", 3,
       "schema5 migration accepted with preserved Transformer registry");
  h.eq("mem[sw_cfg(4)+20]", 0,
       "legacy patches receive four switches without invented extras");
}
