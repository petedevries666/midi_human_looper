#include "../headless/controller_wire.hpp"
#include <cstdlib>
#include <iostream>
static unsigned checks = 0;
static void check(bool ok, const char *s) {
  ++checks;
  if (!ok) {
    std::cerr << s << '\n';
    std::exit(1);
  }
}
int main() {
  {
    controller::Host isolated;
    controller::Source a, b;
    a.id=101; a.kind=2; a.channel=1; a.number=21;
    b.id=102; b.kind=2; b.channel=2; b.number=22;
    check(isolated.source(a) && isolated.source(b), "isolation source setup");
    controller::Binding mapping;
    mapping.instrument=1; mapping.kind=1; mapping.base=.4;
    mapping.policy.id=11; mapping.policy.source=101; mapping.policy.target=201;
    check(isolated.bind(mapping), "source A mapping");
    mapping.instrument=2; mapping.policy.id=12; mapping.policy.source=102; mapping.policy.target=202;
    check(isolated.bind(mapping), "source B mapping");
    check(isolated.testSource(101,100,0) && isolated.testSource(102,90,0), "both physical owners active");
    check(isolated.stagePerformanceTarget(203,.2), "independent movement target");
    const auto movement=isolated.acquirePerformanceTarget(203,.3);
    check(movement && isolated.morph(204,.8,1)==0, "movement lease and missing morph refusal");
    check(isolated.stagePerformanceTarget(204,.2) && isolated.morph(204,.8,1), "independent snapshot morph");
    const auto otherToken=isolated.target(202)->token;
    const auto morphToken=isolated.target(204)->token;
    a.number=23;
    check(isolated.source(a), "reassign one source");
    check(!isolated.target(201)->owner && isolated.target(201)->effective==100/127., "only reassigned owner's lease ends without jumping value");
    check(isolated.target(202)->owner==12 && isolated.target(202)->token==otherToken, "unrelated physical owner survives");
    check(isolated.updatePerformanceTarget(203,movement,.5), "unrelated movement token survives reassignment");
    check(isolated.target(204)->morphing && isolated.target(204)->token==morphToken, "snapshot morph survives reassignment");
    // A mapping may share an external target; reset must not steal its lease.
    const auto shared=isolated.acquirePerformanceTarget(201,.6);
    check(shared && isolated.forget(101), "forget source with externally owned target");
    check(isolated.updatePerformanceTarget(201,shared,.7) && isolated.updatePerformanceTarget(203,movement,.6), "FORGET preserves external owners even on same target");
    check(isolated.learn(101), "arm source A learn");
    uint8_t cc[]={178,22,80};
    check(isolated.midi(cc,3,.1,[](int,int,int){return false;}) && isolated.learnConflict()==102, "conflict requires deliberate confirmation");
    check(isolated.confirm() && !isolated.target(202)->owner, "deliberate reassignment releases displaced source only");
    check(isolated.updatePerformanceTarget(201,shared,.8) && isolated.updatePerformanceTarget(203,movement,.7), "conflict confirmation preserves both external owners");
    check(isolated.target(204)->morphing && isolated.target(204)->token==morphToken, "conflict confirmation preserves snapshot morph");
    check(isolated.configuration().valid(), "source isolation retains valid persistent mappings");
    isolated.panic();
    check(!isolated.updatePerformanceTarget(203,movement,.9) && !isolated.target(204)->morphing, "explicit PANIC still invalidates all automation");
  }
  {
    controller::Host manual;controller::Source source;source.id=900;
    check(manual.source(source),"unassigned named source can be auditioned");
    controller::Binding binding;binding.policy.id=901;binding.policy.source=900;binding.policy.target=902;binding.instrument=1;binding.kind=1;binding.base=.25;
    binding.policy.takeover=controller::Takeover::Glide;binding.policy.glideSeconds=.2;
    check(manual.bind(binding),"manual test shares regular policy mapping");
    const auto saved=controller::configurationJson(manual.configuration());
    check(manual.learn(900),"manual source Learn armed");
    check(manual.testSource(900,127,0),"manual input accepted by source identity");
    double applied=0;auto exists=[](const controller::Binding&){return true;};auto apply=[&](const controller::Binding&,double v){applied=v;};
    manual.tick(.1,exists,apply);check(std::abs(applied-.625)<1e-8,"manual input obeys GLIDE midpoint");
    check(manual.learnTarget()==900 && manual.configuration().sources[0].kind==0,"manual test cannot capture or cancel Learn");
    check(controller::configurationJson(manual.configuration())==saved,"manual gesture cannot mutate persistent assignment or base");
    check(!manual.testSource(999,64,.1) && !manual.testSource(900,128,.1),"manual test rejects missing source and out of range");
    manual.tick(.2,exists,apply);check(applied==1,"manual glide reaches physical maximum");
    manual.cancel();source.kind=1;source.channel=0;source.number=99;check(manual.source(source),"note source assignment remains supported");
    binding.policy.takeover=controller::Takeover::Direct;check(manual.bind(binding),"note direct policy");
    check(manual.testSource(900,1,.3),"manual NOTE has binary physical range");manual.tick(.3,exists,apply);check(applied==1,"NOTE test positive value means full press");
    check(manual.testSource(900,0,.4),"manual NOTE release");manual.tick(.4,exists,apply);check(applied==0,"NOTE test zero means release");
  }
  {
    controller::Host commands;
    controller::Source source; source.id=1; source.kind=1; source.channel=3; source.number=60;
    check(commands.source(source), "command Learn source setup");
    controller::Binding mapping; mapping.policy.id=11; mapping.policy.source=1;
    mapping.policy.target=31; mapping.instrument=1; mapping.kind=1; mapping.base=.5;
    check(commands.bind(mapping), "command Learn mapping setup");
    auto legacy=[](int,int,int){return false;};
    uint8_t attack[]={147,60,100},release[]={131,60,0},cc[]={176,21,100};
    check(commands.midi(attack,3,0,legacy) && commands.target(31)->owner==11, "source owns mapped target");
    check(commands.learnCommand(1) && commands.learnsCommand(), "typed command Learn lease");
    check(commands.midi(cc,3,.01,legacy) && commands.learnTarget()==1, "command Learn ignores and consumes CC");
    check(commands.midi(attack,3,.02,legacy) && commands.learnConflict()==1, "equal source/command IDs still conflict");
    commands.cancel();
    check(commands.configuration().sources[0].kind==1, "cancel retains source assignment");
    check(commands.midi(release,3,.03,legacy), "cancelled capture release quarantined");
    check(commands.learnCommand(1) && commands.midi(attack,3,.04,legacy), "relearn command conflict");
    check(commands.confirm(), "deliberate command reassignment");
    controller::Source captured;
    check(commands.takeCommandCapture(captured) && captured.id==1 && captured.kind==1 && captured.channel==3 && captured.number==60, "exact command target captured");
    check(!commands.takeCommandCapture(captured) && !commands.learnTarget(), "capture delivered once and lease exits");
    check(commands.configuration().sources[0].kind==0 && commands.target(31)->owner==0, "reassignment releases only conflicting mapping ownership");
    check(commands.midi(release,3,.05,legacy), "successful capture release quarantined");
    check(commands.configuration().valid(), "command Learn creates no persistent temporary source");
  }
  controller::Host h;
  controller::Source a;
  a.id = 101;
  controller::Source b;
  b.id = 102;
  check(h.source(a) && h.source(b), "independent sources");
  uint8_t unrelatedRelease[] = {128, 60, 0};
  check(h.learn(101) && !h.midi(unrelatedRelease, 3, 0,
                                [](int, int, int) { return false; }),
        "Learn preserves pre-existing note releases");
  check(h.learn(101) && h.learn(102), "exclusive Learn switches target");
  uint8_t on[] = {144, 50, 100}, off[] = {128, 50, 0};
  auto free = [](int, int, int) { return false; };
  check(h.midi(on, 3, 0, free), "captured Note On consumed");
  check(!h.learnTarget() && h.configuration().sources[0].kind == 0 &&
            h.configuration().sources[1].kind == 1,
        "only exact Learn target assigned");
  check(h.forget(102) && h.midi(on, 3, .05, free),
        "repeated captured press cannot escape quarantine");
  check(h.midi(off, 3, .1, free), "captured release quarantined after FORGET");
  check(h.learn(101) && h.midi(on, 3, .2, [](int, int, int) { return true; }),
        "legacy conflict captured");
  check(h.learnConflict() == -1 && !h.confirm(),
        "legacy conflict cannot silently reassign");
  h.cancel();
  check(h.midi(off, 3, .3, free), "conflict release quarantined after CANCEL");
  a.kind = 2;
  a.channel = 1;
  a.number = 21;
  check(h.source(a), "CC identity");
  controller::Binding bind;
  bind.policy.id = 1;
  bind.policy.source = 101;
  bind.policy.target = 201;
  bind.instrument = 1;
  bind.kind = 1;
  bind.base = .4;
  bind.policy.takeover = controller::Takeover::Glide;
  bind.policy.glideSeconds = .2;
  bind.policy.back = controller::Return::Command;
  bind.policy.returnSeconds = .2;
  check(h.bind(bind), "bind actual target contract");
  uint8_t cc[] = {177, 21, 127};
  check(h.midi(cc, 3, .4, free), "configured CC consumed");
  auto exists = [](const controller::Binding &) { return true; };
  double value = 0;
  auto apply = [&](const controller::Binding &, double v) { value = v; };
  h.tick(.5, exists, apply);
  check(std::abs(value - .7) < 1e-8, "glide normalized midpoint");
  check(h.returnCommand(201), "explicit return routed");
  h.tick(.6, exists, apply);
  check(std::abs(value - .55) < 1e-8, "return ramp midpoint");
  h.tick(.71, exists, apply);
  check(std::abs(value - .4) < 1e-8 && !h.target(201)->owner,
        "return relinquishes ownership");
  auto persisted = controller::configurationJson(h.configuration());
  check(h.morph(201, .2, 1) != 0,
        "adapter owns morph through existing policy engine");
  h.tick(.91, exists, apply);
  check(std::abs(value - .36) < 1e-8,
        "adapter applies sample-clock morph through normal target callback");
  check(controller::configurationJson(h.configuration()) == persisted,
        "transient morph never serialized");
  h.recall(1, 0, bind.kind, .3);
  h.tick(.92, exists, apply);
  check(std::abs(value - .3) < 1e-8 && !h.target(201)->morphing,
        "manual adapter recall retires morph");
  h.morph(201, .9, 1);
  h.panic();
  h.tick(.93, exists, apply);
  check(std::abs(value - .3) < 1e-8,
        "adapter PANIC prevents further morph writes");
  for (unsigned i = 0; i < 500; ++i) {
    bind.policy.target = 300 + i;
    check(h.bind(bind), "retarget must retire orphan target");
  }
  auto old = h.configuration();
  auto invalid = old;
  invalid.bindings[0].instrument = 999;
  check(!h.replace(
            invalid,
            [](const controller::Binding &b) { return b.instrument == 1; }),
        "invalid recall is atomic");
  check(h.configuration().bindings[0].instrument == 1,
        "invalid recall preserves configuration");
  check(h.tick(
            1, [](const controller::Binding &) { return false; }, apply),
        "target deletion retires mapping");
  check(!h.configuration().bindings[0].policy.id,
        "deleted target cannot retain assignment");
  std::string json = controller::configurationJson(old);
  auto first = json.find('['), last = json.find(']');
  auto wire = json.substr(first + 1, last - first - 1);
  for (auto &ch : wire)
    if (ch == ',')
      ch = ' ';
  std::istringstream input(wire);
  controller::Configuration restored;
  check(controller::readConfiguration(input, restored),
        "versioned configuration roundtrip");
  check(restored.bindings[0].policy.target == 799,
        "stable target identity persisted");
  std::cout << "PASS: " << checks << " Controller host adapter checks\n";
}
