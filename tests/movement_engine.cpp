#include "../headless/movement_engine.hpp"
#include <cassert>
#include <iostream>
#include <vector>
#include <chrono>
struct Event{uint64_t sample;unsigned ch,cc,value;};
int main(){
 unsigned checks=0;auto check=[&](bool ok){++checks;assert(ok);};
 // Movement playback and the Controller/editor share the same segment bend.
 for(double bend:{-.98,-.5,0.,.5,.98}){
  movement::Definition d;d.curve({{0,.1,bend},{.4,.9,-bend},{1,.2,0}});
  controller::Curve expected;expected.count=3;expected.points[0]={0,.1,bend};expected.points[1]={.4,.9,-bend};expected.points[2]={1,.2,0};
  for(unsigned i=0;i<=1000;++i)check(std::abs(d.value(i/1000.)-expected.evaluate(i/1000.))<1e-12);
  d.hold=true;check(d.value(.2)==.1&&d.value(.7)==.9&&d.value(1)==.2);
 }
 {
  controller::Host host;movement::Runtime rt(host,48000);movement::Prepared p;p.rate=100;
  movement::Definition d;d.soft=false;d.duration=.1;d.number=74;d.restValue=.5;d.curve({{0,.2,0},{1,.8,0}});
  d.chargeDuration.enabled=true;d.chargeDuration.from=.1;d.chargeDuration.to=2;d.chargeDuration.factor=16;
  d.chargeAmplitude.enabled=true;d.chargeAmplitude.from=0;d.chargeAmplitude.to=.25;d.chargeAmplitude.factor=16;p.definitions={d};rt.install(std::move(p));
  auto resolve=[](const controller::Binding&,uint32_t&,double&){return false;};auto apply=[](const controller::Binding&,double){return true;};unsigned value=0;auto emit=[&](uint64_t,unsigned,unsigned,unsigned v){value=v;return true;};
  check(rt.start(0,0,resolve,0,1,.8));rt.render(1,emit,apply);check(value==54);rt.render(48001,emit,apply);check(rt.active==1);rt.render(96001,emit,apply);check(rt.active==0&&value==73);
 }
 for(unsigned cycle:{1u,2u}){
  controller::Host host;movement::Runtime rt(host,48000);movement::Prepared p;p.rate=100;
  movement::Definition d;d.cycle=cycle;d.soft=false;d.duration=1;d.number=74;d.curve({{0,0,0},{1,1,0}});p.definitions={d};rt.install(std::move(p));
  auto resolve=[](const controller::Binding&,uint32_t&,double&){return false;};auto apply=[](const controller::Binding&,double){return true;};std::vector<Event> events;
  auto emit=[&](uint64_t t,unsigned ch,unsigned cc,unsigned value){events.push_back({t,ch,cc,value});return true;};
  check(rt.start(0,0,resolve));rt.render(48000+1,emit,apply);check(rt.active==1&&events.back().sample==48000&&events.back().value==0);
  auto middle=std::find_if(events.begin(),events.end(),[](const Event &e){return e.sample==24000;});check(middle!=events.end()&&middle->value==(cycle==2?127:64));
  rt.render(96000+1,emit,apply);check(rt.active==1&&events.back().sample==96000&&events.back().value==0);rt.stop(0);check(rt.active==0);
  d.gated=true;d.releaseSeconds=.1;d.restValue=.2;p.definitions={d};rt.install(std::move(p));check(rt.start(0,100000,resolve,2,9));rt.render(150000,emit,apply);rt.release(2,9,150000);rt.render(154801,emit,apply);check(rt.active==0&&events.back().value==25);
 }
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
 {
  // Distinct movements share ownership by channel+CC; incoming policy wins.
  controller::Host host;movement::Runtime rt(host,48000);movement::Prepared p;p.rate=100;
  movement::Definition a;a.id="first";a.channel=2;a.number=5;a.soft=false;a.duration=2;a.curve({{0,.8,0},{1,.8,0}});
  auto b=a;b.id="second";b.soft=true;b.glide=.4;b.curve({{0,.2,0},{1,.2,0}});
  auto c=b;c.id="direct";c.soft=false;c.curve({{0,.9,0},{1,.9,0}});
  auto other=b;other.id="other-channel";other.channel=3;p.definitions={a,b,c,other};rt.install(std::move(p));
  std::vector<Event> out;auto emit=[&](uint64_t t,unsigned ch,unsigned cc,unsigned value){out.push_back({t,ch,cc,value});return true;};auto apply=[](const controller::Binding&,double){return true;};auto resolve=[](const controller::Binding&,uint32_t&,double&){return false;};
  check(rt.start(0,0,resolve));rt.render(4800,emit,apply);
  check(rt.start(1,4800,resolve));rt.render(4801,emit,apply);check(rt.active==1&&out.back().value==102);
  rt.render(14401,emit,apply);check(out.back().value==64); // halfway through incoming .4s glide
  rt.render(24001,emit,apply);check(out.back().value==25);
  check(rt.start(2,24001,resolve));rt.render(24002,emit,apply);check(rt.active==1&&out.back().value==114);
  check(rt.start(3,24002,resolve));rt.render(24483,emit,apply);check(rt.active==2);rt.panic();
 }
 {
  controller::Host host;movement::Runtime rt(host,48000);movement::Prepared p;p.rate=100;
  movement::Definition d;d.id="held";d.number=5;d.soft=false;d.gated=true;d.duration=.2;d.releaseSeconds=.2;d.restValue=.25;d.curve({{0,0,0},{1,1,0}});p.definitions={d};rt.install(std::move(p));
  auto resolve=[](const controller::Binding&,uint32_t&,double&){return false;};auto apply=[](const controller::Binding&,double){return true;};unsigned value=0;auto emit=[&](uint64_t,unsigned,unsigned,unsigned v){value=v;return true;};
  check(rt.start(0,0,resolve,2,10));rt.render(24001,emit,apply);check(rt.active==1&&value==127);
  rt.release(2,9,24001);rt.render(24482,emit,apply);check(rt.active==1&&value==127);
  rt.release(2,10,24482);rt.render(29283,emit,apply);check(value==79&&rt.active==1);
  rt.render(34083,emit,apply);check(value==32&&rt.active==0);
  check(rt.start(0,40000,resolve,2,11));rt.render(44000,emit,apply);rt.release(2,11,44000);rt.render(45000,emit,apply);
  check(rt.start(0,45000,resolve,2,12));rt.release(2,11,45001);rt.render(55000,emit,apply);check(value==127&&rt.active==1);
  rt.physical(0,5,99,55000);rt.release(2,12,55001);rt.render(65000,emit,apply);check(rt.active==0);rt.panic();
 }
 for(unsigned rate:{10u,25u,50u,100u}){
  controller::Host host;movement::Runtime rt(host,48000);rt.block(8192);movement::Prepared p;p.rate=rate;movement::Definition d;d.soft=false;d.number=74;d.duration=1000;d.curve({{0,0,0},{.1,1,0},{.2,0,0},{1,1,0}});p.definitions={d};rt.install(std::move(p));
  auto resolve=[](const controller::Binding&,uint32_t&,double&){return false;};unsigned volume=0;auto emit=[&](uint64_t,unsigned,unsigned,unsigned){++volume;return true;};auto apply=[](const controller::Binding&,double){return true;};check(rt.start(0,0,resolve));double total=0,maximum=0;
  for(unsigned j=1;j<=1024;++j){auto start=std::chrono::steady_clock::now();rt.render(uint64_t(j)*8192,emit,apply);double us=std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-start).count();total+=us;maximum=std::max(maximum,us);}
  std::cout<<"MOVEMENT_CPU rate="<<rate<<" block=8192 sr=48000 samples="<<1024*8192<<" callbacks=1024 mean_us="<<total/1024<<" max_us="<<maximum<<" emitted="<<volume<<'\n';
 }
 std::cout<<"PASS "<<checks<<" production MOVEMENT runtime/Controller checks\n";
}
