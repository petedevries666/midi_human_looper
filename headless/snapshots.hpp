#pragma once
#include "controller_engine.hpp"
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
  std::array<Value, 256> values{};
  bool valid() const {
    if (count > values.size())
      return false;
    for (unsigned i = 0; i < count; ++i) {
      const auto &v = values[i];
      if (!v.key.instrument || v.key.instrument > 16777215 ||
          v.key.module > 16777215 || v.key.kind < 0 || v.key.kind > 15 ||
          !std::isfinite(v.effective))
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
struct Configuration {
  uint32_t nextId = 1, selected = 0;
  unsigned count = 0;
  std::array<Record, 16> records{};
};
class Snapshots {
  std::array<Record, 16> records{};
  uint32_t nextId = 1;

public:
  static constexpr unsigned version = 1;
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
        records[i].state = state;
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
  bool erase(uint32_t id) {
    for (unsigned i = 0; i < count; ++i)
      if (records[i].id == id) {
        for (unsigned j = i + 1; j < count; ++j)
          records[j - 1] = records[j];
        records[--count] = Record{};
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
  Configuration configuration() const {
    Configuration c;
    c.nextId = nextId;
    c.count = count;
    c.selected = selected;
    c.records = records;
    return c;
  }
  bool restore(const Configuration &c) {
    if (c.count > 16 || !c.nextId || c.nextId > 16777216)
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
    records = c.records;
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
    std::array<int, 512> lookup;
    lookup.fill(-1);
    auto hash = [](const Key &k) {
      uint64_t v = (uint64_t(k.instrument) << 32) | (uint64_t(k.module) << 4) |
                   unsigned(k.kind);
      v ^= v >> 33;
      v *= UINT64_C(0xff51afd7ed558ccd);
      v ^= v >> 33;
      return unsigned(v) & 511;
    };
    for (unsigned i = 0; i < current.count; ++i) {
      unsigned slot = hash(current.values[i].key);
      while (lookup[slot] >= 0)
        slot = (slot + 1) & 511;
      lookup[slot] = int(i);
    }
    for (unsigned i = 0; i < r->state.count; ++i) {
      const auto &v = r->state.values[i];
      if (!v.included)
        continue;
      unsigned slot = hash(v.key);
      while (lookup[slot] >= 0 && !(current.values[lookup[slot]].key == v.key))
        slot = (slot + 1) & 511;
      if (lookup[slot] < 0 ||
          !std::isfinite(current.values[lookup[slot]].effective) ||
          std::abs(v.effective - current.values[lookup[slot]].effective) > 1e-7)
        return true;
    }
    return false;
  }
};
} // namespace performance
