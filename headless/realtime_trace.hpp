#pragma once
// Optional diagnostics: fixed SPSC records in the callback; CSV only on a
// separate consumer thread. No callback allocation, file I/O or waiting.
#include <array>
#include <atomic>
#include <cstdint>
#include <fstream>
#include <stdexcept>
#include <thread>
#include <chrono>
#include <time.h>
#include <sys/resource.h>
#include <pthread.h>
namespace realtime_trace {
inline uint64_t clock(clockid_t id) { timespec t{}; clock_gettime(id,&t); return uint64_t(t.tv_sec)*1000000000+t.tv_nsec; }
constexpr unsigned TopStages=10, Stages=24, Capacity=4096;
struct Record {
 uint64_t sample=0,entry=0,gap=0,wall=0,cpu=0,xruns=0,rejected=0,overflow=0;
 unsigned frames=0,commands=0,pending=0,active=0;
 uint64_t callbackCycle=0,jackFrame=0,noteEvents=0,noteOns=0,ccEvents=0,instanceRejected=0;
 unsigned phraseInstances=0,phraseSourcesMask=0,inputEvents=0;
 uint64_t clockWall=0,resourceWall=0;
 uint64_t orderErrors=0,userUs=0,systemUs=0,minorFaults=0,majorFaults=0,voluntarySwitches=0,involuntarySwitches=0;
 std::array<uint64_t,Stages> stageWall{},stageCpu{};
};
class Trace {
 std::array<Record,Capacity> records{};
 std::atomic<uint64_t> write{0},read{0},dropped{0};
 std::atomic<bool> done{false}; std::atomic<pthread_t> producer{}; bool cpuDetail=false; std::ofstream cpuFile; std::ofstream file; std::thread worker;
 uint64_t previousEntry=0,callbackCycle=0;
 void drain() {
  clockid_t producerClock{};bool haveClock=false;uint64_t nextCPU=0;
  while(!done.load(std::memory_order_acquire)||read.load()!=write.load()) {
   const auto now=clock(CLOCK_MONOTONIC);
   if(!haveClock&&producer.load(std::memory_order_acquire))haveClock=pthread_getcpuclockid(producer.load(),&producerClock)==0;
   if(haveClock&&now>=nextCPU){cpuFile<<now<<','<<clock(producerClock)<<'\n';nextCPU=now+10000000;}
   auto r=read.load(std::memory_order_relaxed),w=write.load(std::memory_order_acquire);
   if(r==w){std::this_thread::sleep_for(std::chrono::milliseconds(2));continue;}
   const auto v=records[r%Capacity];read.store(r+1,std::memory_order_release);
   file<<v.sample<<','<<v.frames<<','<<v.entry<<','<<v.gap<<','<<v.wall<<','<<v.cpu<<','<<v.xruns<<','<<v.commands<<','<<v.pending<<','<<v.active<<','<<v.rejected<<','<<v.overflow<<','<<v.jackFrame<<','<<v.noteEvents<<','<<v.noteOns<<','<<v.ccEvents<<','<<v.phraseInstances<<','<<v.phraseSourcesMask<<','<<v.instanceRejected<<','<<v.inputEvents<<','<<v.orderErrors<<','<<v.userUs<<','<<v.systemUs<<','<<v.minorFaults<<','<<v.majorFaults<<','<<v.voluntarySwitches<<','<<v.involuntarySwitches<<','<<v.clockWall<<','<<v.resourceWall;
   for(unsigned j=0;j<Stages;++j)file<<','<<v.stageWall[j]<<','<<v.stageCpu[j];
   file<<','<<v.callbackCycle<<'\n';
  }
  file<<"# dropped="<<dropped.load()<<"\n# detailed_cpu="<<cpuDetail<<"\n";file.flush();cpuFile.flush();
 }
public:
 explicit Trace(const std::string& path,bool detailedCPU=false):cpuDetail(detailedCPU),cpuFile(path+".cpu.csv"),file(path) {
  cpuFile<<"wall_ns,thread_cpu_ns\n";
  if(!file||!cpuFile)throw std::runtime_error("cannot open RT trace");
  file<<"sample,frames,entry_ns,entry_gap_ns,wall_ns,cpu_ns,xruns,commands,pending,active,rejected,overflow,jack_frame,note_events,note_ons,cc_events,phrase_instances,phrase_sources_mask,instance_rejected,input_events,order_errors,user_us,system_us,minor_faults,major_faults,voluntary_switches,involuntary_switches,clock_read_wall_ns,resource_read_wall_ns";
  for(const char* name:{"input_recovery","commands","controller_transport","movement_parameters","performance","eel_phrase_transformers","movement_cc_actions","midi_collect","sort","emit_observe_reply","jack_cycle_clock","jack_output_buffer","jack_output_clear","recovery","queued_output","jack_input_buffer","jack_input_count","jack_input_get","input_copy","input_dispatch","movement_render","controller_tick","jack_transport_query","chain_tick"})file<<','<<name<<"_wall_ns,"<<name<<"_cpu_ns";
  file<<",callback_cycle\n";worker=std::thread([this]{drain();});
 }
 ~Trace(){done.store(true,std::memory_order_release);worker.join();}
 void publish(Record v){auto w=write.load(std::memory_order_relaxed);if(w-read.load(std::memory_order_acquire)>=Capacity){++dropped;return;}records[w%Capacity]=v;write.store(w+1,std::memory_order_release);}
 class Scope {
  Trace* trace;uint64_t startWall=0,startCpu=0,lastWall=0,lastCpu=0;unsigned stage=0;
 rusage usageStart{};
  static uint64_t us(timeval t){return uint64_t(t.tv_sec)*1000000+t.tv_usec;}
 public:
  Record value;
  // Nested operation brackets overlap the original ten stage totals.
  // Fixed stack storage only; no clocks at all when tracing is disabled.
  class Probe {
    Scope& owner; unsigned index; uint64_t wall=0,cpu=0;
  public:
    Probe(Scope& s,unsigned i):owner(s),index(i){if(s.trace){wall=clock(CLOCK_MONOTONIC);cpu=s.trace->cpuDetail?clock(CLOCK_THREAD_CPUTIME_ID):0;}}
    ~Probe(){if(owner.trace){auto c=owner.trace->cpuDetail?clock(CLOCK_THREAD_CPUTIME_ID):0,w=clock(CLOCK_MONOTONIC);owner.value.stageWall[index]+=w-wall;owner.value.stageCpu[index]+=c-cpu;}}
  };

  Scope(Trace* t,uint64_t sample,unsigned frames):trace(t){if(!t)return;t->producer.store(pthread_self(),std::memory_order_release);value.callbackCycle=++t->callbackCycle;value.sample=sample;value.frames=frames;startWall=lastWall=clock(CLOCK_MONOTONIC);startCpu=lastCpu=t->cpuDetail?clock(CLOCK_THREAD_CPUTIME_ID):0;value.entry=startWall;value.gap=t->previousEntry?startWall-t->previousEntry:0;t->previousEntry=startWall;lastWall=clock(CLOCK_MONOTONIC);value.clockWall+=lastWall-startWall;if(t->cpuDetail)getrusage(RUSAGE_THREAD,&usageStart);auto after=clock(CLOCK_MONOTONIC);value.resourceWall+=after-lastWall;lastWall=after;}
  void mark(unsigned next){if(!trace)return;auto w=clock(CLOCK_MONOTONIC),c=trace->cpuDetail?clock(CLOCK_THREAD_CPUTIME_ID):0,after=clock(CLOCK_MONOTONIC);value.clockWall+=after-w;value.stageWall[stage]+=w-lastWall;value.stageCpu[stage]+=c-lastCpu;lastWall=after;lastCpu=c;stage=next;}
  ~Scope(){if(!trace)return;mark(stage);value.cpu=lastCpu-startCpu;rusage end{};if(trace->cpuDetail)getrusage(RUSAGE_THREAD,&end);auto after=clock(CLOCK_MONOTONIC);value.resourceWall+=after-lastWall;value.wall=after-startWall;value.userUs=us(end.ru_utime)-us(usageStart.ru_utime);value.systemUs=us(end.ru_stime)-us(usageStart.ru_stime);value.minorFaults=end.ru_minflt-usageStart.ru_minflt;value.majorFaults=end.ru_majflt-usageStart.ru_majflt;value.voluntarySwitches=end.ru_nvcsw-usageStart.ru_nvcsw;value.involuntarySwitches=end.ru_nivcsw-usageStart.ru_nivcsw;trace->publish(value);}
 };
};
}
