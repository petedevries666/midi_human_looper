#include "../headless/controller_engine.hpp"
#include "../headless/snapshot_wire.hpp"
#include <iostream>
#include <stdexcept>
using namespace controller;
unsigned checks = 0;
void check(bool x, const char *name) {
  ++checks;
  if (!x)
    throw std::runtime_error(name);
}
void near(double x, double y, const char *n) {
  check(std::abs(x - y) < 1e-9, n);
}
Mapping map(uint32_t id, uint32_t source, uint32_t target,
            Takeover mode = Takeover::Direct) {
  Mapping m;
  m.id = id;
  m.source = source;
  m.target = target;
  m.takeover = mode;
  return m;
}
#include "morph_engine_cases.hpp"
int main() {
  try {
    morph_engine_tests();
    {
      Engine e;
      check(e.addTarget(1, .5), "target");
      auto m = map(1, 1, 1, Takeover::Pickup);
      check(e.configure(m), "pickup config");
      e.input(1, 0, 0);
      near(e.target(1)->effective, .5, "pickup prevents jump");
      check(e.target(1)->takeoverPending, "pending");
      e.input(1, .4, .1);
      near(e.target(1)->effective, .5, "not crossed");
      e.input(1, .6, .2);
      near(e.target(1)->effective, .6, "cross pickup");
      check(!e.target(1)->takeoverPending, "pickup acquired");
      e.recall(1, .9);
      e.input(1, .2, .3);
      near(e.target(1)->effective, .9, "patch pickup reset");
    }
    {
      Engine e;
      e.addTarget(1, .2);
      auto m = map(1, 1, 1, Takeover::Glide);
      m.glideSeconds = 1;
      e.configure(m);
      e.input(1, 1, 0);
      near(e.target(1)->effective, .2, "glide no jump");
      e.tick(.5);
      near(e.target(1)->effective, .6, "glide midpoint");
      e.input(1, 0, .5);
      near(e.target(1)->effective, .6, "continuous retarget");
      e.tick(1);
      near(e.target(1)->effective, .3, "retarget midpoint");
      e.tick(1.5);
      near(e.target(1)->effective, 0, "retarget complete");
      check(!e.tick(1), "reject backwards time");
    }
    {
      Engine e;
      e.addTarget(1, .5);
      auto m = map(1, 1, 1, Takeover::Slew);
      m.slewPerSecond = .2;
      e.configure(m);
      e.input(1, 1, 0);
      e.tick(1);
      near(e.target(1)->effective, .7, "slew rate");
      e.input(1, 0, 1);
      e.tick(2);
      near(e.target(1)->effective, .5, "slew retarget");
    }
    {
      Engine e;
      e.addTarget(1, .25);
      auto m = map(1, 1, 1);
      m.back = Return::Idle;
      m.idleSeconds = 1;
      m.returnSeconds = 2;
      e.configure(m);
      e.input(1, 1, 0);
      e.tick(2);
      near(e.target(1)->effective, .625, "idle return crossing boundary");
      e.input(1, .8, 2);
      near(e.target(1)->effective, .8, "motion cancels return");
      e.tick(4);
      near(e.target(1)->effective, .525, "idle rearmed");
      e.tick(5);
      near(e.target(1)->effective, .25, "return snapshot");
      check(e.target(1)->owner == 0, "return relinquishes");
    }
    {
      Engine e;
      e.addTarget(1, .4);
      auto m = map(1, 1, 1);
      m.back = Return::Release;
      m.returnSeconds = 1;
      e.configure(m);
      e.input(1, 1, 0);
      e.input(1, 0, .2, false);
      e.tick(.7);
      near(e.target(1)->effective, .7, "release return");
      e.tick(1.2);
      near(e.target(1)->effective, .4, "release completion");
    }
    {
      Engine e;
      e.addTarget(1, .3);
      auto m = map(1, 1, 1);
      m.back = Return::Command;
      m.returnSeconds = 1;
      e.configure(m);
      e.input(1, .9, 0);
      e.capture(1);
      e.input(1, 1, .1);
      check(e.returnCommand(1, .1), "command return");
      e.tick(1.1);
      near(e.target(1)->effective, .9, "explicit snapshot boundary");
    }
    {
      Engine e;
      e.addTarget(1, .2);
      auto low = map(1, 1, 1);
      low.back = Return::Idle;
      low.idleSeconds = .1;
      low.returnSeconds = 1;
      auto high = map(2, 2, 1);
      high.priority = 10;
      e.configure(low);
      e.configure(high);
      e.input(1, .9, 0);
      e.tick(.2);
      e.input(2, .7, .2);
      e.tick(2);
      near(e.target(1)->effective, .7,
           "stale return cannot overwrite higher priority");
      e.input(1, 0, 3);
      near(e.target(1)->effective, .7, "lower source blocked");
      check(!e.external(1, .1, 0, 3), "lower external automation blocked");
      near(e.target(1)->effective, .7, "rejected external preserves owner");
      auto token = e.external(1, .8, 100, 3);
      e.input(2, 0, 4);
      near(e.target(1)->effective, .8, "automation owns");
      check(e.updateExternal(1, token, .75), "macro updates its owned token");
      near(e.target(1)->effective, .75, "macro updated effective value");
      check(!e.updateExternal(1, token + 1, .2), "stale macro update rejected");
      check(!e.updateExternal(1, token, NAN),
            "nonfinite macro update rejected");
      check(!e.releaseExternal(1, token + 1), "stale token rejected");
      check(e.releaseExternal(1, token), "release valid token");
      e.input(1, .6, 4);
      check(!e.updateExternal(1, token, .1),
            "macro cannot overwrite physical takeover");
      near(e.target(1)->effective, .6, "new snapshot after ownership release");
    }
    {
      Engine e;
      for (unsigned i = 1; i <= 3; ++i)
        e.addTarget(i, .2 * i);
      auto a = map(1, 1, 1), b = map(2, 1, 2), c = map(3, 1, 3);
      a.back = b.back = Return::Command;
      e.configure(a);
      e.configure(b);
      e.configure(c);
      e.input(1, 1, 0);
      for (unsigned i = 1; i <= 3; ++i)
        near(e.target(i)->effective, 1, "one source many targets");
      e.returnCommand(1, 0);
      e.returnCommand(2, 0);
      e.tick(1);
      near(e.target(1)->effective, .2, "eligible one returns");
      near(e.target(2)->effective, .4, "eligible two returns");
      near(e.target(3)->effective, 1, "ineligible volume retains");
    }
    {
      Engine e;
      e.addTarget(1, .4);
      auto a = map(2, 1, 1), b = map(1, 1, 1);
      a.curve.points[1].y = .5;
      e.configure(a);
      e.configure(b);
      e.input(1, .8, 0);
      check(e.target(1)->owner == 1, "stable ID tie");
      near(e.target(1)->effective, .8, "tie winner demand");
      e.removeMapping(1);
      e.input(1, .8, .1);
      near(e.target(1)->effective, .4, "remaining mapping");
      e.panic();
      check(e.target(1)->owner == 0, "panic cancels policies");
      e.removeTarget(1);
      check(!e.mapping(2), "target deletion removes maps");
      check(!e.configure(map(3, 1, 1)), "missing target");
    }
    {
      Curve c;
      near(c.evaluate(.5), .5, "identity curve");
      c.points[0].bend = .2;
      near(c.evaluate(.5), .25, "positive bend matches EEL");
      c.points[0].bend = -.2;
      near(c.evaluate(.5), .75, "negative bend matches EEL");
      c.count = 3;
      c.points[0].bend = 0;
      c.points[1] = {.5, .2, 0};
      c.points[2] = {1, 1, 0};
      check(c.valid(), "multipoint curve");
      near(c.evaluate(.75), .6, "multipoint interpolation");
      c.points[1].x = 0;
      check(!c.valid(), "duplicate x rejected");
    }
    {
      performance::State state;
      state.count=512;
      for(unsigned j=0;j<state.count;++j) {state.values[j].key.instrument=j+1;state.values[j].key.kind=1;state.values[j].effective=j%128;}
      performance::Snapshots snapshots;
      auto id=snapshots.capture(state);
      check(id!=0,"expanded stable target capture is bounded at 512");
      check(!snapshots.dirty(id,state),"dense effective lookup terminates and matches");
      state.values[511].effective+=1;
      check(snapshots.dirty(id,state),"last dense target detects modification");
      check(snapshots.update(id,state),"dense state recapture");
      auto wire=performance::configurationJson(snapshots.configuration());
      check(wire.find("\"version\":4")!=std::string::npos,"new eligible kinds use versioned extension");
      state.count=513;
      check(!state.valid(),"extended capture refuses overflow");
      Engine e;
      for (unsigned i = 1; i <= Engine::TargetCapacity; ++i)
        check(e.addTarget(i, 0), "bounded target capacity");
      check(!e.addTarget(Engine::TargetCapacity+1, 0), "target overflow");
      for (unsigned i = 1; i <= 64; ++i)
        check(e.configure(map(i, i, i)), "bounded mapping capacity");
      check(!e.configure(map(65, 1, 1)), "mapping overflow");
      auto bad = map(2, 1, 1);
      bad.returnSeconds = 0;
      check(!e.configure(bad), "invalid config atomic");
      check(e.mapping(2)->source == 2, "invalid preserves old mapping");
      check(!e.input(1, NAN, 0), "reject nonfinite source");
      check(!e.tick(INFINITY), "reject nonfinite clock");
    }
    {
      Engine e;
      e.addTarget(1, .5);
      auto m = map(1, 1, 1, Takeover::Glide);
      m.ease = Ease::Smooth;
      m.glideSeconds = 1;
      e.configure(m);
      e.input(1, 1, 0);
      e.tick(.25);
      near(e.target(1)->effective, .578125, "smoothstep quarter");
      m.enabled = false;
      e.configure(m);
      e.input(1, 0, .5);
      near(e.target(1)->effective, .578125, "disabled mapping transparent");
    }
    {
      Engine e;
      e.addTarget(1, .3);
      auto m = map(1, 1, 1);
      m.back = Return::Idle;
      m.idleSeconds = .5;
      m.returnSeconds = .5;
      e.configure(m);
      e.input(1, .9, 0);
      e.input(1, .9, .4);
      e.tick(.8);
      near(e.target(1)->effective, .9, "repeated identical input resets idle");
      e.tick(2);
      near(e.target(1)->effective, .3, "large time step completes return");
    }
    {
      Engine e;
      for (unsigned i = 1; i <= 16; ++i) {
        e.addTarget(i, .5);
        auto m = map(i, 1 + i % 3, i, i % 2 ? Takeover::Glide : Takeover::Slew);
        m.back = Return::Idle;
        m.idleSeconds = .03;
        m.returnSeconds = .04;
        e.configure(m);
      }
      uint32_t seed = 7;
      for (unsigned i = 0; i < 10000; ++i) {
        seed = 1664525 * seed + 1013904223;
        e.input(1 + seed % 3, double(seed % 1000) / 999, i * .001);
        for (unsigned t = 1; t <= 16; ++t)
          check(std::isfinite(e.target(t)->effective) &&
                    e.target(t)->effective >= 0 && e.target(t)->effective <= 1,
                "rapid deterministic multi-target motion bounded");
      }
    }
    std::cout << "PASS: " << checks
              << " synthetic-time Controller Engine checks\n";
    return 0;
  } catch (const std::exception &e) {
    std::cerr << "FAIL: " << e.what() << '\n';
    return 1;
  }
}
