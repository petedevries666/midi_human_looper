// Actual JACK MIDI graph smoke: two channel inputs, phrase switch and PANIC
// drain.
#include <atomic>
#include <chrono>
#include <iostream>
#include <jack/jack.h>
#include <jack/midiport.h>
#include <thread>
std::atomic<unsigned> frame{0}, on{0}, off{0};
jack_port_t *input, *output;
int process(jack_nframes_t n, void *) {
  void *out = jack_port_get_buffer(output, n);
  jack_midi_clear_buffer(out);
  auto f = frame.fetch_add(1);
  if (f == 10 || f == 30) {
    unsigned char m[3] = {144, 72,
                          static_cast<unsigned char>(f == 10 ? 100 : 0)};
    jack_midi_event_write(out, 0, m, 3);
  }
  if (f == 80 || f == 100) {
    unsigned char m[3] = {145, 81,
                          static_cast<unsigned char>(f == 80 ? 90 : 0)};
    jack_midi_event_write(out, 0, m, 3);
  }
  void *in = jack_port_get_buffer(input, n);
  for (unsigned i = 0; i < jack_midi_get_event_count(in); ++i) {
    jack_midi_event_t e;
    jack_midi_event_get(&e, in, i);
    if (e.size >= 3) {
      if ((e.buffer[0] & 240) == 144 && e.buffer[2])
        ++on;
      else if ((e.buffer[0] & 240) == 128 ||
               ((e.buffer[0] & 240) == 144 && !e.buffer[2]))
        ++off;
    }
  }
  return 0;
}
int main() {
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
  std::this_thread::sleep_for(std::chrono::seconds(2));
  jack_deactivate(c);
  jack_client_close(c);
  std::cout << "JACK notes on=" << on << " off=" << off << '\n';
  return on >= 2 && off >= 2048 ? 0 : 1;
}
