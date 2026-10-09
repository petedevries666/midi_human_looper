// Actual shared EEL scheduler and existing output ownership, not a math model.
static void scheduled_event_tests(Host &h) {
  h.run("gmem[0]=0;panic_pending=0;state=STATE_STOPPED;slider9=1;");
  h.block();
  h.events();
  struct Message {
    unsigned offset;
    int status, note, value;
  };
  auto messages = [&]() {
    std::vector<Message> result;
    ysfx_midi_event_t e{};
    while (ysfx_receive_midi(h.f, &e))
      if (e.size == 3)
        result.push_back({e.offset, e.data[0], e.data[1], e.data[2]});
    return result;
  };
  auto pair = [&](int instrument, int channel, int note, unsigned on,
                  unsigned off, int stage = 6) {
    std::string s = "scheduled_pair(" + std::to_string(instrument) +
                    ",0,scheduled_clock+" + std::to_string(on) +
                    ",scheduled_clock+" + std::to_string(off) + "," +
                    std::to_string(channel) + "," + std::to_string(note) +
                    ",100," + std::to_string(stage) + ")";
    return h.eval(s);
  };
  check(pair(0, 1, 60, 16, 200) == 1, "atomic pair admission");
  h.block();
  auto first = messages();
  check(first.size() == 1 && first[0].offset == 16 && first[0].status == 145,
        "exact delayed channel attack");
  h.run("mem[INST_OUT_BASE]=16;mem[INST_TRANSPOSE_BASE]=36;");
  h.block();
  auto second = messages();
  check(second.size() == 1 && second[0].offset == 72 &&
            second[0].status == 129 && second[0].note == 60,
        "Note Off keeps captured channel/pitch after parameter edits");
  h.eq("scheduled_voice_count", 0, "completed pair reclaims voice");
  h.eq("scheduled_heap_count", 0, "completed pair reclaims queue");
  h.eq("mem[engine_addr(PARAM_ACTIVE_BASE,0)]", 0, "pair releases edit lease");
  h.run("mem[INST_OUT_BASE]=0;mem[INST_TRANSPOSE_BASE]=0;");
  // A pair at the right block edge is not emitted early. Zero-duration ties are
  // On then Off.
  check(pair(0, 2, 61, 128, 128) == 1,
        "zero-duration pair admitted atomically");
  h.block();
  check(messages().empty(), "right-edge event waits for next block");
  h.block();
  auto tied = messages();
  check(tied.size() == 2 && tied[0].offset == 0 && tied[1].offset == 0 &&
            tied[0].status == 146 && tied[1].status == 130,
        "stable same-time attack/release order");
  check(pair(0, 0, 62, 0, 100) == 1 && pair(0, 0, 62, 0, 200) == 1,
        "overlapping same-pitch pairs accepted");
  h.block();
  auto overlap = messages();
  check(
      overlap.size() == 2,
      "first repeated-pitch release is suppressed while another owner sounds");
  h.block();
  auto last = messages();
  check(last.size() == 1 && last[0].status == 128 && last[0].offset == 72,
        "last repeated-pitch owner releases exact note");
  // Heap order with unequal offsets and reversed admission order.
  for (int i = 0; i < 48; ++i)
    check(pair(0, i % 16, 40 + i, 47 - i, 64 + 47 - i) == 1,
          "polyphonic heap admission");
  h.block();
  auto poly = messages();
  check(poly.size() == 96, "all chord attacks and releases survive");
  for (unsigned i = 1; i < poly.size(); ++i)
    check(poly[i - 1].offset <= poly[i].offset,
          "heap emits chronological offsets");
  h.eq("scheduled_heap_count", 0, "polyphonic heap fully drained");
  // Capacity rejects a whole pair, retaining every reserved release.
  for (int i = 0; i < 256; ++i)
    check(pair(0, i % 16, i % 128, 0, 512) == 1,
          "bounded pool reserves matching release");
  check(pair(0, 0, 90, 1, 513) == 0, "full queue rejects whole pair");
  h.eq("scheduled_heap_count", 512, "queue stays at fixed bound");
  h.block();
  messages();
  h.run("test_schedule_command=1;");
  h.block();
  auto canceled = messages();
  check(canceled.size() == 128,
        "cancel releases each sounding channel/pitch once");
  for (auto &event : canceled)
    check((event.status & 240) == 128, "cancel emits releases only");
  h.eq("scheduled_heap_count", 0, "cancel compacts future heap");
  h.eq("scheduled_voice_count", 0, "cancel reclaims all voices");
  h.eq("mem[engine_addr(PARAM_ACTIVE_BASE,0)]", 0,
       "cancel releases all edit leases");
  check(pair(0, 0, 70, 0, 512) == 1, "voice can be reused");
  h.block();
  messages();
  h.run("test_schedule_command=2;");
  h.block();
  messages(); // leave stale heap node intentionally
  check(pair(0, 0, 71, 0, 700) == 1, "generation protects reused voice slot");
  h.block();
  messages();
  for (int i = 0; i < 4; ++i) {
    h.block();
    messages();
  }
  h.eq("scheduled_voice_count", 1, "old release cannot terminate reused voice");
  h.block();
  messages();
  h.eq("scheduled_voice_count", 0, "new generation receives its own release");
  check(pair(0, 0, 60, 0, 200, 0) == 0,
        "unsupported downstream continuation is rejected, never bypassed");
  h.run("mem[INST_TRANSFORM_COUNT_BASE]=1;mem[INST_TRANSFORM_TYPE_BASE]=5;mem["
        "INST_ARP_ENABLED_BASE]=1;");
  check(pair(0, 0, 60, 0, 100) == 0,
        "unsafe ARP ownership is explicitly rejected in foundation");
  h.run("mem[INST_ARP_ENABLED_BASE]=0;mem[INST_TRANSFORM_COUNT_BASE]=0;");
  check(
      h.eval(
          "scheduled_pair(0,0,scheduled_clock,scheduled_clock+100,0,60,0,6)") ==
          0,
      "velocity-zero is not admitted as an attack");
  check(pair(0, 16, 60, 0, 100) == 0, "invalid channel rejected");
  check(pair(0, 0, 128, 0, 100) == 0, "invalid pitch rejected");
  check(h.eval("scheduled_pair(0,0,scheduled_clock,scheduled_clock+srate*60+1,"
               "0,60,100,6)") == 0,
        "absolute scheduling horizon is bounded");
  check(pair(0, 5, 73, 16, 200) == 1, "tempo-independent absolute pair");
  h.run("tempo=60;");
  h.block();
  auto slow = messages();
  check(slow.size() == 1 && slow[0].offset == 16,
        "tempo change does not move absolute attack");
  h.run("tempo=180;");
  h.block();
  auto fast = messages();
  check(fast.size() == 1 && fast[0].offset == 72,
        "tempo change does not move reserved release");
  check(pair(0, 0, 74, 1000, 1200) == 1, "future attack admitted");
  h.run("mem[INST_ENABLED_BASE]=0;");
  h.block();
  check(messages().empty(),
        "bypass cancels pending attack without sounding it");
  h.eq("scheduled_heap_count", 0, "bypass discards canceled pending nodes");
  h.run("mem[INST_ENABLED_BASE]=1;");
  // A live attack can sound before its source Note Off provides the duration.
  double token = h.eval("scheduled_start(0,0,scheduled_clock+16,6,77,100,6)");
  check(token > 0, "live duration reserves release atomically");
  h.block();
  auto unsealed = messages();
  check(unsealed.size() == 1 && unsealed[0].offset == 16,
        "live attack emits before duration is sealed");
  check(h.eval("scheduled_seal(0,0," + std::to_string(token) +
               ",scheduled_clock+72)") == 1,
        "source release seals reserved note");
  check(h.eval("scheduled_seal(0,0," + std::to_string(token) +
               ",scheduled_clock+80)") == 0,
        "source release cannot seal twice");
  h.block();
  auto sealed = messages();
  check(sealed.size() == 1 && sealed[0].offset == 72 &&
            sealed[0].status == 134 && sealed[0].note == 77,
        "sealed duration releases exact live note");
  token = h.eval("scheduled_start(0,0,scheduled_clock+16,6,78,100,6)");
  h.block();
  messages();
  check(h.eval("scheduled_seal(0,1," + std::to_string(token) +
               ",scheduled_clock)") == 0,
        "different module cannot seal another owner");
  check(h.eval("scheduled_seal(0,0," + std::to_string(token) + ",0)") == 1,
        "late source release clamps safely");
  h.block();
  auto late = messages();
  check(late.size() == 1 && late[0].offset == 0 && late[0].status == 134,
        "late release occurs at next block start");
  token = h.eval("scheduled_start(0,0,scheduled_clock,6,79,100,6)");
  h.block();
  messages();
  h.run("scheduled_clock+=srate*60;");
  h.block();
  auto watchdog = messages();
  check(watchdog.size() == 1 && watchdog[0].status == 134 &&
            watchdog[0].note == 79,
        "missing source release expires through bounded watchdog");
  h.eq("scheduled_voice_count", 0, "watchdog reclaims abandoned live voice");
  auto payload = h.payload();
  check(pair(0, 0, 72, 0, 1000) == 1, "pending runtime created");
  check(h.payload() == payload, "scheduled runtime never enters patch payload");
  h.run("panic_pending=1;");
  h.block();
  messages();
  h.eq("scheduled_heap_count", 0, "PANIC clears future echoes");
  h.eq("scheduled_voice_count", 0, "PANIC clears sounding echoes");
  // Instrument deletion cancels before slot reuse, leaving another Instrument
  // untouched.
  h.run("test_gi=i_add();mem[engine_addr(INST_ENABLED_BASE,test_gi)]=1;");
  int gi = int(h.val("test_gi"));
  check(pair(gi, 3, 75, 0, 1000) == 1 && pair(0, 4, 76, 0, 1000) == 1,
        "independent Instrument voices");
  h.block();
  messages();
  h.run("test_schedule_command=3;");
  h.block();
  messages();
  h.eq("scheduled_voice_count", 1, "delete cancels only selected Instrument");
  check(pair(gi, 3, 80, 1000, 1200) == 0,
        "deleted Instrument cannot admit pairs");
  h.run("test_gi=i_add();mem[engine_addr(INST_ENABLED_BASE,test_gi)]=1;");
  gi = int(h.val("test_gi"));
  check(pair(gi, 3, 80, 1000, 1200) == 1,
        "replacement Instrument owns fresh pending pair");
  h.run("mem[engine_addr(INST_ENABLED_BASE,test_gi)]=0;");
  h.block();
  messages();
  h.eq("scheduled_heap_count", 1,
       "partial invalid-owner cancellation immediately compacts its nodes");
  h.eq("scheduled_voice_count", 1,
       "invalid-owner cleanup leaves other Instrument sounding");
  h.run("test_schedule_command=4;");
  h.block();
  messages();
  h.eq("scheduled_voice_count", 0, "phrase STOP cancels delayed tails");
}
