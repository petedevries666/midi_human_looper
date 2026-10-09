#pragma once
#include "controller_host.hpp"
#include <iomanip>
#include <sstream>
namespace controller {
inline bool readBinding(std::istream &s, Binding &b) {
  int takeover, back, ease, on;
  unsigned count;
  if (!(s >> b.policy.id >> b.policy.source >> b.policy.target >>
        b.instrument >> b.module >> b.kind >> b.base >> b.policy.priority >>
        takeover >> back >> ease >> b.policy.threshold >>
        b.policy.glideSeconds >> b.policy.slewPerSecond >>
        b.policy.idleSeconds >> b.policy.returnSeconds >> on >> count) ||
      count < 2 || count > 16 || on < 0 || on > 1)
    return false;
  b.policy.takeover = Takeover(takeover);
  b.policy.back = Return(back);
  b.policy.ease = Ease(ease);
  b.policy.enabled = on;
  b.policy.curve.count = count;
  for (unsigned j = 0; j < 16; ++j)
    if (!(s >> b.policy.curve.points[j].x >> b.policy.curve.points[j].y >>
          b.policy.curve.points[j].bend))
      return false;
  return !b.policy.id || b.valid();
}
inline void writeBinding(std::ostream &s, const Binding &b) {
  auto &p = b.policy;
  s << p.id << ' ' << p.source << ' ' << p.target << ' ' << b.instrument << ' '
    << b.module << ' ' << b.kind << ' ' << b.base << ' ' << p.priority << ' '
    << int(p.takeover) << ' ' << int(p.back) << ' ' << int(p.ease) << ' '
    << p.threshold << ' ' << p.glideSeconds << ' ' << p.slewPerSecond << ' '
    << p.idleSeconds << ' ' << p.returnSeconds << ' ' << p.enabled << ' '
    << p.curve.count;
  for (auto &v : p.curve.points)
    s << ' ' << v.x << ' ' << v.y << ' ' << v.bend;
}
inline bool readConfiguration(std::istream &s, Configuration &c) {
  int version;
  if (!(s >> version) || version != 1)
    return false;
  for (auto &a : c.sources)
    if (!(s >> a.id >> a.kind >> a.channel >> a.number))
      return false;
  for (auto &b : c.bindings)
    if (!readBinding(s, b))
      return false;
  return c.valid();
}
inline std::string configurationJson(const Configuration &c) {
  std::ostringstream raw;
  raw << std::setprecision(17) << 1;
  for (auto &s : c.sources)
    raw << ' ' << s.id << ' ' << s.kind << ' ' << s.channel << ' ' << s.number;
  for (auto &b : c.bindings) {
    raw << ' ';
    writeBinding(raw, b);
  }
  std::string result = raw.str();
  for (auto &ch : result)
    if (ch == ' ')
      ch = ',';
  return "{\"version\":1,\"configuration\":[" + result + "]}";
}
} // namespace controller
