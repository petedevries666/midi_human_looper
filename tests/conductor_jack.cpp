// Actual JACK input/output fixture. No engine emulation or callback allocations.
#include <jack/jack.h>
#include <jack/midiport.h>
#include <array>
#include <atomic>
#include <iostream>
struct Packet{unsigned st=0,note=0,value=0;};
struct Event{unsigned long long frame=0;unsigned offset=0,st=0,note=0,value=0;};
static std::array<Packet,256> queue;
static std::array<Event,16384> events;
static std::atomic<unsigned> read{0},write{0};
static unsigned count=0;static bool overflow=false;
static jack_client_t* client;static jack_port_t *input,*output;
static int process(jack_nframes_t frames,void*){
  auto out=jack_port_get_buffer(output,frames);jack_midi_clear_buffer(out);
  unsigned budget=64;
  while(read.load()!=write.load()&&budget--){auto p=queue[read.load()%queue.size()];unsigned char bytes[]={static_cast<unsigned char>(p.st),static_cast<unsigned char>(p.note),static_cast<unsigned char>(p.value)};
    if(jack_midi_event_write(out,frames>16?16:0,bytes,3))return 1;++read;}
  auto in=jack_port_get_buffer(input,frames);
  for(unsigned j=0;j<jack_midi_get_event_count(in);++j){jack_midi_event_t e;jack_midi_event_get(&e,in,j);
    if(e.size==3&&((e.buffer[0]&240)==128||(e.buffer[0]&240)==144||((e.buffer[0]&240)==176&&(e.buffer[1]==64||e.buffer[1]>=120)))){
      if(count==events.size()){overflow=true;continue;}
      auto &v=events[count++];v.frame=jack_last_frame_time(client);v.offset=e.time;v.st=e.buffer[0];v.note=e.buffer[1];v.value=e.buffer[2];}}
  return 0;
}
int main(){jack_status_t status;client=jack_client_open("conductor_probe",JackNoStartServer,&status);if(!client)return 2;
  input=jack_port_register(client,"observe",JACK_DEFAULT_MIDI_TYPE,JackPortIsInput,0);output=jack_port_register(client,"footswitch",JACK_DEFAULT_MIDI_TYPE,JackPortIsOutput,0);
  jack_set_process_callback(client,process,nullptr);if(jack_activate(client))return 3;
  if(jack_connect(client,"mbmf_d:midi_out",jack_port_name(input))||jack_connect(client,jack_port_name(output),"mbmf_d:midi_in"))return 4;
  std::cout<<"READY\n"<<std::flush;unsigned st,note,value;
  while(std::cin>>st>>note>>value){if(write-read>=queue.size()||st<128||st>239||note>127||value>127)return 5;Packet p;p.st=st;p.note=note;p.value=value;queue[write.load()%queue.size()]=p;++write;}
  jack_deactivate(client);jack_client_close(client);
  for(unsigned j=0;j<count;++j){auto e=events[j];std::cout<<e.frame<<' '<<e.offset<<' '<<e.st<<' '<<e.note<<' '<<e.value<<'\n';}
  return overflow?6:0;
}
