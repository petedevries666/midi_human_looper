from pathlib import Path
import sys
p=Path('/workspace/mbmf-conductor-a/scripts/combined-test.py');s=p.read_text()
line=next(l for l in s.splitlines() if "run(['scripts/headless-test.sh']" in l)
s=s.replace(line,"    print('RECORDED FAILURE: first combined invocation exited 1 in test_zynthian_chains; not rerunning its preceding gates',flush=True)\n    run([sys.executable,'tests/test_zynthian_dedicated_chain.py'],{'CHAIN_NATIVE_ROUTES':'1','CHAIN_JACK_PROBE':'/tmp/mbmf-rc-unblock-final/chain-probe'})\n    run([sys.executable,'tests/test_jack_graph.py'],{'JACK_TEST_BINARY':'/tmp/mbmf-rc-unblock-final/jack-smoke'})")
s=s.replace('try:\n    print(\'RECORDED FAILURE:',"failures=['first combined: test_zynthian_chains.py grid phase assertion after receiver XRUN']\nchecked_run=run\ndef run(command,extra=None):\n    try:\n        checked_run(command,extra);print('GATE EXIT 0: '+' '.join(command),flush=True)\n    except (RuntimeError,subprocess.TimeoutExpired) as error:\n        failures.append(str(error));print('RECORDED GATE FAILURE: '+str(error),flush=True)\ntry:\n    print('RECORDED FAILURE:",1)
s=s.replace("    print('PASS selected combined regression suite',flush=True)","    print('ALL REMAINING GATES EXECUTED; aggregate failures: '+repr(failures),flush=True)\n    sys.exit(bool(failures))")
assert 'checked_run=run' in s
sys.argv=[str(p),'--native','--jack','--browser','chromium','--web-access','--timeout','240']
exec(compile(s,str(p),'exec'),{'__file__':str(p),'__name__':'__main__'})
