#include <sstream>
#include "../headless/parameter_registry.hpp"
static void parameter_contract_tests(const char *source) {
  Host h(source,false);
  for (int kind=0;kind<25;++kind) {
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
