#include "../headless/humanizer.hpp"
#include <cstdlib>
#include <iostream>
static unsigned checks = 0;
static void check(bool ok, const char *s) {
  ++checks;
  if (!ok) {
    std::cerr << s << '\n';
    std::exit(1);
  }
}
int main() {
  humanizer::Configuration c;
  c.enabled = true;
  c.timingMs = 40;
  c.velocityAmount = 40;
  humanizer::Identity a;
  a.scope = 1;
  a.instance = 7;
  a.phrase = 1;
  a.note = 4;
  a.group = 2400;
  double uniformSquares = 0, bellSquares = 0;
  unsigned evolving = 0, independent = 0;
  for (unsigned seed = 0; seed < 1000; ++seed) {
    c.seed = seed;
    for (unsigned variation = 0; variation < 2; ++variation) {
      c.variation = humanizer::Variation(variation);
      for (unsigned feel = 0; feel < 2; ++feel) {
        c.feel = humanizer::Feel(feel);
        for (unsigned scope = 0; scope < 2; ++scope) {
          a.scope = scope;
          a.iteration = 9;
          check(humanizer::pairedShift(c, a, 0, 1, 48000) == 0,
                "all original T=0 attacks protected");
          for (double factor : {.5, 1., 2.}) {
            double shift = humanizer::pairedShift(c, a, 2400, factor, 48000);
            check(2400 * factor + shift >= 1,
                  "nonzero attack is never rebased to zero");
            check(std::abs((3600 * factor + shift) - (2400 * factor + shift) -
                           1200 * factor) < 1e-8,
                  "paired Note Off preserves scaled duration");
            auto other = a;
            other.note = 99;
            check(humanizer::pairedShift(c, other, 2400, factor, 48000) ==
                      shift,
                  "chord timing independent of note index");
            for (unsigned velocity = 0; velocity < 128; ++velocity) {
              auto result = humanizer::velocity(c, a, velocity);
              check(velocity ? result >= 1 && result <= 127 : result == 0,
                    "velocity bounds and Note On zero semantics");
            }
          }
        }
      }
    }
    c.feel = humanizer::Feel::Uniform;
    c.variation = humanizer::Variation::Fixed;
    a.scope = 1;
    a.iteration = 0;
    double fixed = humanizer::pairedShift(c, a, 2400, 1, 48000);
    auto b = a;
    b.iteration = 17;
    check(humanizer::pairedShift(c, b, 2400, 1, 48000) == fixed,
          "FIXED independent of retrigger/loop count");
    c.variation = humanizer::Variation::Evolving;
    evolving += humanizer::pairedShift(c, b, 2400, 1, 48000) != fixed;
    b = a;
    b.instance = 8;
    independent += humanizer::pairedShift(c, b, 2400, 1, 48000) != fixed;
    auto u = humanizer::signedUnit(c, a, 17, true);
    uniformSquares += u * u;
    c.feel = humanizer::Feel::BoundedGaussian;
    auto g = humanizer::signedUnit(c, a, 17, true);
    bellSquares += g * g;
  }
  check(evolving > 900 && independent > 900,
        "EVOLVING and instance streams vary independently");
  check(bellSquares < uniformSquares * .4,
        "bounded Gaussian concentrates nearer center");
  c.timingMs = 0;
  c.velocityAmount = 0;
  for (unsigned v = 0; v < 128; ++v)
    check(humanizer::velocity(c, a, v) == v,
          "zero velocity amount is transparent");
  check(humanizer::pairedShift(c, a, 2400, .5, 48000) == 0,
        "zero timing amount adds no delay");
  c.timingMs = 40;
  c.velocityAmount = 40;
  c.enabled = false;
  check(humanizer::pairedShift(c, a, 2400, 1, 48000) == 0 &&
            humanizer::velocity(c, a, 77) == 77,
        "disabled configuration transparent");
  c.timingMs = 41;
  check(!c.valid(), "excessive timing rejected");
  c.timingMs = 40;
  c.velocityAmount = INFINITY;
  check(!c.valid(), "nonfinite velocity rejected");
  std::cout << "PASS: " << checks
            << " deterministic HUMANIZER algorithm checks (scheduler not "
               "integrated)\n";
}
