// The real Controller policy domain: no competing interpolation writer.
static void morph_engine_tests() {
  {
    Engine e;
    e.addTarget(1, .2);
    auto old = e.external(1, .2, 1000, 0);
    auto token = e.morph(1, 1, 2, 0);
    check(token && token != old, "recall replaces former owner once");
    e.tick(1);
    near(e.target(1)->effective, .6, "linear current-effective midpoint");
    check(!e.releaseExternal(1, old),
          "stale external release cannot cancel morph");
    auto next = e.morph(1, .2, 2, 1);
    near(e.target(1)->effective, .6, "interrupted morph starts without jump");
    check(next != token && !e.releaseExternal(1, token),
          "interrupted token retired");
    e.tick(2);
    near(e.target(1)->effective, .4,
         "interrupted ramp uses interpolated start");
    e.tick(3);
    near(e.target(1)->effective, .2, "exact final destination");
    check(!e.target(1)->owner && !e.target(1)->morphing,
          "completion retires ownership");
    check(e.morph(1, .8, 0, 3) != 0, "instant recall accepted");
    near(e.target(1)->effective, .8, "instant destination");
    check(!e.target(1)->owner, "instant recall leaves no stale owner");
  }
  {
    Engine e;
    e.addTarget(1, 0);
    e.addTarget(2, 1);
    std::array<Transition, 2> batch;
    batch[0].target = 1;
    batch[0].goal = 1;
    batch[0].seconds = 2;
    batch[1].target = 99;
    batch[1].goal = 0;
    batch[1].seconds = 2;
    auto token = e.target(1)->token;
    check(!e.morphBatch(batch.data(), 2, 10),
          "invalid batch rejected as a whole");
    check(e.target(1)->token == token && !e.target(1)->morphing,
          "invalid batch has no partial owner updates");
    check(e.tick(0), "invalid batch does not advance clock");
    batch[1].target = 1;
    check(!e.morphBatch(batch.data(), 2, 0),
          "duplicate targets rejected before commit");
    batch[1].target = 2;
    check(e.morphBatch(batch.data(), 2, 0), "coherent batch accepted");
    e.tick(1);
    near(e.target(1)->effective, .5, "first batch target midpoint");
    near(e.target(2)->effective, .5, "second batch target shares timestamp");
  }
  for (auto policy :
       {Takeover::Direct, Takeover::Pickup, Takeover::Glide, Takeover::Slew}) {
    Engine e;
    e.addTarget(1, 0);
    auto m = map(10, 20, 1, policy);
    m.glideSeconds = 1;
    m.slewPerSecond = .2;
    m.back = Return::Command;
    m.returnSeconds = 1;
    e.configure(m);
    e.morph(1, 1, 2, 0);
    e.tick(1);
    if (policy == Takeover::Pickup) {
      e.input(20, .1, 1);
      check(e.target(1)->morphing, "uncrossed Pickup preserves morph");
    }
    e.input(20, policy == Takeover::Pickup ? .5 : .9, 1);
    check(e.target(1)->owner == 10 && !e.target(1)->morphing,
          "physical mapping takes morph ownership");
    if (policy == Takeover::Glide || policy == Takeover::Slew)
      near(e.target(1)->effective, .5, "smoothed takeover begins without jump");
    e.tick(1.5);
    double expected = policy == Takeover::Glide    ? .7
                      : policy == Takeover::Slew   ? .6
                      : policy == Takeover::Pickup ? .5
                                                   : .9;
    near(e.target(1)->effective, expected,
         "normal takeover policy controls value");
    check(e.returnCommand(1, 1.5), "BACK TO STATE belongs to physical owner");
    e.tick(2.5);
    near(e.target(1)->effective, .5,
         "BACK TO STATE returns to captured morph value");
    e.tick(10);
    near(e.target(1)->effective, .5,
         "morph never reacquires after takeover or return");
  }
  for (auto mode : {Switch::Start, Switch::Midpoint, Switch::End}) {
    Engine e;
    e.addTarget(1, 0);
    e.morph(1, 1, 2, 0, Ease::Smooth, mode);
    e.tick(.9);
    near(e.target(1)->effective, mode == Switch::Start ? 1 : 0,
         "discrete value before threshold");
    e.tick(1);
    near(e.target(1)->effective, mode == Switch::End ? 0 : 1,
         "discrete midpoint uses temporal threshold");
    e.tick(2);
    near(e.target(1)->effective, 1,
         "discrete end never produces fractional enum");
  }
  {
    Engine e;
    e.addTarget(1, 0);
    e.addTarget(2, 1);
    e.morph(1, 1, 2, 0, Ease::Smooth);
    e.morph(2, 0, 2, 0, Ease::Smooth);
    e.tick(.5);
    near(e.target(1)->effective, .15625, "smooth ease quarter");
    near(e.target(2)->effective, .84375, "independent coherent target");
    e.recall(1, .3);
    e.tick(1);
    near(e.target(1)->effective, .3, "manual recall cancels its morph");
    near(e.target(2)->effective, .5, "manual recall preserves other morph");
    e.removeTarget(2);
    e.addTarget(2, .7);
    e.tick(2);
    near(e.target(2)->effective, .7,
         "deleted identity cannot animate recreated target");
    e.morph(1, 1, 2, 2);
    e.tick(3);
    auto value = e.target(1)->effective;
    e.panic();
    e.tick(4);
    near(e.target(1)->effective, value,
         "PANIC freezes effective value and clears writer");
    check(!e.target(1)->morphing && !e.target(1)->owner,
          "PANIC retires runtime");
    auto token = e.morph(1, 0, 1, 4);
    check(!e.morph(1, 2, 1, 4) && !e.morph(1, 0, -1, 4) &&
              !e.morph(1, 0, 3601, 4) && !e.morph(1, 0, 1, 3) &&
              !e.morph(99, 0, 1, 4) && !e.morph(1, 0, 1, 4, Ease(99)),
          "invalid commands rejected atomically");
    check(e.target(1)->token == token,
          "invalid request preserves current owner");
    check(e.releaseExternal(1, token),
          "explicit cancellation uses current token");
  }
  {
    Engine e;
    e.addTarget(1, .5);
    for (unsigned i = 0; i < 1000; ++i) {
      auto before = e.target(1)->effective;
      check(e.morph(1, i % 2 ? 0 : 1, .1, i * .001) != 0,
            "bounded rapid recall");
      // morph() advances to the new timestamp before capturing its starting
      // point.
      check(std::abs(e.target(1)->effective - before) <= .01,
            "rapid recalls remain continuous");
      e.tick(i * .001 + .0005);
    }
    e.tick(2);
    check(!e.target(1)->morphing, "rapid recall completes cleanly");
  }
}
