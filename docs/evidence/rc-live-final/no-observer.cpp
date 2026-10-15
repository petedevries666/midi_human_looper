// Negative control: actual JACK callback with no MBMF engine/EEL/Controller.
#include "../headless/realtime_trace.hpp"
#include <jack/jack.h>
#include <jack/midiport.h>
#include <cstdio>
#include <memory>
struct Control {realtime_trace::Trace* trace;jack_client_t* client;jack_port_t *in,*out;uint64_t sample=0;std::atomic<uint64_t> xruns{0};};
static int process(jack_nframes_t n,void* opaque){auto &c=*static_cast<Control*>(opaque);realtime_trace::Trace::Scope s(c.trace,c.sample,n);c.sample+=n;
 {realtime_trace::Trace::Scope::Probe p(s,10);s.value.jackFrame=jack_last_frame_time(c.client);}
 void *in,*out;
 {realtime_trace::Trace::Scope::Probe p(s,11);out=jack_port_get_buffer(c.out,n);}
 {realtime_trace::Trace::Scope::Probe p(s,12);jack_midi_clear_buffer(out);}
 {realtime_trace::Trace::Scope::Probe p(s,15);in=jack_port_get_buffer(c.in,n);}
 {realtime_trace::Trace::Scope::Probe p(s,16);s.value.inputEvents=jack_midi_get_event_count(in);}
 s.value.xruns=c.xruns.load();return 0;
}
int main(int argc,char** argv){if(argc!=3)return 2;std::unique_ptr<realtime_trace::Trace> trace;jack_status_t status;Control c;c.trace=trace.get();c.client=jack_client_open("mbmf_negative_control",JackNoStartServer,&status);if(!c.client)return 3;c.in=jack_port_register(c.client,"in",JACK_DEFAULT_MIDI_TYPE,JackPortIsInput,0);c.out=jack_port_register(c.client,"out",JACK_DEFAULT_MIDI_TYPE,JackPortIsOutput,0);jack_set_process_callback(c.client,process,&c);jack_set_xrun_callback(c.client,[](void* p){++static_cast<Control*>(p)->xruns;return 0;},&c);if(jack_activate(c.client))return 4;
 std::this_thread::sleep_for(std::chrono::seconds(1));auto start=realtime_trace::clock(CLOCK_MONOTONIC);auto before=c.xruns.load();std::this_thread::sleep_for(std::chrono::seconds(std::stoul(argv[2])));auto end=realtime_trace::clock(CLOCK_MONOTONIC);auto after=c.xruns.load();jack_deactivate(c.client);jack_client_close(c.client);printf("{\"startNs\":%llu,\"endNs\":%llu,\"xruns\":%llu}\n",(unsigned long long)start,(unsigned long long)end,(unsigned long long)(after-before));}
