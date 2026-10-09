#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>
// Deterministic shared algorithm contract. Scheduling/ownership belong to the
// host adapter; this component never edits recorded MIDI or stores mutable RNG.
namespace humanizer {
enum class Feel { Uniform, BoundedGaussian };
enum class Variation { Fixed, Evolving };
struct Configuration {
  bool enabled = false;
  double timingMs = 0, velocityAmount = 0;
  Feel feel = Feel::Uniform;
  Variation variation = Variation::Fixed;
  uint32_t seed = 1;
  bool valid() const {
    return std::isfinite(timingMs) && timingMs >= 0 && timingMs <= 40 &&
           std::isfinite(velocityAmount) && velocityAmount >= 0 &&
           velocityAmount <= 40 && int(feel) >= 0 && int(feel) <= 1 &&
           int(variation) >= 0 && int(variation) <= 1;
  }
};
struct Identity {
  uint32_t scope = 0, instance = 0, phrase = 0, iteration = 0, note = 0,
           group = 0;
};
inline uint32_t mix(uint32_t value, uint32_t datum) {
  return value * 1664525u + 1013904223u + datum;
}
inline uint32_t hash(const Configuration &c, const Identity &id,
                     uint32_t stream, bool timing) {
  uint32_t h = c.seed;
  h = mix(h, id.scope);
  h = mix(h, id.instance);
  h = mix(h, id.phrase);
  h = mix(h, c.variation == Variation::Evolving ? id.iteration : 0);
  h = mix(h, timing ? id.group : id.note);
  h = mix(h, stream);
  // Avalanche the stream ID: adjacent stream IDs must not produce correlated
  // draws when constructing the bounded Gaussian approximation.
  h ^= h >> 16;
  h *= 0x85ebca6bu;
  h ^= h >> 13;
  h *= 0xc2b2ae35u;
  h ^= h >> 16;
  return h;
}
inline double signedUnit(const Configuration &c, const Identity &id,
                         uint32_t stream, bool timing) {
  // Six independent uniforms provide a bounded bell-shaped approximation,
  // with finite support [-1,1], unlike an unbounded Box-Muller sample.
  unsigned n = c.feel == Feel::BoundedGaussian ? 6 : 1;
  double sum = 0;
  for (unsigned i = 0; i < n; ++i)
    sum += 2 * (hash(c, id, stream + i * 7919u, timing) / 4294967295.) - 1;
  return sum / n;
}
inline double pairedShift(const Configuration &c, const Identity &id,
                          double originalOn, double factor, double sampleRate) {
  if (!c.enabled || c.timingMs == 0 || originalOn == 0)
    return 0;
  double jitter = std::floor(
      signedUnit(c, id, 17, true) * c.timingMs * sampleRate / 1000 + .5);
  // The SAME shift applies to the corresponding Note Off. A naturally later
  // attack may approach the origin but must not be converted into a T=0 anchor.
  return std::max(1., originalOn * factor + jitter) - originalOn * factor;
}
inline uint8_t velocity(const Configuration &c, const Identity &id,
                        uint8_t input) {
  if (!input || !c.enabled || c.velocityAmount == 0)
    return input;
  double value = std::floor(
      input + signedUnit(c, id, 104729, false) * c.velocityAmount + .5);
  return uint8_t(std::max(1., std::min(127., value)));
}
} // namespace humanizer
