#pragma once
// Native reusable musical transforms. This file is an isolated foundation:
// integration into the current instrument pipeline must preserve voice ownership.
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <limits>
namespace native_expression {
inline double clamp01(double v) {return std::isfinite(v)?std::max(0.0,std::min(1.0,v)):0.0;}
struct Point {double x=0.0,y=0.0;};
struct VelocityCurve {
  std::array<Point,16> points{{{0,0},{1,1}}};
  unsigned count=2;
  double amount=1.0;
  // Input/output both normalized. Duplicate x positions are invalid.
  bool valid()const {
    if(count<2||count>points.size()||points[0].x!=0.0||points[count-1].x!=1.0)return false;
    for(unsigned i=0;i<count;i++){
      if(!std::isfinite(points[i].x)||!std::isfinite(points[i].y)||points[i].y<0||points[i].y>1)return false;
      if(i && points[i].x<=points[i-1].x)return false;
    }
    return std::isfinite(amount)&&amount>=0&&amount<=1;
  }
  uint8_t process(uint8_t velocity)const {
    if(!velocity||!valid())return velocity;
    const double x=double(velocity-1)/126.0;
    unsigned hi=1;while(hi+1<count&&points[hi].x<x)++hi;
    const auto a=points[hi-1],b=points[hi];
    const double t=clamp01((x-a.x)/(b.x-a.x));
    const double mapped=std::max(1.0,std::min(127.0,1.0+126.0*(a.y+(b.y-a.y)*t)));
    return static_cast<uint8_t>(std::max(1.0,std::min(127.0,std::round(velocity+(mapped-velocity)*amount))));
  }
};
inline uint32_t scramble(uint32_t x) {
  x^=x>>16;x*=0x7feb352du;x^=x>>15;x*=0x846ca68bu;x^=x>>16;return x;
}
inline double unit(uint32_t seed,uint64_t voice,uint64_t iteration,uint32_t stream) {
  auto h=scramble(seed^scramble(uint32_t(voice))^scramble(uint32_t(voice>>32))^scramble(uint32_t(iteration))^scramble(uint32_t(iteration>>32))^scramble(stream));
  return (double(h)+0.5)/4294967296.0;
}
enum class Distribution : uint8_t {Uniform,BoundedGaussian};
struct Humanizer {
  double timingRangeMs=0;
  double timingBiasMs=0;
  double velocityVariation=0;
  uint32_t seed=1;
  Distribution distribution=Distribution::BoundedGaussian;
  bool evolving=false;
  bool valid()const{return std::isfinite(timingRangeMs)&&timingRangeMs>=0&&timingRangeMs<=2000 &&
    std::isfinite(timingBiasMs)&&std::abs(timingBiasMs)<=2000 &&
    std::isfinite(velocityVariation)&&velocityVariation>=0&&velocityVariation<=1;}
  double draw(uint64_t identity,uint64_t iteration,uint32_t stream)const {
    if(!evolving)iteration=0;
    if(distribution==Distribution::Uniform)return 2*unit(seed,identity,iteration,stream)-1;
    double sum=0;for(uint32_t i=0;i<6;i++)sum+=unit(seed,identity,iteration,stream+i);
    return (sum-3.0)/3.0;
  }
  int64_t sampleShift(uint64_t groupOrNote,uint64_t iteration,uint32_t sampleRate)const {
    if(!valid()||sampleRate==0)return 0;
    const double ms=timingBiasMs+timingRangeMs*draw(groupOrNote,iteration,0x21ab31);
    return static_cast<int64_t>(std::llround(ms*double(sampleRate)/1000.0));
  }
  uint8_t noteVelocity(uint8_t velocity,uint64_t noteId,uint64_t iteration)const {
    if(!velocity||!valid())return velocity;
    const double scale=1.0+velocityVariation*draw(noteId,iteration,0x7d3412);
    return static_cast<uint8_t>(std::max(1.0,std::min(127.0,std::round(velocity*scale))));
  }
};
// The caller must cache the shift by an original *voice* identity and apply it
// to both Note On and Note Off. Negative shifts may only be used when a phrase
// has genuine lookahead; MIDI input cannot be scheduled before its arrival.
inline uint64_t delayedSample(uint64_t original,int64_t shift,uint64_t earliest=0){
  if(shift>=0){auto s=static_cast<uint64_t>(shift);return original>UINT64_MAX-s?UINT64_MAX:std::max(earliest,original+s);}
  auto s=static_cast<uint64_t>(-(shift+1))+1;
  return std::max(earliest,original<s?uint64_t(0):original-s);
}
} // namespace native_expression
