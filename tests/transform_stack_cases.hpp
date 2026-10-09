static void transform_stack_tests(Host &h) {
  h.run("panic_pending=0;state=STATE_IDLE;mem[INST_ENABLED_BASE]=1;"
        "mem[INST_ENABLED_BASE+1]=0;mem[INST_ENABLED_BASE+2]=0;"
        "mem[INST_OUT_BASE]=2;mem[INST_TRANSFORM_COUNT_BASE]=0;"
        "tf_defaults();cc_defaults();tf_runtime_reset();cc_runtime_reset();"
        "transform_add(0,4);transform_add(0,4);transform_add(0,1);transform_"
        "add(0,1);");
  cc_block(h);
  h.eq("mem[INST_TRANSFORM_COUNT_BASE]", 4,
       "stateless Transformer types can repeat");
  h.eq("transform_type(0,7)", 4,
       "generic instance registry stores velocity type");
  h.eq("transform_type(0,8)", 1,
       "generic instance registry stores transpose type");
  check(h.eval("tf_id(0,4)") != h.eval("tf_id(0,7)"),
        "stacked processors have unique IDs");
  h.run("mem[INST_VEL_BASE]=.8;mem[cc_cfg(0)+2]=.5;"
        "mem[INST_TRANSPOSE_BASE]=12;mem[cc_cfg(1)+2]=-5;");
  h.midi(144, 60, 100);
  cc_expect(h.events(), {{145, 67, 40}},
            "stacked transpose sums and velocity composes");
  h.run("transform_remove_slot(0,3);");
  cc_expect(cc_block(h), {}, "removal waits for held source without PANIC");
  h.eq("mem[INST_TRANSFORM_COUNT_BASE]", 4,
       "deferred structural edit keeps active chain");
  h.midi(128, 60, 0);
  cc_expect(h.events(), {{129, 67, 0}},
            "Note Off uses exact chain that emitted Note On");
  cc_block(h);
  h.eq("mem[INST_TRANSFORM_COUNT_BASE]", 3,
       "structural edit applies after source release");
  h.run("transform_add(0,1);");
  cc_block(h);
  h.run("mem[cc_cfg(1)+2]=-5;mem[exp_assign_addr(cc_ti(1,0))]=1;"
        "curve_factory(cc_ti(1,0),3);controller_set_value(0,.625);");
  h.midi(144, 60, 100);
  h.events();
  h.eq("mem[cc_cfg(1)+2]", 12,
       "transpose expression uses its own signed range");
  h.run("controller_set_value(0,.5);");
  cc_block(h);
  h.eq("mem[cc_cfg(1)+2]", 12,
       "expression pitch edit defers while a note is held");
  h.midi(128, 60, 0);
  cc_expect(h.events(), {{129, 84, 0}},
            "deferred expression preserves Note Off pairing");
  cc_block(h);
  h.eq("mem[cc_cfg(1)+2]", 0, "expression edit applies on release");
  // Actual one-shot playback traverses the same processors and retains recorded
  // data.
  h.run("slider9=1;mem[COUNT_BASE]=0;store_event(0,0,144,60,100,0);"
        "store_event(0,256,128,60,0,0);mem[LEN_BASE]=384;mem[MODE_BASE]=1;"
        "mem[DECAY_BASE]=1;trigger_request=0;");
  cc_expect(cc_block(h), {{145, 72, 40}},
            "phrase playback uses the same stacked pipeline");
  cc_block(h);
  auto off = cc_block(h);
  cc_expect(off, {{129, 72, 0}},
            "phrase-owned stacked Note Off remains paired");
  h.eq("mem[layer_base(0,0)+2]", 60,
       "stacking does not rewrite recorded phrase notes");
  cc_block(h);
  // Independent range instances have three independently mapped curve
  // parameters.
  h.run(
      "mem[INST_TRANSFORM_COUNT_BASE]=0;transform_add(0,2);transform_add(0,2);"
      "transform_add(0,1);");
  cc_block(h);
  h.run("mem[INST_RANGE_MODE_BASE]=3;mem[INST_RANGE_LOW_BASE]=60;mem[INST_"
        "RANGE_HIGH_BASE]=65;"
        "mem[cc_cfg(0)+2]=3;mem[cc_cfg(0)+1]=60;mem[cc_cfg(0)+3]=65;"
        "mem[INST_TRANSPOSE_BASE]=12;");
  h.midi(144, 60, 100);
  cc_expect(h.events(), {{145, 72, 100}},
            "visible serial order filters before transpose");
  h.midi(128, 60, 0);
  h.events();
  h.run("mem[INST_TRANSFORM_TYPE_BASE]=1;mem[INST_TRANSFORM_TYPE_BASE+1]=2;"
        "mem[INST_TRANSFORM_TYPE_BASE+2]=7;");
  h.midi(144, 60, 100);
  cc_expect(h.events(), {},
            "moving transpose ahead of range changes filtering predictably");
  h.midi(128, 60, 0);
  h.events();
  h.eq("mem[PARAM_ACTIVE_BASE]", 0,
       "rejected Note On/Off cannot leave input ownership stuck");
  h.run("mem[exp_assign_addr(cc_ti(0,2))]=2;curve_factory(cc_ti(0,2),4);"
        "controller_set_value(1,.25);cc_expression_tick();");
  h.eq("mem[cc_cfg(0)+3]", 95,
       "range high endpoint owns its third expression curve");
  h.eq("param_kind(cc_ti(0,2))", 10,
       "third range parameter identity is stable");
  h.run("external_patch_save_request(1);tf_defaults();cc_defaults();external_"
        "patch_apply();");
  h.eq("io_status", 3, "schema5 serial instances load successfully");
  h.eq("transform_type(0,7)", 2, "patch retains instance processor type");
  h.eq("mem[exp_assign_addr(cc_ti(0,2))]", 2,
       "patch retains independent third curve mapping");
  h.run("save_patch(1);mem[tf_record(0)]=4;save_patch(2);tf_bank_load(1);");
  h.eq("transform_type(0,7)", 2,
       "internal bank restores generic instance types");
  h.run("gmem[2]=4;gmem[3]=TF_LEGACY_PAYLOAD;external_patch_apply();");
  h.eq("io_status", 3, "v1.24 schema4 patches migrate without truncation");
  h.eq("transform_type(0,7)", 6,
       "schema4 extra instances remain CC generators");
  // Stateful modules deliberately remain single-instance per destination.
  h.run(
      "mem[INST_TRANSFORM_COUNT_BASE]=0;transform_add(0,5);transform_add(0,5);"
      "transform_add(0,3);transform_add(0,3);");
  cc_block(h);
  h.eq("mem[INST_TRANSFORM_COUNT_BASE]", 2,
       "ARP and polyphony duplicates are deliberately restricted");
}
