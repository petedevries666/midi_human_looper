// Exact uint32 hashing and paired timing agreement across EEL2 and C++.
static void humanizer_cases(const char *path) {
  Host h(path);
  std::ifstream input("headless/humanizer-eel.jsfx-inc");
  check(bool(input), "open HUMANIZER EEL reference");
  std::string source((std::istreambuf_iterator<char>(input)),
                     std::istreambuf_iterator<char>());
  auto init = source.find("@init");
  check(init != std::string::npos, "HUMANIZER library init section");
  source = source.substr(init + 5);
  auto code = NSEEL_code_compile_ex(h.f->vm.get(), source.c_str(), 0,
                                    NSEEL_CODE_COMPILE_FLAG_COMMONFUNCS);
  check(code != nullptr, "compile HUMANIZER EEL reference functions");
  humanizer::Configuration c;
  c.enabled = true;
  c.timingMs = 40;
  c.velocityAmount = 40;
  humanizer::Identity id;
  id.scope = 1;
  id.instance = 16777215;
  id.phrase = 15;
  id.note = 2047;
  id.group = 2400;
  const uint32_t seeds[] = {0, 1, 991, 16777215, 2147483647, 4294967295u};
  for (auto seed : seeds)
    for (unsigned feel = 0; feel < 2; ++feel)
      for (unsigned variation = 0; variation < 2; ++variation)
        for (unsigned iteration : {0u, 97u, 4294967295u}) {
          c.seed = seed;
          c.feel = humanizer::Feel(feel);
          c.variation = humanizer::Variation(variation);
          id.iteration = iteration;
          auto context = std::to_string(seed) + ",1,16777215,15," +
                         std::to_string(iteration) + ",2047,2400," +
                         std::to_string(variation);
          h.eq("hu_hash(" + context + ",17,1)",
               humanizer::hash(c, id, 17, true), "EEL/C++ exact unsigned hash");
          h.eq("hu_unit(" + context + "," + std::to_string(feel) + ",17,1)",
               humanizer::signedUnit(c, id, 17, true),
               "EEL/C++ bounded distribution");
          h.eq("hu_shift(" + context + "," + std::to_string(feel) +
                   ",40,2400,.5,48000,1)",
               humanizer::pairedShift(c, id, 2400, .5, 48000),
               "EEL/C++ paired shift");
          h.eq("hu_shift(" + context + "," + std::to_string(feel) +
                   ",40,0,1,48000,1)",
               0, "EEL T=0 anchor");
          h.eq("hu_velocity(" + context + "," + std::to_string(feel) +
                   ",40,64,1)",
               humanizer::velocity(c, id, 64), "EEL/C++ velocity");
          h.eq("hu_velocity(" + context + "," + std::to_string(feel) +
                   ",40,0,1)",
               0, "EEL velocity-zero Note Off semantics");
        }
  NSEEL_code_free(code);
}
