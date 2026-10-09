// Actual JACK MIDI graph smoke: two channel inputs, phrase switch and PANIC
// drain.
#include <array>
#include <atomic>
#include <chrono>
#include <iostream>
#include <jack/jack.h>
#include <jack/midiport.h>
#include <string>
#include <thread>
std::atomic<unsigned> frame{0}, on{0}, off{0}, emergency{0};
bool flood = false, ordering = false, scheduled = false;
struct OrderEvent {
  unsigned frame, offset, note, status, channel;
};
std::array<OrderEvent, 6> ordered{};
std::atomic<unsigned> orderCount{0};
jack_port_t *input, *output;
int process(jack_nframes_t n, void *) {
  void *out = jack_port_get_buffer(output, n);
  jack_midi_clear_buffer(out);
  auto f = frame.fetch_add(1);
  if (flood && f < 200) {
    for (unsigned i = 0; i < 1024; ++i) {
      unsigned char m[] = {144, 91,
                           static_cast<unsigned char>((i & 1) ? 0 : 90)};
      if (jack_midi_event_write(out, 0, m, 3))
        break;
    }
  }
  if ((ordering || scheduled) && (f == 10 || f == 30)) {
    unsigned char m[] = {146, 99,
                         static_cast<unsigned char>(f == 10 ? 127 : 0)};
    jack_midi_event_write(out, 0, m, 3);
  }
  if (!ordering && !scheduled && (f == 10 || f == 30)) {
    unsigned char m[3] = {144, 72,
                          static_cast<unsigned char>(f == 10 ? 100 : 0)};
    jack_midi_event_write(out, 0, m, 3);
  }
  if (!ordering && !scheduled && (f == 80 || f == 100)) {
    unsigned char m[3] = {145, 81,
                          static_cast<unsigned char>(f == 80 ? 90 : 0)};
    jack_midi_event_write(out, 0, m, 3);
  }
  void *in = jack_port_get_buffer(input, n);
  for (unsigned i = 0; i < jack_midi_get_event_count(in); ++i) {
    jack_midi_event_t e;
    jack_midi_event_get(&e, in, i);
    if (e.size >= 3) {
      if ((ordering || scheduled) &&
          (e.buffer[1] == 90 || e.buffer[1] == 91 || e.buffer[1] == 92 ||
           e.buffer[1] == 94) &&
          orderCount.load() < (scheduled ? 6u : 5u)) {
        auto at = orderCount.load();
        ordered[at] = {f, e.time, e.buffer[1], unsigned(e.buffer[0] & 240),
                       unsigned(e.buffer[0] & 15)};
        orderCount.store(at + 1);
      }
      if ((e.buffer[0] & 240) == 176 && e.buffer[1] == 120 && e.buffer[2] == 0)
        ++emergency;
      if ((e.buffer[0] & 240) == 144 && e.buffer[2])
        ++on;
      else if ((e.buffer[0] & 240) == 128 ||
               ((e.buffer[0] & 240) == 144 && !e.buffer[2]))
        ++off;
    }
  }
  return 0;
}
int main(int argc, char **argv) {
  flood = argc > 1 && std::string(argv[1]) == "--flood";
  ordering = argc > 1 && std::string(argv[1]) == "--ordering";
  scheduled = argc > 1 && std::string(argv[1]) == "--scheduled";
  jack_status_t status;
  auto c = jack_client_open("midi_smoke", JackNoStartServer, &status);
  if (!c)
    return 2;
  input =
      jack_port_register(c, "in", JACK_DEFAULT_MIDI_TYPE, JackPortIsInput, 0);
  output =
      jack_port_register(c, "out", JACK_DEFAULT_MIDI_TYPE, JackPortIsOutput, 0);
  jack_set_process_callback(c, process, nullptr);
  if (jack_activate(c))
    return 2;
  if (jack_connect(c, jack_port_name(output), "midi_human_looper:midi_in") ||
      jack_connect(c, "midi_human_looper:midi_out", jack_port_name(input)))
    return 3;
  std::this_thread::sleep_for(std::chrono::seconds(flood ? 4 : 2));
  jack_deactivate(c);
  jack_client_close(c);
  std::cout << "JACK notes on=" << on << " off=" << off
            << " emergency=" << emergency << '\n';
  if (scheduled) {
    const unsigned notes[] = {91, 92, 90, 91, 92, 90},
                   offsets[] = {16, 220, 400, 16, 220, 400},
                   channels[] = {2, 3, 1, 2, 3, 1};
    bool ok = orderCount == 6;
    for (unsigned i = 0; i < orderCount; ++i) {
      auto &e = ordered[i];
      std::cout << "SCHEDULE frame=" << e.frame << " offset=" << e.offset
                << " note=" << e.note << " channel=" << e.channel
                << " status=" << e.status << '\n';
      ok &= e.frame == ordered[0].frame + (i == 5 ? 20 : (i >= 3 ? 1 : 0)) &&
            e.offset == offsets[i] && e.note == notes[i] &&
            e.channel == channels[i] && e.status == (i < 3 ? 144u : 128u);
    }
    return ok ? 0 : 1;
  }
  if (ordering) {
    const unsigned notes[] = {91, 94, 94, 92, 90},
                   offsets[] = {16, 120, 120, 220, 400},
                   statuses[] = {144, 144, 128, 144, 144};
    bool ok = orderCount == 5;
    for (unsigned i = 0; i < orderCount; ++i) {
      auto &e = ordered[i];
      std::cout << "ORDER frame=" << e.frame << " offset=" << e.offset
                << " note=" << e.note << " status=" << e.status << '\n';
      ok &= e.frame == ordered[0].frame && e.offset == offsets[i] &&
            e.note == notes[i] && e.status == statuses[i];
    }
    return ok ? 0 : 1;
  }
  return on >= 2 && off >= 2048 && (!flood || emergency >= 16) ? 0 : 1;
}
