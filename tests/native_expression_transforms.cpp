#include "../headless/native_expression_transforms.hpp"
#include <cassert>
#include <iostream>
using namespace native_expression;
int main(){
 VelocityCurve c;
 assert(c.valid());
 for(unsigned v=1;v<=127;v++)assert(c.process(v)==v);
 assert(c.process(0)==0);
 c.points[0].y=1;c.points[1].y=0;
 assert(c.valid()&&c.process(1)==127&&c.process(127)==1);
 c.amount=0;for(unsigned v=1;v<=127;v++)assert(c.process(v)==v);
 c.amount=1;
 c.points[0].y=0;c.points[1].y=1;
 c.count=4;c.points[1]={.25,1};c.points[2]={.75,0};c.points[3]={1,1};
 assert(c.valid());
 c.points[2].x=.2;assert(!c.valid());c.points[2].x=.75;
 Humanizer h;h.timingRangeMs=2000;h.timingBiasMs=0;h.velocityVariation=1;
 assert(h.valid());
 assert(h.sampleShift(4,2,48000)==h.sampleShift(4,2,48000));
 for(uint64_t i=0;i<5000;i++){
   auto s=h.sampleShift(i,i,48000);assert(s>=-96000&&s<=96000);
   auto v=h.noteVelocity(127,i,i);assert(v>=1&&v<=127);
   assert(h.noteVelocity(0,i,i)==0);
 }
 auto s=h.sampleShift(4,2,48000);
 const auto on=delayedSample(200000,s),off=delayedSample(250000,s);
 assert(off-on==50000);
 assert(delayedSample(100,-500)==0);
 h.timingRangeMs=2001;assert(!h.valid()&&h.sampleShift(1,1,48000)==0);
 std::cout<<"native expression foundation: PASS\n";
}
