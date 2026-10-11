#include <sstream>
#include "../headless/parameter_registry.hpp"
static void parameter_contract_tests(const char *source) {
  Host h(source,false);
  for (double rate : {.2,.5,.8,1.}) {
    for (int repeat : {0,1,2,10,1000}) {
      for (int pitch=0;pitch<128;++pitch) {
        std::ostringstream expression;expression.precision(17);
        expression<<"phrase_velocity_decay_gain("<<rate<<","<<repeat<<","<<pitch<<",60,0)";
        check(h.eval(expression.str())==std::pow(rate,repeat),
              "zero pitch bias retains exact legacy pow response");
      }
    }
  }
  check(h.eval("phrase_velocity_decay_gain(.8,3,60,60,1)")==std::pow(.8,3),
        "pitch pivot retains legacy decay");
  check(h.eval("phrase_velocity_decay_gain(.8,3,84,60,1)")>
        h.eval("phrase_velocity_decay_gain(.8,3,60,60,1)"),"positive bias favors high notes");
  check(h.eval("phrase_velocity_decay_gain(.8,3,36,60,-1)")>
        h.eval("phrase_velocity_decay_gain(.8,3,60,60,-1)"),"negative bias favors low notes");
  for (int pitch=0;pitch<127;++pitch) {
    const auto gain=[&](int note) {
      return h.eval("phrase_velocity_decay_gain(.8,3,"+std::to_string(note)+",60,1)");
    };
    check(gain(pitch)<=gain(pitch+1),"pitch-bias response is continuously monotonic");
    check(gain(pitch)>=0 && gain(pitch)<=1,"pitch-bias gain cannot amplify or become negative");
  }
  for (int kind=0;kind<26;++kind) {
    for (double x : {0.,.001,.127,.25,.499999,.5,.500001,.75,.999,1.}) {
      const auto expression="param_scale("+std::to_string(kind)+","+std::to_string(x)+")";
      check(std::abs(h.eval(expression)-performance::physical(kind,x))<1e-7,
            "shared EEL/C++ descriptor scaling parity");
      const double v=performance::physical(kind,x);
      std::ostringstream value;value.precision(17);value<<v;
      const auto norm="param_normalize("+std::to_string(kind)+","+value.str()+")";
      check(std::abs(h.eval(norm)-performance::normalized(kind,v))<1e-7,
            "shared EEL/C++ normalization parity");
    }
  }
}
