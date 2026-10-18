#pragma once
#include <array>
#include <cstddef>
#include <cstdint>

// Explicit emergency PANIC also releases notes absent from the ownership table.
// Keep the sweep bounded across callbacks; failed writes retain their cursor.
class PanicSweep {
  unsigned cursor_ = 2048;
public:
  void begin() { cursor_ = 0; }
  unsigned remaining() const { return 2048 - cursor_; }
  template<class Emit> void drain(unsigned budget, Emit emit) {
    while (budget-- && cursor_ < 2048) {
      const std::array<uint8_t,3> event{{uint8_t(128 | (cursor_ / 128)),
                                       uint8_t(cursor_ % 128),0}};
      if (!emit(event)) break;
      ++cursor_;
    }
  }
};
