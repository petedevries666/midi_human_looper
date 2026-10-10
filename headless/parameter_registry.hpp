#pragma once
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
         kind == 13;
}
} // namespace performance
