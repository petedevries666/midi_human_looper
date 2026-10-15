#pragma once
#include "conductor_document.hpp"
#include <istream>
#include <cmath>
#include <sstream>
#include <string>
#include <vector>

// Control-worker-only carrier. Both production adapters validate the typed
// versioned document before activation; no document/JSON reaches the MIDI callback.
// Match the existing 16 MB command ceiling, not a future musical capacity (Q3).
namespace conductor {
inline bool read(std::istream &in, std::vector<unsigned> &bytes) {
  unsigned count=0;
  if (!(in>>count) || !count || count>4000000) return false;
  bytes.reserve(count);
  for (unsigned i=0;i<count;++i) {
    double c=0;
    if (!(in>>c) || !std::isfinite(c) || c<32 || c>126 || c!=unsigned(c)) return false;
    bytes.push_back(unsigned(c));
  }
  return validDocument(bytes);
}
inline std::string json(const std::vector<unsigned> &bytes) {
  std::ostringstream out;
  out<<"{\"version\":1,\"configuration\":[";
  for(unsigned i=0;i<bytes.size();++i) { if(i) out<<','; out<<bytes[i]; }
  out<<"]}";
  return out.str();
}
}
