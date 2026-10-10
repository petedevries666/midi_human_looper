#pragma once
// Global controller policy domain. Normalized effective targets; no note
// Transformer, MIDI scheduling, sockets, JSON, allocation or wall-clock calls
// in this component.
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
namespace controller {
inline double clamp(double x) { return std::max(0., std::min(1., x)); }
enum class Takeover { Direct, Pickup, Glide, Slew };
enum class Return { Off, Idle, Release, Command };
enum class Ease { Linear, Smooth };
enum class Switch { Continuous, Start, Midpoint, End };
struct Point {
  double x, y, bend;
  Point(double px = 0, double py = 0, double pb = 0) : x(px), y(py), bend(pb) {}
};
struct Curve {
  unsigned count = 2;
  std::array<Point, 16> points{};
  Curve() { points[1].x = points[1].y = 1; }
  bool valid() const {
    if (count < 2 || count > 16 || points[0].x != 0 || points[count - 1].x != 1)
      return false;
    for (unsigned i = 0; i < count; ++i) {
      const auto &p = points[i];
      if (!std::isfinite(p.x) || !std::isfinite(p.y) ||
          !std::isfinite(p.bend) || p.x < 0 || p.x > 1 || p.y < 0 || p.y > 1 ||
          std::abs(p.bend) > .98 || (i && p.x <= points[i - 1].x))
        return false;
    }
    return true;
  }
  double evaluate(double x) const {
    x = clamp(x);
    for (unsigned i = 1; i < count; ++i)
      if (x <= points[i].x) {
        const auto &a = points[i - 1];
        const auto &b = points[i];
        double t = (x - a.x) / (b.x - a.x), power = 1 + 5 * std::abs(a.bend);
        if (a.bend > 0)
          t = std::pow(t, power);
        else if (a.bend < 0)
          t = 1 - std::pow(1 - t, power);
        return clamp(a.y + (b.y - a.y) * t);
      }
    return points[count - 1].y;
  }
};
struct Mapping {
  uint32_t id = 0, source = 0, target = 0;
  int priority = 0;
  Takeover takeover = Takeover::Direct;
  Return back = Return::Off;
  Ease ease = Ease::Linear;
  double threshold = .02, glideSeconds = .2, slewPerSecond = 1, idleSeconds = 1,
         returnSeconds = .5;
  bool enabled = true;
  Curve curve;
  bool valid() const {
    return id && id != UINT32_MAX && source && target && priority >= 0 &&
           priority <= 1000 && curve.valid() && std::isfinite(threshold) &&
           threshold >= 0 && threshold <= 1 && std::isfinite(glideSeconds) &&
           glideSeconds > 0 && glideSeconds <= 60 &&
           std::isfinite(slewPerSecond) && slewPerSecond > 0 &&
           slewPerSecond <= 1000 && std::isfinite(idleSeconds) &&
           idleSeconds >= 0 && idleSeconds <= 3600 &&
           std::isfinite(returnSeconds) && returnSeconds > 0 &&
           returnSeconds <= 60 && int(takeover) >= 0 && int(takeover) <= 3 &&
           int(back) >= 0 && int(back) <= 3 && int(ease) >= 0 && int(ease) <= 1;
  }
};
struct Transition {
  uint32_t target = 0;
  double goal = 0, seconds = 0;
  Ease ease = Ease::Linear;
  Switch switching = Switch::Continuous;
};
struct Target {
  uint32_t id = 0, owner = 0;
  uint64_t token = 0;
  int priority = -1;
  double effective = 0, snapshot = 0;
  bool returning = false, takeoverPending = false;
  // Runtime only: the existing target owner is the sole writer during a morph.
  bool morphing = false;
  double morphStart = 0, morphGoal = 0, morphAt = 0, morphSeconds = 0;
  Ease morphEase = Ease::Linear;
  Switch morphSwitch = Switch::Continuous;
};
class Engine {
public:
  static const unsigned TargetCapacity = 512, MappingCapacity = 64;

private:
  struct Runtime {
    Mapping config;
    bool used = false, previousKnown = false, active = false, returning = false;
    double previous = 0, demand = 0, start = 0, startAt = 0, lastMove = 0,
           snapshot = 0;
    uint64_t token = 0, sequence = 0;
  };
  std::array<Target, TargetCapacity> targets{};
  std::array<Runtime, MappingCapacity> mappings{};
  double time = 0;
  uint64_t generation = 0, sequence = 0;
  Runtime *owner(Target &t) {
    for (auto &m : mappings)
      if (m.used && m.config.id == t.owner && m.token == t.token)
        return &m;
    return nullptr;
  }
  void release(Target &t) {
    if (auto *m = owner(t)) {
      m->active = false;
      m->returning = false;
    }
    t.morphing = false;
    t.owner = 0;
    t.priority = -1;
    t.token = ++generation;
    t.returning = false;
    t.takeoverPending = false;
  }
  void beginReturn(Target &t, Runtime &m, double at) {
    if (t.owner != m.config.id || t.token != m.token || !m.active)
      return;
    m.returning = true;
    m.start = t.effective;
    m.startAt = at;
    m.demand = m.snapshot;
    t.returning = true;
  }
  void update(Target &t, Runtime &m, double at) {
    if (m.returning) {
      double x = clamp((at - m.startAt) / m.config.returnSeconds);
      if (m.config.ease == Ease::Smooth)
        x = x * x * (3 - 2 * x);
      t.effective = clamp(m.start + (m.demand - m.start) * x);
      if (at - m.startAt >= m.config.returnSeconds)
        release(t);
    } else if (m.config.takeover == Takeover::Glide) {
      double x = clamp((at - m.startAt) / m.config.glideSeconds);
      if (m.config.ease == Ease::Smooth)
        x = x * x * (3 - 2 * x);
      t.effective = clamp(m.start + (m.demand - m.start) * x);
    } else if (m.config.takeover == Takeover::Slew) {
      double d = m.config.slewPerSecond * std::max(0., at - time);
      t.effective = clamp(t.effective +
                          std::max(-d, std::min(d, m.demand - t.effective)));
    } else
      t.effective = m.demand;
  }

public:
  static constexpr unsigned configurationVersion = 1;
  const Target *target(uint32_t id) const {
    for (const auto &t : targets)
      if (t.id == id && id)
        return &t;
    return nullptr;
  }
  unsigned freeTargets() const {
    unsigned count = 0;
    for (const auto &t : targets)
      if (!t.id)
        ++count;
    return count;
  }
  bool addTarget(uint32_t id, double effective) {
    if (!id || target(id) || !std::isfinite(effective) || effective < 0 ||
        effective > 1)
      return false;
    for (auto &t : targets)
      if (!t.id) {
        t = Target{};
        t.id = id;
        t.effective = effective;
        t.snapshot = effective;
        t.token = ++generation;
        return true;
      }
    return false;
  }
  bool removeTarget(uint32_t id) {
    for (auto &t : targets)
      if (t.id == id && id) {
        release(t);
        t = Target{};
        for (auto &m : mappings)
          if (m.used && m.config.target == id)
            m = Runtime{};
        return true;
      }
    return false;
  }
  bool configure(const Mapping &config) {
    if (!config.valid() || !target(config.target))
      return false;
    Runtime *slot = nullptr;
    for (auto &m : mappings)
      if (m.used && m.config.id == config.id) {
        slot = &m;
        break;
      }
    if (!slot)
      for (auto &m : mappings)
        if (!m.used) {
          slot = &m;
          break;
        }
    if (!slot)
      return false;
    if (slot->used)
      for (auto &t : targets)
        if (t.owner == slot->config.id)
          release(t);
    *slot = Runtime{};
    slot->used = true;
    slot->config = config;
    return true;
  }
  bool removeMapping(uint32_t id) {
    for (auto &m : mappings)
      if (m.used && m.config.id == id) {
        for (auto &t : targets)
          if (t.owner == id)
            release(t);
        m = Runtime{};
        return true;
      }
    return false;
  }
  bool tick(double now) {
    if (!std::isfinite(now) || now < time)
      return false;
    for (auto &t : targets)
      if (t.id) {
        if (t.morphing && t.owner == UINT32_MAX) {
          double x = clamp((now - t.morphAt) / t.morphSeconds);
          double shaped = t.morphEase == Ease::Smooth ? x * x * (3 - 2 * x) : x;
          if (t.morphSwitch == Switch::Continuous)
            t.effective =
                clamp(t.morphStart + (t.morphGoal - t.morphStart) * shaped);
          else {
            double boundary = t.morphSwitch == Switch::Start      ? 0
                              : t.morphSwitch == Switch::Midpoint ? .5
                                                                  : 1;
            t.effective = x >= boundary ? t.morphGoal : t.morphStart;
          }
          if (x >= 1)
            release(t);
          continue;
        }
        auto *m = owner(t);
        if (!m)
          continue;
        if (!m->returning && m->config.back == Return::Idle &&
            now >= m->lastMove + m->config.idleSeconds) {
          double boundary = std::max(time, m->lastMove + m->config.idleSeconds);
          update(t, *m, boundary);
          beginReturn(t, *m, boundary);
        }
        update(t, *m, now);
      }
    time = now;
    return true;
  }
  bool input(uint32_t source, double value, double now, bool pressed = true) {
    if (!source || !std::isfinite(value) || value < 0 || value > 1 ||
        !tick(now))
      return false;
    auto event = ++sequence;
    // One winner per target for this source event; lower stable mapping ID
    // breaks ties.
    for (auto &t : targets)
      if (t.id) {
        Runtime *winner = nullptr;
        double demanded = 0;
        for (auto &m : mappings)
          if (m.used && m.config.enabled && m.config.source == source &&
              m.config.target == t.id) {
            double demand = m.config.curve.evaluate(value);
            bool eligible = true;
            if (!pressed && m.config.back == Return::Release) {
              if (t.owner == m.config.id && t.token == m.token)
                beginReturn(t, m, now);
              m.previous = demand;
              m.previousKnown = true;
              continue;
            }
            if (m.config.takeover == Takeover::Pickup &&
                t.owner != m.config.id) {
              eligible =
                  std::abs(demand - t.effective) <= m.config.threshold ||
                  (m.previousKnown &&
                   ((m.previous <= t.effective && demand >= t.effective) ||
                    (m.previous >= t.effective && demand <= t.effective)));
              if (!eligible)
                t.takeoverPending = true;
            }
            m.previous = demand;
            m.previousKnown = true;
            if (eligible && m.config.priority >= t.priority &&
                (!winner || m.config.priority > winner->config.priority ||
                 (m.config.priority == winner->config.priority &&
                  m.config.id < winner->config.id))) {
              winner = &m;
              demanded = demand;
            }
          }
        if (winner) {
          auto &m = *winner;
          bool fresh = t.owner != m.config.id || t.token != m.token;
          if (fresh) {
            release(t);
            t.owner = m.config.id;
            t.priority = m.config.priority;
            m.token = t.token;
            m.snapshot = t.effective;
            t.snapshot = t.effective;
          }
          m.active = true;
          m.returning = false;
          m.sequence = event;
          m.lastMove = now;
          m.start = t.effective;
          m.startAt = now;
          m.demand = demanded;
          t.returning = false;
          t.takeoverPending = false;
          if (m.config.takeover == Takeover::Direct ||
              m.config.takeover == Takeover::Pickup)
            t.effective = demanded;
        }
      }
    return true;
  }
  bool returnCommand(uint32_t targetId, double now) {
    if (!tick(now))
      return false;
    for (auto &t : targets)
      if (t.id == targetId) {
        auto *m = owner(t);
        if (!m || m->config.back != Return::Command)
          return false;
        beginReturn(t, *m, now);
        return true;
      }
    return false;
  }
  bool capture(uint32_t targetId) {
    for (auto &t : targets)
      if (t.id == targetId) {
        t.snapshot = t.effective;
        if (auto *m = owner(t))
          m->snapshot = t.effective;
        return true;
      }
    return false;
  }
  uint64_t external(uint32_t id, double value, int priority, double now) {
    if (!std::isfinite(value) || value < 0 || value > 1 || priority < 0 ||
        priority > 1000 || !tick(now))
      return 0;
    for (auto &t : targets)
      if (t.id == id) {
        if (priority < t.priority)
          return 0;
        release(t);
        t.effective = value;
        t.owner = UINT32_MAX;
        t.priority = priority;
        return t.token;
      }
    return 0;
  }
  // A recall is an explicit performance command: it replaces the current owner
  // once. Physical mappings of any configured priority can then take over using
  // their normal Pickup/Glide/Slew policy. A morph never reacquires that
  // target.
  uint64_t morph(uint32_t id, double goal, double seconds, double now,
                 Ease ease = Ease::Linear,
                 Switch switching = Switch::Continuous) {
    if (!target(id) || !std::isfinite(goal) || goal < 0 || goal > 1 ||
        !std::isfinite(seconds) || seconds < 0 || seconds > 3600 ||
        int(ease) < 0 || int(ease) > 1 || int(switching) < 0 ||
        int(switching) > 3 || !tick(now))
      return 0;
    for (auto &t : targets)
      if (t.id == id) {
        release(t);
        // Forget previous Pickup crossings; a new recall is a new reference
        // state.
        for (auto &m : mappings)
          if (m.used && m.config.target == id)
            m.previousKnown = false;
        t.owner = UINT32_MAX;
        t.priority = 0;
        t.morphStart = t.effective;
        t.morphGoal = goal;
        t.morphAt = now;
        t.morphSeconds = seconds;
        t.morphEase = ease;
        t.morphSwitch = switching;
        t.morphing = seconds > 0;
        if (!seconds || switching == Switch::Start)
          t.effective = goal;
        auto token = t.token;
        if (!seconds)
          release(t);
        return token;
      }
    return 0;
  }
  // Validate the whole global performance command before touching time/owners.
  // All transitions share one engine timestamp. Fixed target capacity bounds
  // validation and application; caller-owned storage is never retained.
  bool morphBatch(const Transition *entries, unsigned count, double now) {
    if (!entries || !count || count > TargetCapacity || !std::isfinite(now) ||
        now < time)
      return false;
    for (unsigned i = 0; i < count; ++i) {
      const auto &e = entries[i];
      if (!target(e.target) || !std::isfinite(e.goal) || e.goal < 0 ||
          e.goal > 1 || !std::isfinite(e.seconds) || e.seconds < 0 ||
          e.seconds > 3600 || int(e.ease) < 0 || int(e.ease) > 1 ||
          int(e.switching) < 0 || int(e.switching) > 3)
        return false;
      for (unsigned j = 0; j < i; ++j)
        if (entries[j].target == e.target)
          return false;
    }
    for (unsigned i = 0; i < count; ++i) {
      const auto &e = entries[i];
      morph(e.target, e.goal, e.seconds, now, e.ease, e.switching);
    }
    return true;
  }
  // Streaming performance macro updates retain their original token. Physical
  // takeover cannot be undone by a subsequent macro tick.
  bool updateExternal(uint32_t id, uint64_t token, double value) {
    if (!std::isfinite(value) || value < 0 || value > 1)
      return false;
    for (auto &t : targets)
      if (t.id == id && t.owner == UINT32_MAX && t.token == token) {
        t.morphing = false;
        t.effective = value;
        return true;
      }
    return false;
  }
  bool releaseExternal(uint32_t id, uint64_t token) {
    for (auto &t : targets)
      if (t.id == id && t.owner == UINT32_MAX && t.token == token) {
        release(t);
        return true;
      }
    return false;
  }
  void panic() {
    for (auto &t : targets)
      if (t.id)
        release(t);
    for (auto &m : mappings)
      if (m.used) {
        m.previousKnown = false;
        m.active = false;
        m.returning = false;
      }
  }
  bool recall(uint32_t id, double value) {
    if (!std::isfinite(value) || value < 0 || value > 1)
      return false;
    for (auto &t : targets)
      if (t.id == id) {
        release(t);
        t.effective = value;
        t.snapshot = value;
        for (auto &m : mappings)
          if (m.used && m.config.target == id) {
            m.previousKnown = false;
            m.active = false;
            m.returning = false;
          }
        return true;
      }
    return false;
  }
  const Mapping *mapping(uint32_t id) const {
    for (const auto &m : mappings)
      if (m.used && m.config.id == id)
        return &m.config;
    return nullptr;
  }
};
} // namespace controller
