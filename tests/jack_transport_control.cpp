// Worker-side JACK transport stimulus/query; no audio callback or hardware ports.
#include <jack/jack.h>
#include <iostream>
#include <string>
int main(){
  jack_status_t status;auto client=jack_client_open("m4_transport",JackNoStartServer,&status);
  if(!client)return 2;
  std::cout<<"READY\n"<<std::flush;
  std::string command;
  while(std::cin>>command){
    if(command=="start")jack_transport_start(client);
    else if(command=="stop")jack_transport_stop(client);
    else if(command=="locate"){unsigned frame;if(!(std::cin>>frame))return 3;jack_transport_locate(client,frame);}
    else if(command!="state")return 4;
    jack_position_t p{};auto state=jack_transport_query(client,&p);
    std::cout<<unsigned(state)<<' '<<p.frame<<'\n'<<std::flush;
  }
  jack_client_close(client);
}
