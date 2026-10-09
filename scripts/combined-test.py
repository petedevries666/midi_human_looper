#!/usr/bin/env python3
"""Combined regression runner; explicit optional JACK/browser tests, bounded waits."""
import argparse, os, signal, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--native',action='store_true')
p.add_argument('--jack',action='store_true',help='desktop dummy server only; never on a running Zynthian')
p.add_argument('--browser',choices=('none','chromium','firefox','stock-firefox'),default='none')
p.add_argument('--timeout',type=int,default=180)
a=p.parse_args()
if a.timeout<=0:p.error('timeout must be positive')
env=dict(os.environ)
def run(command,extra=None):
    print('+ '+' '.join(command),flush=True)
    child=subprocess.Popen(command,cwd=ROOT,env={**env,**(extra or {})},start_new_session=True)
    try:
        code=child.wait(timeout=a.timeout)
        if code:raise RuntimeError(f'exit {code}: {command[0]}')
    except BaseException:
        # Browser drivers and native hosts are also retired on timeout/interruption.
        try:os.killpg(child.pid,signal.SIGTERM)
        except ProcessLookupError:pass
        try:child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid,signal.SIGKILL);child.wait()
        raise
try:
    run(['scripts/headless-test.sh'],{'RUN_JACK_TESTS':'1' if a.jack else '0','RUN_NATIVE_TESTS':'0'})
    run([sys.executable,'tests/test_controller_integration.py'])
    run(['scripts/controller-test.sh'])
    run(['scripts/controller-test.sh'],{'SANITIZE':'1'})
    run(['scripts/humanizer-test.sh'])
    run(['scripts/humanizer-test.sh'],{'SANITIZE':'1'})
    if a.native:
        run(['tests/run_host_tests.sh'])
        run([sys.executable,'tests/test_patch_io.py'])
    if a.browser=='stock-firefox':run([sys.executable,'tests/test_headless_firefox.py'])
    elif a.browser!='none':
        run([sys.executable,'tests/test_headless_browser.py'],{'MIDI_BROWSER':a.browser})
        # The generic editor currently uses Chromium's explicit executable route.
        if a.browser=='chromium':
            run([sys.executable,'tests/test_headless_editor.py'])
            run([sys.executable,'tests/test_controller_browser.py'])
    print('PASS selected combined regression suite',flush=True)
except (RuntimeError,subprocess.TimeoutExpired,KeyboardInterrupt) as error:
    print(f'FAILED: {error}',file=sys.stderr);sys.exit(1)
