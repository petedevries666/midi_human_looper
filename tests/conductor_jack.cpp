// Actual JACK input/output fixture. No engine emulation or callback allocations.
#include <jack/jack.h>
#include <jack/midiport.h>
#include <array>
#include <atomic>
#include <iostream>
struct Packet{unsigned st=0,note=0,value=0,offset=16;};
struct Event{unsigned long long frame=0;unsigned offset=0,st=0,note=0,value=0;};
static std::array<Packet,256> queue;
#ifndef MBMF_TEST_EVENT_CAPACITY
#define MBMF_TEST_EVENT_CAPACITY 16384
#endif
static std::array<Event,MBMF_TEST_EVENT_CAPACITY> events;
static std::atomic<unsigned> read{0},write{0};
static unsigned count=0;static bool overflow=false;
static jack_client_t* client;static jack_port_t *input,*output;
#ifdef MBMF_TEST_ACYCLIC
static jack_client_t* sourceClient;
#endif
static int send(jack_nframes_t frames,void*){
  auto out=jack_port_get_buffer(output,frames);jack_midi_clear_buffer(out);
  unsigned budget=64;
  while(read.load()!=write.load()&&budget--){auto p=queue[read.load()%queue.size()];unsigned char bytes[]={static_cast<unsigned char>(p.st),static_cast<unsigned char>(p.note),static_cast<unsigned char>(p.value)};
    if(jack_midi_event_write(out,std::min(p.offset,unsigned(frames-1)),bytes,3))return 1;++read;}
  return 0;
}
static int process(jack_nframes_t frames,void*){
#ifndef MBMF_TEST_ACYCLIC
  if(send(frames,nullptr))return 1;
#endif
#ifdef MBMF_TEST_ACYCLIC
  const auto observedFrame=jack_last_frame_time(client);
#endif
  auto in=jack_port_get_buffer(input,frames);
  for(unsigned j=0;j<jack_midi_get_event_count(in);++j){jack_midi_event_t e;jack_midi_event_get(&e,in,j);
#ifdef MBMF_TEST_FORBID_PRIVATE_CONTROL
    if(e.size==17&&e.buffer[0]==240&&e.buffer[1]==125&&e.buffer[2]==77)overflow=true;
#endif
#if defined(MBMF_TEST_CAPTURE_CHANNEL_VOICE)
    if((e.size==2||e.size==3)&&(e.buffer[0]&240)>=128&&(e.buffer[0]&240)<240){
#elif defined(MBMF_TEST_CAPTURE_ALL_CC)
    if(e.size==3&&((e.buffer[0]&240)==128||(e.buffer[0]&240)==144||(e.buffer[0]&240)==176)){
#else
    if(e.size==3&&((e.buffer[0]&240)==128||(e.buffer[0]&240)==144||((e.buffer[0]&240)==176&&(e.buffer[1]==64||e.buffer[1]>=120)))){
#endif
      if(count==events.size()){overflow=true;continue;}
      auto &v=events[count++];
#ifdef MBMF_TEST_ACYCLIC
      v.frame=observedFrame;
#else
      v.frame=jack_last_frame_time(client);
#endif
      v.offset=e.time;v.st=e.buffer[0];v.note=e.buffer[1];v.value=e.size==3?e.buffer[2]:0;}}
  return 0;
}
int main(){
#ifdef MBMF_TEST_ACYCLIC
  // Observation pages must be faulted before JACK activation, not by the sink.
  volatile Event *warm=events.data();for(unsigned j=0;j<events.size();++j)warm[j].frame=0;
#endif
  jack_status_t status;client=jack_client_open("conductor_probe",JackNoStartServer,&status);if(!client)return 2;
  input=jack_port_register(client,"observe",JACK_DEFAULT_MIDI_TYPE,JackPortIsInput,0);
#ifdef MBMF_TEST_ACYCLIC
  sourceClient=jack_client_open("conductor_send",JackNoStartServer,&status);if(!sourceClient)return 2;
  output=jack_port_register(sourceClient,"footswitch",JACK_DEFAULT_MIDI_TYPE,JackPortIsOutput,0);
  jack_set_process_callback(sourceClient,send,nullptr);if(jack_activate(sourceClient))return 3;
#else
  output=jack_port_register(client,"footswitch",JACK_DEFAULT_MIDI_TYPE,JackPortIsOutput,0);
#endif
  jack_set_process_callback(client,process,nullptr);if(jack_activate(client))return 3;
  if(jack_connect(client,"mbmf_d:midi_out",jack_port_name(input))||jack_connect(client,jack_port_name(output),"mbmf_d:midi_in"))return 4;
  std::cout<<"READY\n"<<std::flush;unsigned st,note,value;
  while(std::cin>>st>>note>>value){if(write-read>=queue.size()||st<128||st>239||note>127||value>127)return 5;Packet p;p.st=st;p.note=note;p.value=value;
#ifdef MBMF_TEST_CAPTURE_ALL_CC
    if(!(std::cin>>p.offset))return 5;
#endif
    queue[write.load()%queue.size()]=p;++write;}
#ifdef MBMF_TEST_ACYCLIC
  jack_deactivate(sourceClient);jack_client_close(sourceClient);
#endif
  jack_deactivate(client);jack_client_close(client);
  for(unsigned j=0;j<count;++j){auto e=events[j];std::cout<<e.frame<<' '<<e.offset<<' '<<e.st<<' '<<e.note<<' '<<e.value<<'\n';}
  return overflow?6:0;
}
