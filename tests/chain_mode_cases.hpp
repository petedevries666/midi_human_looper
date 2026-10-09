#include "../headless/chain_mode.hpp"
static void chain_mode_tests(const char *source) {
  Host h(source);
  h.run("ext_noinit=1;gmem[0]=0;panic_pending=0;slider9=1;");
  ChainMode chain(h.f, true);
  chain.command(2, 0);
  check(!chain.tick(0, 128, 48000, false, 120),
        "armed record survives JACK Starting/Stopped before first roll");
  check(chain.armed, "record pending until transport rolls");
  chain.tick(0, 128, 48000, true, 120);
  check(chain.recording && !chain.armed, "take begins at common grid origin");
  h.eq("mem[MODE_BASE]", 0, "chain records LOOP mode");
  h.midi(144, 60, 100);
  chain.tick(128, 128, 48000, true, 120);
  h.midi(128, 60, 0);
  h.eq("layer_count(0)", 2,
       "existing recording dispatcher captures paired MIDI");
  chain.command(3, 0);
  check(!chain.recording, "manual finish disarms only selected recording");
  h.eq("mem[TRIG_BASE]", 1, "recorded loop armed for playback");
  h.eq("mem[LEN_BASE]", 192000, "take retains shared two-bar length");
  chain.previous = 0;
  chain.command(2, 0);
  chain.tick(0, 128, 48000, true, 120);
  check(!chain.command(2, 1),
        "recording target cannot be stolen by another phrase");
  h.midi(144, 65, 100);
  chain.command(3, 0);
  h.eq("layer_count(0)", 4,
       "overdub retains earlier take and adds paired notes");
  chain.previous = 0;
  h.run("clear_layer(1);");
  chain.command(2, 1);
  chain.tick(256, 128, 48000, true, 120);
  check(chain.armed && !chain.recording, "second phrase waits for common wrap");
  chain.tick(384, 128, 48000, false, 120);
  check(!chain.run && !chain.armed,
        "transport STOP cancels record and playback");
  chain.previous = 0;
  chain.command(2, 1);
  chain.tick(192000, 128, 48000, true, 120);
  h.midi(145, 61, 100);
  chain.command(3, 1);
  h.eq("layer_count(1)", 2, "finish supplies missing recorded Note Off");
  h.eq("mem[layer_base(1,1)]", 191999, "synthetic release remains inside loop");
  h.eq("mem[layer_base(1,1)+1]", 129,
       "synthetic release preserves MIDI channel");
  check(chain.tick(192128, 128, 48000, true, 130),
        "tempo change requires owned-note release");
  check(chain.error && !chain.run,
        "tempo change never silently stretches recorded events");
  check(!chain.tick(192256, 128, 48000, true, 130),
        "latched clock error does not spam PANIC each block");
  chain.previous = 0;
  chain.command(1, 1);
  chain.tick(100000, 128, 48000, true, 120);
  check(chain.tick(0, 128, 48000, true, 120) && !chain.run,
        "transport seek cancels playback safely");
  chain.previous = 0;
  chain.command(1, 1);
  chain.tick(100000, 128, 48000, true, 120, 1000000);
  check(chain.tick(100384, 128, 48000, true, 120, 1000384) && chain.run,
        "missed callback resumes playback with release, unlike transport seek");
  check(chain.tick(0, 128, 48000, true, 120, 1000512) && !chain.run,
        "transport seek is detected independently of JACK sample clock");
  // Full phrase with an unmatched attack must be rejected, never played without
  // its release.
  h.run("clear_layer(2);store_event(2,0,144,62,100,0);chain_test_i=1;loop(MAX_"
        "EVENTS_PER_LAYER-1,store_event(2,chain_test_i,176,1,1,0);chain_test_i+"
        "=1;);");
  chain.previous = 0;
  chain.command(2, 2);
  chain.tick(0, 128, 48000, true, 120);
  chain.command(3, 2);
  h.eq("mem[TRIG_BASE+2]", 0, "capacity exhaustion disables unsafe loop");
}
