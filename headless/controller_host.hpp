#pragma once
#include "controller_engine.hpp"
#include <array>
#include <cstdint>
// Host adapter configuration v1. Stable IDs are never array positions.
namespace controller {
struct Source {
  uint32_t id = 0;
  int kind = 0, channel = 0, number = 0; // kind 0=unassigned, 1=note, 2=CC
  bool valid() const {
    return id && id <= 16777215 && kind >= 0 && kind <= 2 && channel >= 0 &&
           channel < 16 && number >= 0 && number < 128 &&
           (kind != 2 || (number != 64 && number < 120));
  }
};
struct Binding {
  Mapping policy;
  uint32_t instrument = 0, module = 0;
  int kind = 1;
  double base = 0; // normalized committed value; runtime never serialized
  bool valid() const {
    return policy.valid() && instrument && instrument <= 16777215 &&
           module <= 16777215 && kind >= 0 && kind < 16 &&
           (kind < 14 || (instrument <= 16 && !module)) &&
           std::isfinite(base) && base >= 0 && base <= 1;
  }
};
struct Configuration {
  std::array<Source, 16> sources{};
  std::array<Binding, 32> bindings{};
  bool valid() const {
    for (unsigned i = 0; i < sources.size(); ++i)
      if (sources[i].id) {
        if (!sources[i].valid())
          return false;
        for (unsigned j = 0; j < i; ++j)
          if (sources[j].id == sources[i].id ||
              (sources[i].kind && sources[j].kind == sources[i].kind &&
               sources[j].channel == sources[i].channel &&
               sources[j].number == sources[i].number))
            return false;
      }
    for (unsigned i = 0; i < bindings.size(); ++i)
      if (bindings[i].policy.id) {
        auto &b = bindings[i];
        if (!b.valid())
          return false;
        bool source = false;
        for (auto &s : sources)
          source |= s.id == b.policy.source;
        if (!source)
          return false;
        for (unsigned j = 0; j < i; ++j)
          if (bindings[j].policy.id) {
            auto &a = bindings[j];
            if (a.policy.id == b.policy.id)
              return false;
            bool key = a.instrument == b.instrument && a.module == b.module &&
                       a.kind == b.kind;
            if (key != (a.policy.target == b.policy.target) ||
                (key && a.base != b.base))
              return false;
          }
      }
    return true;
  }
};
class Host {
  Engine core;
  Configuration config;
  uint32_t learning = 0;
  Source candidate;
  int conflict = 0;
  // Captured note release must never leak into performance routing.
  std::array<std::array<bool, 128>, 16> quarantine{};

public:
  double time = 0;
  const Configuration &configuration() const { return config; }
  const Target *target(uint32_t id) const { return core.target(id); }
  uint32_t learnTarget() const { return learning; }
  const Source &learnCandidate() const { return candidate; }
  int learnConflict() const { return conflict; }
  template <class Resolve>
  bool replace(const Configuration &next, Resolve resolve) {
    if (!next.valid())
      return false;
    for (auto &b : next.bindings)
      if (b.policy.id && !resolve(b))
        return false;
    core = Engine{};
    core.tick(time);
    config = next;
    learning = 0;
    candidate = Source{};
    conflict = 0;
    for (auto &b : config.bindings)
      if (b.policy.id) {
        if (!core.target(b.policy.target))
          core.addTarget(b.policy.target, b.base);
        core.configure(b.policy);
      }
    return true;
  }
  bool source(const Source &s) {
    if (!s.valid())
      return false;
    for (auto &a : config.sources)
      if (a.id != s.id && a.kind && s.kind && a.kind == s.kind &&
          a.channel == s.channel && a.number == s.number)
        return false;
    for (auto &a : config.sources)
      if (a.id == s.id) {
        a = s;
        panic();
        return true;
      }
    for (auto &a : config.sources)
      if (!a.id) {
        a = s;
        return true;
      }
    return false;
  }
  bool forget(uint32_t id) {
    for (auto &s : config.sources)
      if (s.id == id) {
        s.kind = 0;
        cancel();
        core.panic();
        return true;
      }
    return false;
  }
  bool learn(uint32_t id) {
    for (auto &s : config.sources)
      if (s.id == id) {
        cancel();
        learning = id;
        return true;
      }
    return false;
  }
  void cancel() {
    learning = 0;
    candidate = Source{};
    conflict = 0;
  }
  bool confirm() {
    if (!learning || !candidate.kind || conflict < 0)
      return false;
    for (auto &s : config.sources)
      if (s.id != learning && s.kind == candidate.kind &&
          s.channel == candidate.channel && s.number == candidate.number)
        s.kind = 0;
    auto s = candidate;
    s.id = learning;
    bool ok = source(s);
    if (ok)
      cancel();
    return ok;
  }
  template <class Legacy>
  bool midi(const uint8_t *bytes, unsigned size, double now, Legacy legacy) {
    time = now;
    core.tick(now);
    if (size != 3)
      return false;
    int status = bytes[0] & 240, ch = bytes[0] & 15, num = bytes[1],
        value = bytes[2];
    if (num > 127 || value > 127)
      return false;
    bool on = status == 144 && value,
         off = status == 128 || (status == 144 && !value);
    if ((on || off) && quarantine[ch][num]) {
      if (off)
        quarantine[ch][num] = false;
      return true;
    }
    int kind = on || off ? 1 : status == 176 ? 2 : 0;
    // Channel-mode/sustain releases remain available to the safety engine.
    if (!kind || (kind == 2 && (num == 64 || num >= 120)))
      return false;
    if (learning && !off) {
      if (candidate.kind)
        return true; // Await deliberate conflict decision.
      candidate.id = learning;
      candidate.kind = kind;
      candidate.channel = ch;
      candidate.number = num;
      if (on)
        quarantine[ch][num] = true;
      conflict = legacy(kind, ch, num) ? -1 : 0;
      for (auto &s : config.sources)
        if (!conflict && s.id != learning && s.kind == kind &&
            s.channel == ch && s.number == num)
          conflict = int(s.id);
      if (!conflict)
        confirm();
      return true;
    }
    for (auto &s : config.sources)
      if (s.kind == kind && s.channel == ch && s.number == num) {
        core.input(s.id, kind == 1 ? (on ? 1. : 0.) : value / 127., now,
                   kind == 2 ? value > 0 : on);
        return true;
      }
    return false;
  }
  bool bind(const Binding &binding) {
    if (!binding.valid())
      return false;
    Configuration next = config;
    bool placed = false;
    for (auto &b : next.bindings)
      if (b.policy.id == binding.policy.id) {
        b = binding;
        placed = true;
        break;
      }
    if (!placed)
      for (auto &b : next.bindings)
        if (!b.policy.id) {
          b = binding;
          placed = true;
          break;
        }
    if (!placed || !next.valid())
      return false;
    if (!core.target(binding.policy.target) &&
        !core.addTarget(binding.policy.target, binding.base))
      return false;
    if (!core.configure(binding.policy))
      return false;
    for (auto &old : config.bindings)
      if (old.policy.id == binding.policy.id &&
          old.policy.target != binding.policy.target) {
        bool used = false;
        for (auto &v : next.bindings)
          used |= v.policy.id && v.policy.target == old.policy.target;
        if (!used)
          core.removeTarget(old.policy.target);
      }
    config = next;
    return true;
  }
  bool remove(uint32_t id) {
    for (auto &b : config.bindings)
      if (b.policy.id == id) {
        auto target = b.policy.target;
        core.removeMapping(id);
        b = Binding{};
        bool used = false;
        for (auto &v : config.bindings)
          used |= v.policy.id && v.policy.target == target;
        if (!used)
          core.removeTarget(target);
        return true;
      }
    return false;
  }
  void recall(uint32_t instrument, uint32_t module, int kind, double base) {
    for (auto &b : config.bindings)
      if (b.policy.id && b.instrument == instrument && b.module == module &&
          b.kind == kind) {
        b.base = base;
        core.recall(b.policy.target, base);
      }
  }
  template <class Resolve, class Apply>
  bool tick(double now, Resolve resolve, Apply apply) {
    time = now;
    core.tick(now);
    bool changed = false;
    for (auto &b : config.bindings)
      if (b.policy.id) {
        if (!resolve(b)) {
          auto id = b.policy.id;
          remove(id);
          changed = true;
          continue;
        }
        auto t = core.target(b.policy.target);
        if (t)
          apply(b, t->effective);
      }
    return changed;
  }
  uint64_t morph(uint32_t id, double goal, double seconds,
                 Ease ease = Ease::Linear,
                 Switch switching = Switch::Continuous) {
    return core.morph(id, goal, seconds, time, ease, switching);
  }
  bool morphBatch(const Transition *entries, unsigned count) {
    return core.morphBatch(entries, count, time);
  }
  bool returnCommand(uint32_t id) { return core.returnCommand(id, time); }
  bool capture(uint32_t id) { return core.capture(id); }
  void panic() {
    cancel();
    core.panic();
  }
};
} // namespace controller
