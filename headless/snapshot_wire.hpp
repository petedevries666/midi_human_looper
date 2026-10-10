#pragma once
#include "snapshots.hpp"
#include <iomanip>
#include <istream>
#include <sstream>
namespace performance {
// Control-worker codec only. Never invoke streams/JSON on the processing
// thread.
inline bool integer(std::istream &in, unsigned &value, unsigned maximum) {
  double x;
  if (!(in >> x) || !std::isfinite(x) || x < 0 || x > maximum ||
      x != std::floor(x))
    return false;
  value = unsigned(x);
  return true;
}
inline bool readConfiguration(std::istream &in, Configuration &c) {
  unsigned version = 0;
  if (!integer(in, version, 2) || version < 1 ||
      !integer(in, c.nextId, 16777216) || !integer(in, c.selected, 16777215) ||
      !integer(in, c.count, 16))
    return false;
  for (unsigned i = 0; i < c.count; ++i) {
    auto &r = c.records[i];
    unsigned ease = 0, sw = 0;
    if (!integer(in, r.id, 16777215) || !(in >> r.seconds) ||
        !integer(in, ease, 1) || !integer(in, sw, 3) ||
        !integer(in, r.state.count, 256))
      return false;
    r.ease = controller::Ease(ease);
    r.switching = controller::Switch(sw);
    for (unsigned j = 0; j < 49; ++j) {
      unsigned ch = 0;
      if (!integer(in, ch, 126) || (ch && ch < 32))
        return false;
      r.name[j] = char(ch);
    }
    for (unsigned j = 0; j < r.state.count; ++j) {
      auto &v = r.state.values[j];
      unsigned k = 0, include = 0, expression = 0;
      if (!integer(in, v.key.instrument, 16777215) ||
          !integer(in, v.key.module, 16777215) || !integer(in, k, 15) ||
          !(in >> v.effective) || !integer(in, include, 1) ||
          !integer(in, expression, 1))
        return false;
      v.key.kind = int(k);
      v.included = include;
      v.expression = expression;
    }
  }
  if (version >= 2)
    for (auto &a : c.actions)
      if (!integer(in, a.switchId, 16777215) || !integer(in, a.gesture, 2) ||
          !integer(in, a.action, 7) || !integer(in, a.snapshotId, 16777215))
        return false;
  Snapshots validate;
  return validate.restore(c);
}
inline std::string configurationJson(const Configuration &c) {
  std::ostringstream o;
  o << std::setprecision(17) << "{\"version\":2,\"configuration\":[2,"
    << c.nextId << ',' << c.selected << ',' << c.count;
  for (unsigned i = 0; i < c.count; ++i) {
    const auto &r = c.records[i];
    o << ',' << r.id << ',' << r.seconds << ',' << int(r.ease) << ','
      << int(r.switching) << ',' << r.state.count;
    for (unsigned j = 0; j < 49; ++j)
      o << ',' << unsigned(static_cast<unsigned char>(r.name[j]));
    for (unsigned j = 0; j < r.state.count; ++j) {
      const auto &v = r.state.values[j];
      o << ',' << v.key.instrument << ',' << v.key.module << ',' << v.key.kind
        << ',' << v.effective << ',' << v.included << ',' << v.expression;
    }
  }
  for (const auto &a : c.actions)
    o << ',' << a.switchId << ',' << a.gesture << ',' << a.action << ','
      << a.snapshotId;
  o << "]}";
  return o.str();
}
} // namespace performance
