static void instrument_voice_tests(Host &h) {
  h.run("panic_pending=0;state=STATE_STOPPED;mem[INST_ENABLED_BASE]=0;i_add();"
        "mem[engine_addr(INST_ENABLED_BASE,3)]=1;mem[engine_addr(INST_OUT_BASE,"
        "3)]=2;");
  h.midi(144, 42, 90);
  h.events();
  h.run("i_submit(2,3,4);");
  h.block();
  h.events();
  h.run("i_submit(1,0,0);");
  h.block();
  h.events();
  h.run("mem[engine_addr(INST_ENABLED_BASE,3)]=1;mem[engine_addr(INST_OUT_BASE,"
        "3)]=2;");
  h.midi(144, 42, 95);
  h.events();
  h.midi(128, 42, 0);
  auto events = h.events();
  for (auto e : events)
    check(!(e[0] == 129 && e[1] == 42),
          "late pre-delete physical release cannot cut replacement note");
  h.eq("mem[engine_addr(SW_LIVE_OUT_BASE,3*2048+128+42)]", 1,
       "replacement retains its own live output owner");
  h.midi(128, 42, 0);
  events = h.events();
  bool off = false;
  for (auto e : events)
    if (e[0] == 129 && e[1] == 42)
      off = true;
  check(off, "replacement releases on its own physical Note Off");
  // A release received while the old slot is absent must also drain quarantine.
  h.midi(144, 43, 90);
  h.events();
  h.run("i_submit(2,3,5);");
  h.block();
  h.events();
  h.midi(128, 43, 0);
  h.events();
  h.run("i_submit(1,0,0);");
  h.block();
  h.events();
  h.run("mem[engine_addr(INST_ENABLED_BASE,3)]=1;mem[engine_addr(INST_OUT_BASE,"
        "3)]=2;");
  h.midi(144, 43, 90);
  h.events();
  h.midi(128, 43, 0);
  events = h.events();
  off = false;
  for (auto e : events)
    if (e[0] == 129 && e[1] == 43)
      off = true;
  check(off, "absent-slot release does not poison future ownership");
  // Same-phrase overlapping voices have independent creation-time instrument
  // IDs.
  h.run("mem[COUNT_BASE]=0;store_event(0,0,144,60,90,0);store_event(0,512,128,"
        "60,0,0);"
        "mem[LEN_BASE]=10000;mem[MODE_BASE]=1;mem[DECAY_BASE]=1;trigger_"
        "request=0;");
  h.block();
  h.events();
  h.eq("mem[VOICE_INST_IDS_BASE+3]", 6,
       "voice captures stable destination instrument ID");
  h.run("i_submit(2,3,6);");
  h.block();
  h.events();
  h.run("i_submit(1,0,0);");
  h.block();
  h.events();
  h.run("mem[engine_addr(INST_ENABLED_BASE,3)]=1;mem[engine_addr(INST_OUT_BASE,"
        "3)]=2;trigger_request=0;");
  h.block();
  h.events();
  h.eq("mem[VOICE_INST_IDS_BASE+INST_CAP+3]", 7,
       "overlapping new voice owns replacement ID");
  h.block();
  events = h.events();
  for (auto e : events)
    check(!(e[0] == 129 && e[1] == 60),
          "old voice's delayed Note Off cannot release replacement voice");
  h.eq("mem[NOTE_REF_BASE+128+60]", 1,
       "old voice cannot decrement new voice's ownership");
  h.eq("mem[engine_addr(PARAM_ACTIVE_BASE,3)]", 1,
       "old voice cannot decrement replacement input count");
  for (int i = 0; i < 5; ++i) {
    h.block();
    events = h.events();
  }
  h.eq("mem[NOTE_REF_BASE+128+60]", 0,
       "new voice completes with balanced Note On/Off");
  h.run(
      "mem[engine_addr(SW_MODULE_BASE,3*TRANSFORM_TYPES)]=-1;i_submit(2,3,7);");
  h.block();
  h.events();
  h.eq("mem[engine_addr(SW_MODULE_BASE,3*TRANSFORM_TYPES)]", -999,
       "deletion clears stale module action for reused instrument slot");
  h.run("i_submit(1,0,0);");
  h.block();
  h.events();
  h.run("mem[engine_addr(INST_ENABLED_BASE,3)]=1;mem[engine_addr(INST_OUT_BASE,"
        "3)]=2;");
  h.midi(144, 44, 90);
  h.events();
  h.run("i_submit(2,3,8);");
  h.block();
  h.events();
  h.run("learn_start(SW_COUNT);");
  h.midi(128, 44, 0);
  h.events();
  h.eq("mem[I_QUARANTINE_BASE+3*2048+44]", 0,
       "Learn-consumed release still drains instrument quarantine");
  h.run("learn_cancel();i_submit(1,0,0);");
  h.block();
  h.events();
  h.run("mem[engine_addr(INST_ENABLED_BASE,3)]=1;mem[engine_addr(INST_OUT_BASE,"
        "3)]=2;");
  h.midi(144, 44, 90);
  h.events();
  h.midi(128, 44, 0);
  events = h.events();
  off = false;
  for (auto e : events)
    if (e[0] == 129 && e[1] == 44)
      off = true;
  check(off, "relearning elsewhere cannot poison replacement Note Off");
  h.midi(144, 45, 90);
  h.events();
  h.run("i_submit(2,3,9);");
  h.block();
  h.events();
  h.run("sw_clock+=11*srate;");
  h.block();
  h.events();
  h.eq("mem[I_QUARANTINE_BASE+3*2048+45]", 0,
       "missing hardware release quarantine expires after ten seconds");
  h.run("mem[I_FALLBACK_SUSTAIN_BASE]=127;panic_pending=1;");
  h.block();
  h.events();
  h.eq("mem[I_FALLBACK_SUSTAIN_BASE]", 0,
       "PANIC clears passthrough sustain ownership");
  h.run("mem[NOTE_REF_BASE+60]=1;mem[ARP_HELD_COUNT_BASE+60]=1;edit_name_type="
        "2;");
  h.run("last_trigger_layer=0;trigger_request=0;");
  h.run("external_patch_save_request(1);mem[VOICE_ACTIVE_BASE]=1;mem[VOICE_"
        "LAYER_BASE]=0;mem[VOICE_POS_BASE]=0;mem[VOICE_GAIN_BASE]=1;mem[VOICE_"
        "TIME_BASE]=1;gmem[0]=3;");
  h.block();
  events = h.events();
  bool unexpected = false;
  for (auto e : events)
    if ((e[0] & 240) == 144 && e[2] > 0)
      unexpected = true;
  check(!unexpected,
        "LOAD cannot replay stale voice events from the previous patch");
  h.eq("mem[VOICE_ACTIVE_BASE]", 0,
       "patch LOAD cancels previous runtime voices");
  h.eq("edit_name_type", 0, "patch LOAD closes old name editing focus");
  h.eq("mem[NOTE_REF_BASE+60]", 0,
       "patch LOAD clears previous ONCE ownership references");
  h.eq("mem[ARP_HELD_COUNT_BASE+60]", 0,
       "patch LOAD clears previous ARP input ownership");
  h.run("mem[INST_ENABLED_BASE]=1;mem[INST_ARP_ENABLED_BASE]=1;transform_add(0,"
        "5);");
  h.block();
  h.events();
  h.midi(144, 65, 90);
  h.events();
  h.run("sw_submit(0,2,0,1);sw_submit(0,2,14,SW_PANIC);sw_submit(0,0,0,0);");
  h.block();
  events = h.events();
  unexpected = false;
  for (auto e : events)
    if ((e[0] & 240) == 144 && e[2] > 0)
      unexpected = true;
  check(!unexpected, "explicit PANIC cannot re-sound a held live arpeggiator");
  h.eq("mem[ARP_HELD_COUNT_BASE+65]", 0,
       "explicit PANIC clears live ARP source ownership");
}
