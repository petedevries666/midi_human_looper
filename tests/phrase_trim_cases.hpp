#include "../headless/phrase_trim.hpp"
static void phrase_trim_cases() {
  using namespace phrase_trim;
  auto r=endpoint({{0,144,60,90},{100,128,60,0},{900,176,1,80}});
  check(r.valid && r.length==101 && r.count==2,"trim discards silent tail and retains last Note Off sample");
  r=endpoint({{0,144,60,90},{10,176,64,127},{100,144,60,0},{400,176,64,0}});
  check(r.valid && r.length==401 && r.count==4,"trim respects CC64 release and velocity-zero Note Off");
  r=endpoint({{0,144,60,90},{0,145,60,90},{10,176,64,127},{100,128,60,0},{200,129,60,0},{400,176,64,0}});
  check(r.valid && r.length==401,"trim tracks sustain independently on each MIDI channel");
  check(!endpoint({}).valid,"empty phrase is unchanged");
  check(!endpoint({{0,144,60,90}}).valid,"unfinished note cannot be trimmed");
  check(!endpoint({{0,144,60,90},{10,176,64,127},{100,128,60,0}}).valid,"unreleased sustain cannot be trimmed");
  check(!endpoint({{0,144,60,90},{10,144,60,90},{100,128,60,0}}).valid,"overlapping same-pitch ownership remains balanced");
  r=endpoint({{0,144,60,90},{100,128,60,0},{100,176,1,80}});
  check(r.valid && r.count==3,"events at the final release timestamp are retained");
}
