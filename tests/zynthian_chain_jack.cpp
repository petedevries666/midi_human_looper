// Three independent chain destinations and a hardware-like source; no Python in
// JACK callback.
#include <array>
#include <atomic>
#include <iostream>
#include <jack/jack.h>
#include <jack/midiport.h>
#include <thread>
struct Event {
  unsigned chain, frame, offset, status, note, value;
};
std::array<Event, 16384> events{};
std::atomic<unsigned> count{0}, mask{0};
jack_client_t *client;
std::array<jack_port_t *, 3> inputs, outputs;
std::array<bool, 3> held{};
int process(jack_nframes_t n, void *) {
  jack_position_t p{};
  auto transport = jack_transport_query(client, &p);
  unsigned phase = p.frame % 192512;
  for (unsigned i = 0; i < 3; ++i) {
    auto out = jack_port_get_buffer(outputs[i], n);
    jack_midi_clear_buffer(out);
    bool attack = transport == JackTransportRolling &&
                  (mask.load() & (1u << i)) && phase == 0;
    bool release = held[i] && (phase == 24576 || !(mask.load() & (1u << i)) ||
                               transport != JackTransportRolling);
    if (attack || release) {
      unsigned char data[] = {
          static_cast<unsigned char>((attack ? 144 : 128) | i),
          static_cast<unsigned char>(60 + i),
          static_cast<unsigned char>(attack ? 100 : 0)};
      if (!jack_midi_event_write(out, 0, data, 3))
        held[i] = attack;
    }
    auto in = jack_port_get_buffer(inputs[i], n);
    for (unsigned j = 0; j < jack_midi_get_event_count(in); ++j) {
      jack_midi_event_t e;
      jack_midi_event_get(&e, in, j);
      if (e.size == 3 && e.buffer[1] >= 60 && e.buffer[1] <= 62 &&
          (e.buffer[0] & 240) != 176 && count < events.size()) {
        auto index = count.load();
        events[index] = {i,           p.frame,     e.time,
                         e.buffer[0], e.buffer[1], e.buffer[2]};
        count.store(index + 1);
      }
    }
  }
  return 0;
}
int main() {
  jack_status_t s;
  client = jack_client_open("mbh_three_chain_probe", JackNoStartServer, &s);
  if (!client)
    return 2;
  for (unsigned i = 0; i < 3; ++i) {
    inputs[i] = jack_port_register(client, ("in" + std::to_string(i)).c_str(),
                                   JACK_DEFAULT_MIDI_TYPE, JackPortIsInput, 0);
    outputs[i] =
        jack_port_register(client, ("out" + std::to_string(i)).c_str(),
                           JACK_DEFAULT_MIDI_TYPE, JackPortIsOutput, 0);
  }
  jack_set_process_callback(client, process, nullptr);
  if (jack_activate(client))
    return 3;
  for (unsigned i = 0; i < 3; ++i) {
    auto name = "mbh_" + std::to_string(i + 1);
    if (jack_connect(client, jack_port_name(outputs[i]),
                     (name + ":midi_in").c_str()) ||
        jack_connect(client, (name + ":midi_out").c_str(),
                     jack_port_name(inputs[i])))
      return 4;
  }
  std::cout << "READY\n" << std::flush;
  unsigned value;
  while (std::cin >> value)
    mask = value;
  jack_deactivate(client);
  jack_client_close(client);
  for (unsigned i = 0; i < count; ++i) {
    auto &e = events[i];
    std::cout << e.chain << ' ' << e.frame << ' ' << e.offset << ' ' << e.status
              << ' ' << e.note << ' ' << e.value << '\n';
  }
  return 0;
}
