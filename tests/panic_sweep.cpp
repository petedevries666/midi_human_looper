#include "../headless/panic_sweep.hpp"
#include <cassert>
#include <vector>
#include <iostream>
int main() {
  PanicSweep sweep;assert(!sweep.remaining());sweep.begin();
  std::vector<std::array<uint8_t,3>> events;
  sweep.drain(64,[&](auto event){events.push_back(event);return true;});
  assert(events.size()==64 && sweep.remaining()==1984);
  sweep.drain(64,[](auto){return false;});assert(sweep.remaining()==1984);
  while(sweep.remaining())sweep.drain(64,[&](auto event){events.push_back(event);return true;});
  assert(events.size()==2048);
  for(unsigned i=0;i<2048;++i)assert((events[i]==std::array<uint8_t,3>{{uint8_t(128+i/128),uint8_t(i%128),0}}));
  sweep.begin();sweep.drain(1,[](auto){return true;});sweep.begin();assert(sweep.remaining()==2048);
  std::cout<<"PASS full-channel note coverage, bounded writes, retry and restart\n";
}
