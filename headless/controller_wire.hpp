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
  if (!(s >> version) || (version != 1 && version != 2))
    return false;
  for (auto &a : c.sources)
    if (!(s >> a.id >> a.kind >> a.channel >> a.number))
      return false;
  for (auto &b : c.bindings)
    if (!readBinding(s, b))
      return false;
  if(version==2)for(auto &a:c.sources){bool end=false;for(unsigned j=0;j<16;++j){int ch;if(!(s>>ch)||ch<0||ch>=127||(ch&&ch<32)||(end&&ch))return false;a.name[j]=char(ch);end|=ch==0;}}
  if(version==2)for(unsigned i=0;i<4;++i){unsigned count;if(!(s>>count)||(count && (count<2 || count>16)))return false;c.presetEnabled[i]=count>0;c.presets[i].count=count;for(auto &p:c.presets[i].points)if(!(s>>p.x>>p.y>>p.bend))return false;}
  return c.valid();
}
inline std::string configurationJson(const Configuration &c) {
  std::ostringstream raw;
  int version=1;for(const auto &s:c.sources)if(s.name[0])version=2;for(bool enabled:c.presetEnabled)if(enabled)version=2;
  raw << std::setprecision(17) << version;
  for (auto &s : c.sources)
    raw << ' ' << s.id << ' ' << s.kind << ' ' << s.channel << ' ' << s.number;
  for (auto &b : c.bindings) {
    raw << ' ';
    writeBinding(raw, b);
  }
  if(version==2)for(const auto &s:c.sources)for(unsigned j=0;j<16;++j)raw<<' '<<int(s.name[j]);
  if(version==2)for(unsigned i=0;i<4;++i){raw<<' '<<(c.presetEnabled[i]?c.presets[i].count:0);for(const auto &p:c.presets[i].points)raw<<' '<<p.x<<' '<<p.y<<' '<<p.bend;}
  std::string result = raw.str();
  for (auto &ch : result)
    if (ch == ' ')
      ch = ',';
  return "{\"version\":"+std::to_string(version)+",\"configuration\":[" + result + "]}";
}
} // namespace controller
