#include "../headless/realtime_trace.hpp"
#include <cassert>
#include <cstdlib>
#include <new>
#include <sstream>
#include <iostream>
#include <vector>
#include <sys/syscall.h>
#include <unistd.h>
static thread_local bool inCallback=false;
static thread_local unsigned allocations=0,cpuReads=0,resourceReads=0;
extern "C" int clock_gettime(clockid_t id,timespec* t) noexcept {if(inCallback&&id==CLOCK_THREAD_CPUTIME_ID)++cpuReads;return syscall(SYS_clock_gettime,id,t);}
extern "C" int getrusage(__rusage_who_t who,rusage* u) noexcept {if(inCallback)++resourceReads;return syscall(SYS_getrusage,who,u);}
void* operator new(std::size_t n){if(inCallback)++allocations;if(void* p=std::malloc(n))return p;throw std::bad_alloc();}
void operator delete(void* p) noexcept {std::free(p);}
int main(int argc,char** argv){assert(argc==2||argc==3);bool detailed=argc==2;
 auto trace=new realtime_trace::Trace(argv[1],detailed);
 uint64_t start=realtime_trace::clock(CLOCK_MONOTONIC);
 for(unsigned i=0;i<10000;++i){inCallback=true;{realtime_trace::Trace::Scope s(trace,i*128,128);for(unsigned j=1;j<10;++j)s.mark(j);}inCallback=false;}
 auto elapsed=realtime_trace::clock(CLOCK_MONOTONIC)-start;
 assert(allocations==0);assert(detailed?(cpuReads>0&&resourceReads==20000):(cpuReads==0&&resourceReads==0));delete trace;
 std::ifstream f(argv[1]);std::string line;unsigned records=0;uint64_t previous=0;bool footer=false;uint64_t dropped=0;
 std::getline(f,line);assert(line.find("movement_cc_actions_cpu_ns")!=std::string::npos);
 while(std::getline(f,line)){if(line[0]=='#'){if(line.find("# dropped=")==0){footer=true;dropped=std::stoull(line.substr(line.find('=')+1));}continue;}std::istringstream s(line);std::string cell;std::getline(s,cell,',');auto sample=std::stoull(cell);assert(!records||sample>previous);previous=sample;
 std::vector<uint64_t> fields;fields.push_back(sample);while(std::getline(s,cell,','))fields.push_back(std::stoull(cell));
 assert(fields.size()==30+realtime_trace::Stages*2); // Ten top-level stages plus explicit nested operation brackets.
 assert(fields[5]<=fields[4]+2000);if(!detailed)assert(fields[5]==0); // CPU endpoint must be inside wall bracket.
 uint64_t stageWall=0;for(unsigned j=0;j<10;++j)stageWall+=fields[29+j*2];
 assert(stageWall+fields[27]+fields[28]<=fields[4]);
 ++records;}
 assert(footer&&records>0&&records+dropped==10000);
 std::cout<<"PASS zero callback allocations; ordered bounded ring; "<<records<<" records; mean instrumented scope ns="<<elapsed/10000<<"\n";
}
