static void phrase_play_tests(Host &h) {
  h.run("sw_defaults();sw_runtime_reset();panic_pending=0;state=STATE_STOPPED;"
        "mem[INST_ENABLED_BASE]=1;mem[INST_ENABLED_BASE+1]=0;mem[INST_ENABLED_"
        "BASE+2]=0;mem[INST_TRANSFORM_COUNT_BASE]=0;"
        "mem[COUNT_BASE]=0;store_event(0,0,144,50,90,0);store_event(0,500,128,"
        "50,0,0);mem[LEN_BASE]=1000;mem[MODE_BASE]=1;"
        "mem[COUNT_BASE+1]=0;store_event(1,0,144,51,90,0);mem[LEN_BASE+1]=1000;"
        "mem[MODE_BASE+1]=1;");
  // The keyboard icon immediately before M/S starts phrase-specific Learn.
  click(h, 235, 204);
  h.eq("phrase_note_learn", 0, "PHRASES icon targets Phrase 1");
  h.midi(0x92, 72, 90);
  check(h.events().empty(), "learning phrase input stays silent");
  h.midi(0x82, 72, 0);
  check(h.events().empty(), "learn capture release stays silent");
  h.eq("mem[PHRASE_NOTE_BASE]", 72, "Phrase 1 assignment stored");
  h.eq("mem[PHRASE_NOTE_BASE+1]", -1, "other phrase assignment unchanged");
  h.eq("mem[sw_cfg(0)+2]", 0,
       "learning phrase leaves Smart Switch assignment unchanged");
  h.midi(0x92, 72, 1);
  auto e = h.events();
  int ons = 0;
  bool leaked = false;
  for (auto m : e) {
    if (m[0] == 144 && m[1] == 50)
      ons++;
    if (m[1] == 72)
      leaked = true;
  }
  check(ons == 1 && !leaked,
        "Helix press immediately plays Phrase 1, with no command MIDI leak");
  h.eq("state", 4, "phrase play does not enter RECORD");
  h.eq("overdub_armed", 0, "phrase play does not arm OVERDUB");
  h.eq("overdub_active", 0, "phrase play does not start OVERDUB");
  h.midi(0x82, 72, 0);
  e = h.events();
  leaked = false;
  for (auto m : e)
    if (m[1] == 72)
      leaked = true;
  check(!leaked, "phrase trigger release consumed");
  click(h, 235, 242);
  h.midi(0x92, 73, 90);
  h.events();
  h.midi(0x82, 73, 0);
  h.events();
  h.eq("mem[PHRASE_NOTE_BASE]", 72, "learning Phrase 2 preserves Phrase 1");
  h.midi(0x92, 73, 90);
  e = h.events();
  ons = 0;
  for (auto m : e)
    if (m[0] == 144 && m[1] == 51)
      ons++;
  check(ons == 1, "second phrase has independent playback input");
  h.midi(0x82, 73, 0);
  h.events();
  h.run(
      "overdub_layer=0;overdub_armed=1;overdub_wait_note=1;overdub_active=0;");
  h.midi(0x92, 72, 90);
  h.events();
  h.eq("overdub_active", 0,
       "play command does not start explicitly armed overdub");
  h.eq("overdub_armed", 1, "play command preserves separate overdub arm");
  h.midi(0x82, 72, 0);
  h.events();
  h.run("overdub_armed=0;overdub_wait_note=0;record_layer=15;state=STATE_"
        "RECORDING;");
  h.midi(0x92, 72, 90);
  h.events();
  h.midi(0x82, 72, 0);
  h.events();
  h.eq("layer_count(15)", 0,
       "trigger press/release never enter phrase recording");
  h.run("state=STATE_STOPPED;mem[MODE_BASE]=2;");
  h.midi(0x92, 72, 90);
  h.events();
  h.eq("mem[HOLD_ACTIVE_BASE]", 1, "learned HOLD input uses existing playback");
  h.midi(0x82, 72, 0);
  h.events();
  h.run("mem[MODE_BASE]=0;loop_len_samples=1000;play_sample_pos=0;");
  h.midi(0x92, 72, 90);
  e = h.events();
  h.eq("state", 3, "learned LOOP input starts playback");
  h.eq("mem[TRIG_BASE]", 1, "learned LOOP enables corresponding phrase");
  h.midi(0x82, 72, 0);
  h.events();
  h.run("state=STATE_STOPPED;external_patch_save_request(1);mem[PHRASE_NOTE_"
        "BASE]=-1;mem[PHRASE_NOTE_BASE+1]=-1;external_patch_apply();");
  h.eq("mem[PHRASE_NOTE_BASE]", 72, "patch restores Phrase 1 input");
  h.eq("mem[PHRASE_NOTE_BASE+1]", 73,
       "patch restores independent Phrase 2 input");
  h.eq("mem[learn_phrase_channel(0)]", 3,
       "patch restores exact phrase MIDI channel");
}
