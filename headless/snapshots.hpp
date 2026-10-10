#pragma once
#include "controller_engine.hpp"
#include "parameter_registry.hpp"
#include <algorithm>
#include <array>
#include <cstring>
namespace performance {
struct Key {
  uint32_t instrument = 0, module = 0;
  int kind = 0;
  bool operator==(const Key &b) const {
    return instrument == b.instrument && module == b.module && kind == b.kind;
  }
};
struct Value {
  Key key;
  double effective = 0;
  bool included = true, expression = false;
};
struct State {
  unsigned count = 0;
  std::array<Value, 512> values{};
  bool valid() const {
    if (count > values.size())
      return false;
    for (unsigned i = 0; i < count; ++i) {
      const auto &v = values[i];
      if (!v.key.instrument || v.key.instrument > 16777215 ||
          v.key.module > 16777215 || v.key.kind < 0 || v.key.kind > 24 ||
          v.key.kind == 16 || !std::isfinite(v.effective))
        return false;
      for (unsigned j = 0; j < i; ++j)
        if (v.key == values[j].key)
          return false;
    }
    return true;
  }
};
struct Record {
  uint32_t id = 0;
  char name[49]{};
  double seconds = 2;
  controller::Ease ease = controller::Ease::Smooth;
  controller::Switch switching = controller::Switch::Midpoint;
  State state;
  bool valid() const {
    return id && id <= 16777215 && std::memchr(name, 0, sizeof(name)) &&
           std::isfinite(seconds) && seconds >= 0 && seconds <= 30 &&
           int(ease) >= 0 && int(ease) <= 1 && int(switching) >= 0 &&
           int(switching) <= 3 && state.valid();
  }
};
struct SwitchAction {
  uint32_t switchId = 0, snapshotId = 0;
  unsigned gesture = 0, action = 0; // 1 next, 2 previous, 3 recall, 4 morph, 5
                                    // cycle, 6/7 morph next/previous
};
struct AB {
  uint32_t a = 0, b = 0;
  double position = 0;
  unsigned ease = 0;
  bool valid() const {
    return a <= 16777215 && b <= 16777215 && std::isfinite(position) &&
           position >= 0 && position <= 1 && ease <= 1 &&
           ((!a && !b) || (a && b && a != b));
  }
};
struct Configuration {
  uint32_t nextId = 1, selected = 0;
  unsigned count = 0;
  std::array<Record, 16> records{};
  std::array<SwitchAction, 48> actions{};
  AB ab;
};
class Snapshots {
  std::array<Record, 16> records{};
  uint32_t nextId = 1;
  std::array<SwitchAction, 48> actions{};

public:
  static constexpr unsigned version = 4;
  AB ab;
  unsigned count = 0;
  uint32_t selected = 0, revision = 1;
  const Record *find(uint32_t id) const {
    for (unsigned i = 0; i < count; ++i)
      if (records[i].id == id)
        return &records[i];
    return nullptr;
  }
  const Record &at(unsigned i) const { return records[i]; }
  uint32_t capture(const State &state) {
    if (count == records.size() || !state.valid() || nextId > 16777215)
      return 0;
    Record r;
    r.id = nextId++;
    const char prefix[] = "SNAPSHOT ";
    std::memcpy(r.name, prefix, 9);
    r.name[9] = '0' + (count + 1) / 10;
    r.name[10] = '0' + (count + 1) % 10;
    r.state = state;
    records[count++] = r;
    selected = r.id;
    ++revision;
    return r.id;
  }
  bool update(uint32_t id, const State &state) {
    if (!state.valid())
      return false;
    for (unsigned i = 0; i < count; ++i)
      if (records[i].id == id) {
        State updated = state;
        for (unsigned j = 0; j < updated.count; ++j)
          for (unsigned k = 0; k < records[i].state.count; ++k)
            if (updated.values[j].key == records[i].state.values[k].key)
              updated.values[j].included = records[i].state.values[k].included;
        records[i].state = updated;
        ++revision;
        return true;
      }
    return false;
  }
  bool commit(const Record &draft, uint32_t expected) {
    if (expected != revision || !draft.valid())
      return false;
    for (unsigned i = 0; i < count; ++i)
      if (records[i].id == draft.id) {
        records[i] = draft;
        ++revision;
        return true;
      }
    return false;
  }
  uint32_t duplicate(uint32_t id) {
    const auto *r = find(id);
    if (!r || count == records.size() || nextId > 16777215)
      return 0;
    Record copy = *r;
    copy.id = nextId++;
    records[count++] = copy;
    ++revision;
    return copy.id;
  }
  void pruneInstrument(uint32_t id) {
    for (unsigned i = 0; i < count; ++i) {
      auto &state = records[i].state;
      unsigned kept = 0;
      for (unsigned j = 0; j < state.count; ++j) {
        const auto &v = state.values[j];
        if (v.key.instrument != id || phraseKind(v.key.kind))
          state.values[kept++] = v;
      }
      for (unsigned j = kept; j < state.count; ++j) state.values[j] = Value{};
      state.count = kept;
    }
    ++revision;
  }
  bool erase(uint32_t id) {
    for (unsigned i = 0; i < count; ++i)
      if (records[i].id == id) {
        for (unsigned j = i + 1; j < count; ++j)
          records[j - 1] = records[j];
        records[--count] = Record{};
        if (ab.a == id || ab.b == id)
          ab = AB{};
        for (auto &a : actions)
          if ((a.action == 3 || a.action == 4) && a.snapshotId == id)
            a = SwitchAction{};
        if (selected == id)
          selected = 0;
        ++revision;
        return true;
      }
    return false;
  }
  bool move(uint32_t id, int direction) {
    if (direction != 1 && direction != -1)
      return false;
    for (unsigned i = 0; i < count; ++i)
      if (records[i].id == id) {
        int to = int(i) + direction;
        if (to < 0 || to >= int(count))
          return false;
        std::swap(records[i], records[to]);
        ++revision;
        return true;
      }
    return false;
  }
  const std::array<SwitchAction, 48> &switchActions() const { return actions; }
  bool setAction(SwitchAction a) {
    if (!a.switchId || a.switchId > 16777215 || a.gesture > 2 || a.action > 7 ||
        a.snapshotId > 16777215)
      return false;
    if ((a.action == 3 || a.action == 4) && !find(a.snapshotId))
      return false;
    for (auto &old : actions)
      if (old.switchId == a.switchId && old.gesture == a.gesture) {
        old = a.action ? a : SwitchAction{};
        ++revision;
        return true;
      }
    if (!a.action)
      return true;
    for (auto &old : actions)
      if (!old.switchId) {
        old = a;
        ++revision;
        return true;
      }
    return false;
  }
  uint32_t navigate(unsigned action) const {
    if (!count)
      return 0;
    unsigned index = count - 1;
    for (unsigned i = 0; i < count; ++i)
      if (records[i].id == selected)
        index = i;
    bool previous = action == 2 || action == 7;
    if (!selected && previous)
      return records[count - 1].id;
    return records[(index + (previous ? count - 1 : 1)) % count].id;
  }
  Configuration configuration() const {
    Configuration c;
    c.nextId = nextId;
    c.count = count;
    c.selected = selected;
    c.records = records;
    c.actions = actions;
    c.ab = ab;
    return c;
  }
  bool restore(const Configuration &c) {
    if (!c.ab.valid() || c.count > 16 || !c.nextId || c.nextId > 16777216)
      return false;
    bool selectedKnown = c.selected == 0;
    for (unsigned i = 0; i < c.count; ++i) {
      const auto &r = c.records[i];
      if (!r.valid() || r.id >= c.nextId)
        return false;
      selectedKnown = selectedKnown || r.id == c.selected;
      for (unsigned j = 0; j < i; ++j)
        if (c.records[j].id == r.id)
          return false;
    }
    if (!selectedKnown)
      return false;
    for (unsigned i = 0; i < c.actions.size(); ++i) {
      const auto &a = c.actions[i];
      if (a.gesture > 2 || a.action > 7 || a.switchId > 16777215 ||
          a.snapshotId > 16777215 || (!a.switchId && a.action) ||
          (a.switchId && !a.action))
        return false;
      for (unsigned j = 0; j < i; ++j)
        if (a.switchId && c.actions[j].switchId == a.switchId &&
            c.actions[j].gesture == a.gesture)
          return false;
    }
    if (c.ab.a &&
        (!std::any_of(c.records.begin(), c.records.begin() + c.count,
                      [&](const Record &r) { return r.id == c.ab.a; }) ||
         !std::any_of(c.records.begin(), c.records.begin() + c.count,
                      [&](const Record &r) { return r.id == c.ab.b; })))
      return false;
    ab = c.ab;
    records = c.records;
    actions = c.actions;
    count = c.count;
    nextId = c.nextId;
    selected = c.selected;
    ++revision;
    return true;
  }
  bool dirty(uint32_t id, const State &current) const {
    const auto *r = find(id);
    if (!r)
      return true;
    if (current.count > current.values.size())
      return true;
    std::array<int, 1024> lookup;
    lookup.fill(-1);
    auto hash = [](const Key &k) {
      uint64_t v = (uint64_t(k.instrument) << 32) | (uint64_t(k.module) << 4) |
                   unsigned(k.kind);
      v ^= v >> 33;
      v *= UINT64_C(0xff51afd7ed558ccd);
      v ^= v >> 33;
      return unsigned(v) & 1023;
    };
    for (unsigned i = 0; i < current.count; ++i) {
      unsigned slot = hash(current.values[i].key);
      while (lookup[slot] >= 0)
        slot = (slot + 1) & 1023;
      lookup[slot] = int(i);
    }
    for (unsigned i = 0; i < r->state.count; ++i) {
      const auto &v = r->state.values[i];
      if (!v.included)
        continue;
      unsigned slot = hash(v.key);
      while (lookup[slot] >= 0 && !(current.values[lookup[slot]].key == v.key))
        slot = (slot + 1) & 1023;
      if (lookup[slot] < 0 ||
          !std::isfinite(current.values[lookup[slot]].effective) ||
          std::abs(v.effective - current.values[lookup[slot]].effective) > 1e-7)
        return true;
    }
    return false;
  }
};
} // namespace performance
