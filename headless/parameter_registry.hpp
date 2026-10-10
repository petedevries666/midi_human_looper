#pragma once
#include <algorithm>
#include <cmath>
// Stable engine parameter identities, matching modules/catalog.json engineKind.
// The callback uses this bounded lookup; it never parses descriptors or
// allocates.
namespace performance {
constexpr int parameterCount(int type) {
  return type == 2                ? 3
         : type == 5              ? 4
         : type == 6              ? 2
         : type >= 1 && type <= 6 ? 1
                                  : 0;
}
constexpr int parameterKind(int type, int row) {
  return row < 0 || row >= parameterCount(type) ? -1
         : type == 1                            ? 7
         : type == 2                            ? 8 + row
         : type == 3                            ? 11
         : type == 4                            ? 0
         : type == 5                            ? (row < 3 ? 4 + row : 12)
         : row == 0                             ? 2
                                                : 13;
}
constexpr bool discrete(int kind) {
  return kind == 3 || kind == 4 || kind == 8 || kind == 11 || kind == 12 ||
         kind == 13 || (kind >= 18 && kind <= 24);
}
constexpr bool phraseKind(int kind) {
  return kind == 14 || kind == 15 || (kind >= 17 && kind <= 20);
}
constexpr bool binned(int kind) {
  return kind == 3 || kind == 4 || kind == 8 || kind == 11 || kind == 12 ||
         (kind >= 18 && kind <= 24);
}
inline double physical(int kind, double x) {
  x = std::max(0., std::min(1., x));
  if (kind == 14)
    return std::pow(2., 2 * x - 1);
  if (kind == 16)
    return x;
  double low = kind == 7                               ? -48
               : kind == 0 || kind == 15 || kind == 17 ? .2
               : kind == 5                             ? .25
               : kind == 6                             ? .02
                                                       : 0;
  double high = kind == 7                               ? 48
                : kind == 0 || kind == 17               ? 3
                : kind == 5 || kind == 22 || kind == 23 ? 16
                : kind == 3 || kind == 6 || kind == 12 || kind == 15 ||
                        kind == 18 || kind == 19 || kind == 21 || kind == 24
                    ? 1
                : kind == 4 || kind == 20 ? 2
                : kind == 8 || kind == 11 ? 3
                                          : 127;
  double step = kind == 0 || kind == 6 || kind == 15 || kind == 17 ? .01
                : kind == 5                                        ? .25
                                                                   : 1;
  return binned(kind) ? std::min(high, std::floor(x * (high + 1)))
                      : std::floor((low + (high - low) * x) / step + .5) * step;
}
inline double normalized(int kind, double v) {
  if (kind == 14)
    return std::max(0., std::min(1., (std::log2(v <= 0 ? 1 : v) + 1) / 2));
  if (kind == 16)
    return std::max(0., std::min(1., v));
  double low = physical(kind, 0), high = physical(kind, 1);
  return std::max(0., std::min(1., binned(kind) ? (v + .5) / (high + 1)
                                                : (v - low) / (high - low)));
}
} // namespace performance
