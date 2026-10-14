// Three independent chain destinations and a hardware-like source; no Python in
// JACK callback.
#include <array>
#include <cmath>
#include <atomic>
#include <iostream>
#include <jack/jack.h>
#include <jack/midiport.h>
#include <thread>
struct Event {
  unsigned chain, frame, offset, status, note, value;
};
std::array<Event, 16384> events{};
std::atomic<unsigned> count{0}, mask{0}, pendingCc{0};
jack_client_t *client, *sourceClient;
std::array<jack_port_t *, 3> inputs, outputs;
std::array<bool, 3> held{};
unsigned loopLength=192512;
bool fanout = false;
bool nativeRoutes = false;
int sourceProcess(jack_nframes_t n, void *) {
  jack_position_t p{};
  auto transport = jack_transport_query(sourceClient, &p);
  unsigned phase = p.frame % loopLength;
  const bool emitCc = pendingCc.exchange(0) != 0;
  for (unsigned i = 0; i < 3; ++i) {
    auto out = jack_port_get_buffer(outputs[i], n);
    jack_midi_clear_buffer(out);
    if (emitCc) {
      unsigned char cc[]={static_cast<unsigned char>(176|i),42,87};
      if (jack_midi_event_write(out,0,cc,3)) return 5;
    }
    bool attack = transport == JackTransportRolling &&
                  (mask.load() & (1u << i)) && (loopLength-phase)%loopLength<n;
    bool release = held[i] && ((24576+loopLength-phase)%loopLength<n || !(mask.load() & (1u << i)) ||
                               transport != JackTransportRolling);
    if (attack || release) {
      unsigned char data[] = {
          static_cast<unsigned char>((attack ? 144 : 128) | i),
          static_cast<unsigned char>(60 + i),
          static_cast<unsigned char>(attack ? 100 : 0)};
      unsigned offset=attack?(loopLength-phase)%loopLength:
        transport==JackTransportRolling && (mask.load() & (1u<<i))?(24576+loopLength-phase)%loopLength:0;
      if (!jack_midi_event_write(out, offset, data, 3))
        held[i] = attack;
    }
  }
  return 0;
}
int process(jack_nframes_t n, void *) {
  jack_position_t p{};
  jack_transport_query(client, &p);
  for (unsigned i = 0; i < 3; ++i) {
    auto in = jack_port_get_buffer(inputs[i], n);
    for (unsigned j = 0; j < jack_midi_get_event_count(in); ++j) {
      jack_midi_event_t e;
      jack_midi_event_get(&e, in, j);
      if (e.size == 3 && count < events.size() &&
          (((e.buffer[0] & 240) != 176 && e.buffer[1] >= 60 && e.buffer[1] <= 62) ||
           ((e.buffer[0] & 240) == 176 && (nativeRoutes || e.buffer[1] == 64 || e.buffer[1] >= 120)))) {
        auto index = count.load();
        events[index] = {i,           fanout ? jack_last_frame_time(client) : p.frame,     e.time,
                         e.buffer[0], e.buffer[1], e.buffer[2]};
        count.store(index + 1);
      }
    }
  }
  return 0;
}
int main() {
  fanout = std::getenv("CHAIN_FANOUT") != nullptr;
  nativeRoutes = std::getenv("CHAIN_NATIVE_ROUTES") != nullptr;
  jack_status_t s;
  client = jack_client_open("mbh_three_chain_probe", JackNoStartServer, &s);
  sourceClient = jack_client_open("mbh_three_chain_source", JackNoStartServer, &s);
  if (!client || !sourceClient)
    return 2;
  for (unsigned i = 0; i < 3; ++i) {
    inputs[i] = jack_port_register(client, ("in" + std::to_string(i)).c_str(),
                                   JACK_DEFAULT_MIDI_TYPE, JackPortIsInput, 0);
    outputs[i] =
        jack_port_register(sourceClient, ("out" + std::to_string(i)).c_str(),
                           JACK_DEFAULT_MIDI_TYPE, JackPortIsOutput, 0);
  }
  loopLength=std::getenv("CHAIN_TIMING_VERSION") && std::string(std::getenv("CHAIN_TIMING_VERSION"))=="1"
    ? unsigned(std::llround(192000.0/jack_get_buffer_size(sourceClient)))*jack_get_buffer_size(sourceClient) : 192000;
  jack_set_process_callback(sourceClient, sourceProcess, nullptr);
  jack_set_process_callback(client, process, nullptr);
  if (jack_activate(sourceClient) || jack_activate(client))
    return 3;
  for (unsigned i = 0; i < 3; ++i) {
    auto name = "mbh_" + std::to_string(fanout ? 1 : i + 1);
    if (jack_connect(client, jack_port_name(outputs[i]),
                     (name + ":midi_in").c_str()) ||
        (!std::getenv("CHAIN_NATIVE_ROUTES") && jack_connect(client, (name + ":midi_out").c_str(),
                     jack_port_name(inputs[i]))))
      return 4;
  }
  std::cout << "READY\n" << std::flush;
  unsigned value;
  while (std::cin >> value) {
    if (fanout && value == 8) jack_transport_stop(client);
    else if (fanout && value == 9) jack_transport_start(client);
    else if (fanout && value == 10) pendingCc = 1;
    else mask = value;
  }
  jack_deactivate(sourceClient);
  jack_deactivate(client);
  jack_client_close(sourceClient);
  jack_client_close(client);
  for (unsigned i = 0; i < count; ++i) {
    auto &e = events[i];
    std::cout << e.chain << ' ' << e.frame << ' ' << e.offset << ' ' << e.status
              << ' ' << e.note << ' ' << e.value << '\n';
  }
  return 0;
}
