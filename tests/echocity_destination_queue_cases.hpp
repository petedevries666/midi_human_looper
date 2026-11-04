static void destinationQueueTests(){
 {
  DestinationQueue q;Event e{};e.voice={0,1,TokenDomain::Voice};e.channel=1;e.pitch=60;e.velocity=100;e.on=true;
  realtime=true;
  for(unsigned j=0;j<256;++j){e.voice.slot=j;CHECK(q.attack(e,2,20));}
  CHECK(q.pending()==256&&q.leases()==256);CHECK(!q.attack(e,2,20));
  for(unsigned j=0;j<256;++j){e.voice.slot=j;CHECK(q.release(e,40));}
  CHECK(q.pending()==512&&!q.leases());unsigned count=0;
  q.drain([&](const DestinationQueue::Entry&row){CHECK(row.offset==(count<256?20u:40u));CHECK(row.on==(count<256));CHECK(row.target==2&&row.pitch==60);++count;});
  realtime=false;CHECK(count==512&&!q.pending()&&!q.leases()&&!allocations);
 }
 for(auto traversal:{Traversal::Forward,Traversal::ReverseAll,Traversal::Alternate,Traversal::RandomChaos}){
  Runtime r(8000);DestinationQueue q;Output out;auto emit=[&](auto...args){return out(args...);};auto c=settings();
  c[0].destinationTransforms=2;c[0].routing=Routing::Cycle;c[0].channelMask=2;c[0].traversal=traversal;
  r.setDestinationIngress([](void*context,const Event&e){auto&q=*static_cast<DestinationQueue*>(context);return e.on?q.attack(e,2,unsigned(e.sample)):q.release(e,unsigned(e.sample));},&q);
  r.configure(c);realtime=true;CHECK(r.source(edge(true),0,120,emit));CHECK(r.source(edge(false),40,120,emit));
  r.render(0,800,emit);CHECK(out.count==2);CHECK(q.pending()==4&&!q.leases());
  unsigned on=0,off=0;q.drain([&](const DestinationQueue::Entry&e){CHECK(e.channel==1&&e.pitch==60);e.on?++on:++off;});
  realtime=false;CHECK(on==2&&off==2&&!r.failed&&!r.sources()&&!r.pending()&&!allocations);
 }
 {
  Runtime r(8000);Output out;auto emit=[&](auto...args){return out(args...);};auto c=settings();c[0].dry=0;c[0].destinationTransforms=2;r.configure(c);
  auto on=edge(true,Origin::Echo);auto off=edge(false,Origin::Echo);
  realtime=true;CHECK(r.source(on,0,120,emit));CHECK(r.source(off,40,120,emit));r.render(0,800,emit);realtime=false;
  CHECK(out.count==2&&out.events[0].velocity==100&&!r.pending()&&!r.sources()&&!r.failed&&!allocations);
 }
}
