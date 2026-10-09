// A single host block must drain all queued MIDI, including paired releases.
void midi_burst_tests(Host &h) {
  h.run("gmem[0]=0;panic_pending=0;state=STATE_STOPPED;");
  h.block();
  h.events();
  auto queue = [&](int status, int note, int value, unsigned offset) {
    uint8_t data[] = {uint8_t(status), uint8_t(note), uint8_t(value)};
    ysfx_midi_event_t e{};
    e.size = 3;
    e.data = data;
    e.offset = offset;
    check(ysfx_send_midi(h.f, &e), "enqueue same-block MIDI burst");
  };
  for (int pitch : {60, 64, 67})
    queue(144, pitch, 90, 0);
  for (int pitch : {60, 64, 67})
    queue(128, pitch, 0, 96);
  h.block();
  auto events = h.events();
  check(events.size() == 6, "all chord attacks and releases survive one block");
  if (events.size() == 6)
    for (unsigned i = 0; i < 6; ++i) {
      check(events[i][0] == (i < 3 ? 144 : 128),
            "burst retains Note On/Off order");
      check(events[i][1] == (i % 3 == 0   ? 60
                             : i % 3 == 1 ? 64
                                          : 67),
            "burst retains independent pitches");
    }
  h.eq("mem[engine_addr(PARAM_ACTIVE_BASE,0)]", 0,
       "chord burst leaves no held source notes");
  h.run("mem[engine_addr(INST_IN_BASE,0)]=1;mem[engine_addr(INST_OUT_BASE,0)]="
        "1;mem[engine_addr(INST_ENABLED_BASE,1)]=1;mem[engine_addr(INST_IN_"
        "BASE,1)]=2;mem[engine_addr(INST_OUT_BASE,1)]=2;");
  h.block();
  h.events();
  queue(144, 60, 90, 0);
  queue(145, 64, 90, 32);
  queue(128, 60, 0, 64);
  queue(129, 64, 0, 96);
  h.block();
  events = h.events();
  check(events.size() == 4,
        "two Instruments receive every event in the same block");
  if (events.size() == 4)
    for (unsigned i = 0; i < 4; ++i)
      check(events[i][0] == (i == 0   ? 144
                             : i == 1 ? 145
                             : i == 2 ? 128
                                      : 129),
            "same-block routing retains channel identity");
  h.eq("mem[engine_addr(PARAM_ACTIVE_BASE,0)]", 0,
       "first Instrument release ownership balanced");
  h.eq("mem[engine_addr(PARAM_ACTIVE_BASE,1)]", 0,
       "second Instrument release ownership balanced");
  h.run("learn_start(SW_COUNT);");
  queue(176, 8, 80, 0);
  queue(144, 70, 90, 32);
  queue(128, 70, 0, 64);
  h.block();
  events = h.events();
  check(events.size() == 2, "Learn consumes its event and continues draining "
                            "subsequent performance MIDI");
  h.eq("mem[CONTROLLER_CC_BASE]", 8, "burst Learn captures only exact target");
  h.eq("mem[CONTROLLER_CC_BASE+1]", -1,
       "burst Learn leaves other controller unassigned");
  h.eq("sw_learn", -1, "burst Learn exits after capture");
}
