static void fragmentTests(){
 for(auto mode:{Traversal::ReverseAll,Traversal::Alternate,Traversal::RandomChaos}){
  Runtime r(8000);Output out;auto emit=[&](auto...args){return out(args...);};auto c=settings();c[0].traversal=mode;c[0].firstOffset=0;c[0].repeats=1;r.configure(c);
  unsigned forward=0,reverse=0;
  realtime=true;
  for(unsigned fragment=0;fragment<24;++fragment){const uint64_t start=fragment*240;const size_t from=out.count;
   for(unsigned note=0;note<3;++note){CHECK(r.source(edge(true,Origin::Live,0,60+note*2),start+note*20,120,emit));CHECK(r.source(edge(false,Origin::Live,0,60+note*2),start+note*20+10,120,emit));}
   CHECK(out.events[from].on&&out.events[from].sample==start&&out.events[from].velocity==100);
   r.render(start,240,emit);unsigned notes[3]{},n=0;
   for(size_t i=from;i<out.count;++i)if(out.events[i].on&&out.events[i].sample>=start+80){CHECK(n<3);notes[n++]=out.events[i].pitch;}
   CHECK(n==3);const bool backwards=notes[0]==64;CHECK((backwards?notes[2]==60:notes[0]==60&&notes[2]==64)&&notes[1]==62);
   forward+=!backwards;reverse+=backwards;
   if(mode==Traversal::ReverseAll)CHECK(backwards);
   if(mode==Traversal::Alternate)CHECK(backwards==bool(fragment%2));
   CHECK(!r.pending()&&!r.sources()&&!r.failed);
  }
  realtime=false;if(mode==Traversal::RandomChaos)CHECK(forward&&reverse);CHECK(!allocations);
 }
 {
  Runtime r(8000);Output out;auto emit=[&](auto...args){return out(args...);};auto c=settings();c[0].traversal=Traversal::ReverseAll;c[0].firstOffset=0;c[0].repeats=1;c[0].gate=2;r.configure(c);
  realtime=true;CHECK(r.source(edge(true),0,120,emit));r.render(0,200,emit);CHECK(r.source(edge(false),250,120,emit));r.render(200,600,emit);realtime=false;
  CHECK(out.events[out.count-1].sample==659&&!out.events[out.count-1].on);CHECK(!r.sources()&&!r.pending()&&!r.failed&&!allocations);
 }
 for(auto action:{SourceAction::StopInstance,SourceAction::StopPhrases,SourceAction::Reset}){
  Runtime r(8000);Output out;auto emit=[&](auto...args){return out(args...);};auto c=settings();c[0].traversal=Traversal::ReverseAll;r.configure(c);
  CHECK(r.source(edge(true,Origin::Phrase,42),0,120,emit));CHECK(r.pending()==1);
  CHECK(r.source({action,{1,Origin::Phrase,42,0,60},0,0},40,120,emit));r.render(0,2000,emit);
  CHECK(out.count==2&&!r.pending()&&!r.sources()&&!r.failed);
 }
 {
  Runtime r(8000);Output out;auto emit=[&](auto...args){return out(args...);};auto c=settings();c[0].traversal=Traversal::ReverseAll;c[0].repeats=32;r.configure(c);
  realtime=true;for(unsigned n=0;n<9;++n)CHECK(r.source(edge(true,Origin::Live,0,60+n),n,120,emit));
  for(unsigned n=0;n<9;++n){CHECK(r.source(edge(false,Origin::Live,0,60+n),20+n,120,emit));}r.render(0,3000,emit);realtime=false;
  CHECK(r.rejected==1&&out.count==18&&!r.sources()&&!r.pending()&&!r.failed&&!allocations);
 }
 {
  Runtime r(8000);Output out;auto emit=[&](auto...args){return out(args...);};auto c=settings();c[0].traversal=Traversal::ReverseAll;r.configure(c);
  CHECK(r.source(edge(true),0,120,emit));c[0].enabled=false;r.configure(c);r.begin(40,emit);
  CHECK(r.sources()==1&&!r.pending());CHECK(r.source(edge(false),50,120,emit));r.render(0,2000,emit);CHECK(out.count==2&&!r.sources());
 }
 {
  Configurations c{};std::istringstream v3("3 1 1 1 0 10 0 .5 1 1 1 1 0 0 1 1 3");CHECK(read(v3,c));CHECK(c[0].traversal==Traversal::RandomChaos);CHECK(json(c).find("\"version\":3")!=std::string::npos);
  std::istringstream bad("3 1 1 1 0 10 0 .5 1 1 1 1 0 0 1 1 4");CHECK(!read(bad,c));
 }
}
