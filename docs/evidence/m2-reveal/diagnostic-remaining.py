import json,os,signal,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[3];dest=root/'docs/evidence/m2-reveal/remaining';dest.mkdir(exist_ok=True)
py=sys.executable
commands=[
 [py,'tests/test_instance_ownership_native.py'],
 ['scripts/m0-playback-test.sh'],['scripts/m0-playback-test.sh','--m1-groups'],['scripts/m0-playback-test.sh','--m2-gestures'],
 ['tests/run_host_tests.sh'],['scripts/portable-test.sh'],['scripts/conductor-persistence-test.sh'],[py,'tests/test_patch_io.py'],
]+[[py,'tests/'+p] for p in ['test_headless_browser.py','test_update_controls_browser.py','test_phrase_output_browser.py','test_headless_editor.py','test_conductor_execution_browser.py','test_conductor_editor_browser.py','test_movement_browser.py','conductor_diagnostics/pending_edit.py','conductor_diagnostics/editor_click.py','test_controller_browser.py','test_snapshot_browser.py','test_product_browser.py','test_web_parity_browser.py','test_tactile_browser.py','test_performance_density.py','test_phrase_midi_browser.py','test_native_hold_browser.py','test_phrase_mute_groups_browser.py','test_recovery_browser.py','test_hardware_feedback_browser.py','test_module_picker_browser.py','test_issue53_browser.py']]
results=[]
for i,cmd in enumerate(commands):
 name=f'{i:02d}-{Path(cmd[1] if cmd[0]==py else cmd[0]).stem}';print('+',name,*cmd,flush=True)
 with (dest/(name+'.log')).open('w') as log:
  child=subprocess.Popen(cmd,cwd=root,stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,COMPARE_ROOT=str(root)),start_new_session=True)
  try:code=child.wait(timeout=600)
  except subprocess.TimeoutExpired:
   os.killpg(child.pid,signal.SIGTERM);child.wait(timeout=5);code=124
 results.append(dict(command=cmd,exitCode=code,log=name+'.log'));(dest/'results.json').write_text(json.dumps(results,indent=2)+'\n');print('EXIT',code,flush=True)
print('RESULT',len(results),'commands;',sum(x['exitCode']!=0 for x in results),'failures',flush=True)
sys.exit(any(x['exitCode']!=0 for x in results))
