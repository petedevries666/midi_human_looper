#include "../headless/midi_thru.hpp"
#include <cassert>
#include <iostream>

int main(){
  using namespace midi_thru;
  Configuration patch{};Inputs inputs{};Runtime runtime;
  inputs[1].source=7;inputs[1].connected=true;
  auto update=runtime.configure(patch,inputs);
  assert(update.modes[16]==1 && update.modes[0]==0);
  assert(update.close[16]);
  update=runtime.configure(patch,inputs);
  for(bool close:update.close)assert(!close);
  patch[0].source=7;patch[0].channels[2]=0;
  update=runtime.configure(patch,inputs);
  assert(update.close[18] && !update.close[17] && update.modes[18]==0);
  // Reusing a bus for another device must release the previous device's notes
  // even when the new device has exactly the same effective channel policies.
  inputs[1].source=8;
  update=runtime.configure(patch,inputs);
  assert(update.modes[18]==1);
  for(unsigned ch=0;ch<Channels;++ch)assert(update.close[16+ch]);
  inputs[1].connected=false;
  update=runtime.configure(patch,inputs);
  for(unsigned ch=0;ch<Channels;++ch){assert(update.close[16+ch]);assert(update.modes[16+ch]==0);}
  // Invalid carriers do not partially overwrite the prior patch configuration.
  const auto saved=json(patch);
  std::istringstream invalid("1 1 7 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 3");
  assert(!read(invalid,patch));assert(json(patch)==saved);
  const auto oldSource=inputs[1].source;
  std::istringstream invalidInputs("1 1 1 8 2");
  assert(!readInputs(invalidInputs,inputs));assert(inputs[1].source==oldSource);
  std::cout<<"PASS MIDI THRU policy transitions, disconnected inputs and transactional carriers\n";
}
