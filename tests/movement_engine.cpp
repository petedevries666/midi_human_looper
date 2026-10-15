#include "../headless/movement_engine.hpp"
#include <cassert>
#include <iostream>
#include <vector>
#include <chrono>
struct Event{uint64_t sample;unsigned ch,cc,value;};
int main(){
 unsigned checks=0;auto check=[&](bool ok){++checks;assert(ok);};
 for(unsigned sr:{44100u,48000u,96000u})for(unsigned rate:{10u,25u,50u,100u}){
  controller::Host host;movement::Runtime rt(host,sr);movement::Prepared p;p.rate=rate;
  movement::Definition d;d.soft=false;d.duration=1;d.number=7;d.curve({{0,0,0},{.5,.5,0},{1,1,0}});p.definitions.push_back(d);rt.install(std::move(p));
  std::vector<Event> out;auto emit=[&](uint64_t t,unsigned ch,unsigned cc,unsigned value){out.push_back({t,ch,cc,value});return true;};auto apply=[](const controller::Binding&,double){return true;};auto resolve=[](const controller::Binding&,uint32_t&,double&){return false;};
  check(rt.start(0,16,resolve));for(uint64_t t=128;t<sr+2048;t+=128)rt.render(t,emit,apply);
  check(out.front().sample==16&&out.front().value==0&&out.back().sample==sr+16&&out.back().value==127);check(out.size()==rate+1);check(rt.active==0);
  for(unsigned i=0;i<out.size();++i){check(out[i].sample==16+uint64_t(std::ceil(i*double(sr)/rate)));check(out[i].value==unsigned(std::floor(i*127./rate+.5)));}
 }
 {
  controller::Host host;movement::Runtime rt(host,48000);movement::Prepared p;movement::Definition a;a.number=11;a.soft=false;a.curve({{0,.2,0},{.5,.2,0},{1,.9,0}});a.hold=true;p.definitions={a,a};p.definitions[1].curve({{0,.8,0},{1,.4,0}});rt.install(std::move(p));
  std::vector<Event> out;auto emit=[&](uint64_t t,unsigned ch,unsigned cc,unsigned value){out.push_back({t,ch,cc,value});return true;};auto apply=[](const controller::Binding&,double){return true;};auto resolve=[](const controller::Binding&,uint32_t&,double&){return false;};
  check(rt.start(0,0,resolve));rt.render(24000,emit,apply);check(out.size()==1&&out[0].value==25);check(rt.start(1,24000,resolve));rt.render(30000,emit,apply);check(rt.active==1&&out.back().value==102);
  rt.physical(0,11,77);auto count=out.size();rt.render(96000,emit,apply);check(!rt.active&&out.size()==count);
  check(rt.start(0,96000,resolve));rt.panic();rt.render(192000,emit,apply);check(out.size()==count);
  rt.physical(0,11,77,240220);check(rt.start(0,240016,resolve));rt.render(248192,emit,apply);check(!rt.active&&out.size()==count);
 }
 {
  controller::Host host;host.stagePerformanceTarget(42,.8);movement::Runtime rt(host,48000);movement::Prepared p;movement::Definition d;d.cc=false;d.duration=1;d.glide=.2;d.curve({{0,0,0},{1,1,0}});p.definitions={d};rt.install(std::move(p));
  auto resolve=[](const controller::Binding&,uint32_t &id,double &v){id=42;v=.8;return true;};auto emit=[](uint64_t,unsigned,unsigned,unsigned){return true;};double value=-1;auto apply=[&](const controller::Binding&,double v){value=v;return true;};
  check(rt.start(0,0,resolve));rt.render(4800,emit,apply);check(std::abs(value-.45)<1e-10);
  controller::Source s;s.id=1;host.source(s);controller::Binding b;b.policy.id=1;b.policy.source=1;b.policy.target=42;b.instrument=1;b.kind=1;b.base=.8;check(host.bind(b));check(host.testSource(1,90,.1));rt.render(9600,emit,apply);check(!rt.active&&std::abs(host.target(42)->effective-90./127)<1e-10);
 }
 {
  controller::Host host;movement::Runtime rt(host,48000);rt.block(8192);movement::Prepared p;p.rate=100;
  for(unsigned i=0;i<4;++i){movement::Definition d;d.number=20+i;d.curve({{0,0,0},{1,1,0}});p.definitions.push_back(d);}rt.install(std::move(p));auto resolve=[](const controller::Binding&,uint32_t&,double&){return false;};
  check(rt.start(0,0,resolve)&&rt.start(1,0,resolve)&&rt.start(2,0,resolve));check(!rt.start(3,0,resolve));check(rt.active==3&&rt.rejected==1);rt.panic();check(rt.active==0);
 }
 for(unsigned rate:{10u,25u,50u,100u}){
  controller::Host host;movement::Runtime rt(host,48000);rt.block(8192);movement::Prepared p;p.rate=rate;movement::Definition d;d.soft=false;d.number=74;d.duration=1000;d.curve({{0,0,0},{.1,1,0},{.2,0,0},{1,1,0}});p.definitions={d};rt.install(std::move(p));
  auto resolve=[](const controller::Binding&,uint32_t&,double&){return false;};unsigned volume=0;auto emit=[&](uint64_t,unsigned,unsigned,unsigned){++volume;return true;};auto apply=[](const controller::Binding&,double){return true;};check(rt.start(0,0,resolve));double total=0,maximum=0;
  for(unsigned j=1;j<=1024;++j){auto start=std::chrono::steady_clock::now();rt.render(uint64_t(j)*8192,emit,apply);double us=std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-start).count();total+=us;maximum=std::max(maximum,us);}
  std::cout<<"MOVEMENT_CPU rate="<<rate<<" block=8192 sr=48000 samples="<<1024*8192<<" callbacks=1024 mean_us="<<total/1024<<" max_us="<<maximum<<" emitted="<<volume<<'\n';
 }
 std::cout<<"PASS "<<checks<<" production MOVEMENT runtime/Controller checks\n";
}
