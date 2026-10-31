static void routingTests(){
 // Transform wet attacks at delivery, then release the captured final pitch.
 // A filtered destination must neither mute DRY nor create an orphan Off.
 for(bool filtered:{false,true}){
  Runtime r(8000);Output out;auto emit=[&](auto...args){return out(args...);};auto c=settings();
  c[0].destinationTransforms=true;c[0].routing=Routing::Cycle;c[0].channelMask=2;c[0].repeats=1;
  struct Target {int transpose=12;bool filtered=false;unsigned calls=0;} target;target.filtered=filtered;
  r.setDestinationTransform([](void*context,uint32_t origin,uint8_t ch,uint8_t&pitch,uint8_t&vel){
   auto&t=*static_cast<Target*>(context);++t.calls;CHECK(origin==1&&ch==1);
   if(t.filtered)return false;pitch=uint8_t(pitch+t.transpose);vel=25;return true;
  },&target);r.configure(c);
  realtime=true;CHECK(r.source(edge(true),0,120,emit));CHECK(r.source(edge(false),40,120,emit));
  r.render(0,81,emit);target.transpose=-12;r.render(81,175,emit);realtime=false;
  CHECK(target.calls==1&&!r.failed&&!r.pending()&&!r.sources()&&!allocations);
  CHECK(out.count==(filtered?2u:4u));CHECK(out.events[0].pitch==60&&out.events[0].velocity==100);
  if(!filtered){CHECK(out.events[2].on&&out.events[2].pitch==72&&out.events[2].velocity==25);CHECK(!out.events[3].on&&out.events[3].pitch==72);}
 }
 {
  Configurations original{};auto &c=original[0];c.id=c.instrument=1;c.destinationTransforms=true;
  const auto text=json(original);CHECK(text.find("\"version\":5")!=std::string::npos);
  auto start=text.find('['),end=text.find(']');auto wire=text.substr(start+1,end-start-1);std::replace(wire.begin(),wire.end(),',',' ');
  Configurations restored{};std::istringstream in(wire);CHECK(read(in,restored));CHECK(restored[0].destinationTransforms);
 }
 for(auto traversal:{Traversal::Forward,Traversal::ReverseAll,Traversal::Alternate,Traversal::RandomChaos})
 for(auto routing:{Routing::Cycle,Routing::Random,Routing::Pattern}){
  Runtime r(8000);Output out;auto emit=[&](auto...args){return out(args...);};auto c=settings();
  c[0].traversal=traversal;c[0].routing=routing;c[0].channelMask=(1u<<1)|(1u<<4)|(1u<<15);c[0].noRepeat=true;
  c[0].patternLength=4;c[0].pattern={1,4,1,15};c[0].repeats=8;r.configure(c);
  realtime=true;
  for(unsigned n=0;n<3;++n){CHECK(r.source(edge(true,Origin::Live,0,60+n),n*20,120,emit));CHECK(r.source(edge(false,Origin::Live,0,60+n),n*20+10,120,emit));}
  // Changes after admission affect future series, never the queued Off channels.
  auto changed=c;changed[0].channelMask=1;changed[0].pattern={0};r.configure(changed);
  r.render(0,1200,emit);realtime=false;
  unsigned wet=0;std::array<unsigned,16*128> held{};std::array<int,8> perRepeat{};perRepeat.fill(-1);
  std::array<int,3> previous{};previous.fill(-1);
  for(size_t i=0;i<out.count;++i){const auto&e=out.events[i];auto&count=held[e.ch*128+e.pitch];
   if(e.on){++count;if(e.velocity==50){++wet;CHECK(e.ch==1||e.ch==4||e.ch==15);
    const unsigned base=traversal==Traversal::Forward?80:160;const unsigned repeat=unsigned((e.sample-base)/80);CHECK(repeat<8);
    if(routing==Routing::Cycle)CHECK((e.ch==std::array<unsigned,3>{1,4,15}[repeat%3]));
    if(routing==Routing::Pattern)CHECK(e.ch==c[0].pattern[repeat%4]);
    const unsigned note=e.pitch-60;if(routing==Routing::Random){CHECK(previous[note]!=int(e.ch));previous[note]=int(e.ch);}
    if(perRepeat[repeat]<0)perRepeat[repeat]=int(e.ch);else CHECK(perRepeat[repeat]==int(e.ch));
   }}else{CHECK(count>0);--count;}
  }
  CHECK(wet==24&&!r.failed&&!r.pending()&&!r.sources()&&!allocations);
  for(auto count:held)CHECK(count==0);
 }
 {
  Configuration c;c.id=c.instrument=1;c.routing=Routing::Cycle;CHECK(!valid(c));c.channelMask=65536;CHECK(!valid(c));
  c.channelMask=1;CHECK(valid(c));c.routing=Routing::Pattern;CHECK(!valid(c));c.patternLength=1;CHECK(valid(c));c.pattern[0]=16;CHECK(!valid(c));
 }
 {
  Configuration c;c.id=c.instrument=1;c.routing=Routing::Random;c.channelMask=1u<<15;c.noRepeat=true;c.repeats=32;
  std::array<uint8_t,32> channels{};routeChannels(c,0,123,channels);for(auto ch:channels)CHECK(ch==15);
 }
 {
  Configurations original{};auto&c=original[0];c.id=c.instrument=1;c.routing=Routing::Pattern;c.patternLength=4;c.pattern={1,4,1,15};
  std::string text=json(original);CHECK(text.find("\"version\":4")!=std::string::npos);
  auto start=text.find('['),end=text.find(']');std::string wire=text.substr(start+1,end-start-1);std::replace(wire.begin(),wire.end(),',',' ');
  Configurations restored{};std::istringstream in(wire);CHECK(read(in,restored));CHECK(restored[0].routing==Routing::Pattern&&restored[0].pattern==c.pattern&&restored[0].patternLength==4);
 }
}
