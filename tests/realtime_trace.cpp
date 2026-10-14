#include "../headless/realtime_trace.hpp"
#include <cassert>
#include <cstdlib>
#include <new>
#include <sstream>
#include <iostream>
static thread_local bool inCallback=false;
static thread_local unsigned allocations=0;
void* operator new(std::size_t n){if(inCallback)++allocations;if(void* p=std::malloc(n))return p;throw std::bad_alloc();}
void operator delete(void* p) noexcept {std::free(p);}
int main(int argc,char** argv){assert(argc==2);
 auto trace=new realtime_trace::Trace(argv[1]);
 uint64_t start=realtime_trace::clock(CLOCK_MONOTONIC);
 for(unsigned i=0;i<10000;++i){inCallback=true;{realtime_trace::Trace::Scope s(trace,i*128,128);for(unsigned j=1;j<10;++j)s.mark(j);}inCallback=false;}
 auto elapsed=realtime_trace::clock(CLOCK_MONOTONIC)-start;
 assert(allocations==0);delete trace;
 std::ifstream f(argv[1]);std::string line;unsigned records=0;uint64_t previous=0;bool footer=false;uint64_t dropped=0;
 std::getline(f,line);assert(line.find("movement_cc_actions_cpu_ns")!=std::string::npos);
 while(std::getline(f,line)){if(line[0]=='#'){footer=true;dropped=std::stoull(line.substr(line.find('=')+1));continue;}std::istringstream s(line);std::string cell;std::getline(s,cell,',');auto sample=std::stoull(cell);assert(!records||sample>previous);previous=sample;++records;}
 assert(footer&&records>0&&records+dropped==10000);
 std::cout<<"PASS zero callback allocations; ordered bounded ring; "<<records<<" records; mean instrumented scope ns="<<elapsed/10000<<"\n";
}
