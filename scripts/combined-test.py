#!/usr/bin/env python3
"""Combined regression runner; explicit optional JACK/browser tests, bounded waits."""
import argparse, os, signal, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--native',action='store_true')
p.add_argument('--web-access',action='store_true',help='real Webconf gateway/Tornado/Chromium fixtures; requires tests/requirements-web-access.txt')
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
    run(['scripts/headless-test.sh'],{'RUN_JACK_TESTS':'1' if a.jack else '0','RUN_NATIVE_TESTS':'0','TEST_PYTHON':sys.executable,'RUN_CHAIN_BROWSER':'1' if a.browser=='chromium' else '0'})
    if a.jack:run(['scripts/movement-jack-test.sh'],{'MOVEMENT_BROWSER_AUTHOR':'1' if a.browser=='chromium' else '0'})
    run([sys.executable,'tests/test_zynthian_update.py'])
    run([sys.executable,'tests/test_update_controls.py'])
    run([sys.executable,'tests/test_update_native.py'])
    run([sys.executable,'tests/test_zynthian_channel_source.py'])
    run([sys.executable,'tests/test_patch_extension_preservation.py'])
    run([sys.executable,'tests/test_native_free_capture.py'])
    run([sys.executable,'tests/test_observation.py'])
    run([sys.executable,'tests/test_reliability_report.py'])
    run([sys.executable,'tests/test_controller_integration.py'])
    run([sys.executable,'tests/test_snapshots.py'])
    run([sys.executable,'tests/test_product_integration.py'])
    run([sys.executable,'tests/test_web_names.py'])
    run([sys.executable,'tests/test_phrase_midi.py'])
    run([sys.executable,'tests/test_portable_project.py'])
    run([sys.executable,'tests/test_conductor_legacy_contract.py'])
    run([sys.executable,'tests/test_conductor_persistence.py'])
    run([sys.executable,'tests/test_movement_persistence.py'])
    run(['scripts/movement-test.sh'])
    run(['scripts/movement-test.sh'],{'SANITIZE':'1'})
    run(['scripts/realtime-trace-test.sh'])
    run([sys.executable,'tests/test_conductor_execution_native.py'])
    run([sys.executable,'tests/test_phrase_mute_groups.py'])
    run([sys.executable,'tests/test_portable_engine.py'])
    run([sys.executable,'tests/test_project_sync.py'])
    run([sys.executable,'tests/test_project_authority.py'])
    run([sys.executable,'tests/test_reaper_bridge.py'])
    run([sys.executable,'tests/test_phrase_midi_integration.py'])
    run(['scripts/controller-test.sh'])
    run(['scripts/controller-test.sh'],{'SANITIZE':'1'})
    if a.native:
        # PR A baseline: explicit known failures, not functional Conductor support.
        run(['scripts/conductor-baseline.sh'])
        run([sys.executable,'tests/test_conductor_native_baseline.py'])
        run([sys.executable,'tests/test_instance_ownership_native.py'])
        run(['scripts/m0-playback-test.sh'])
        run(['scripts/m0-playback-test.sh','--m1-groups'])
        run(['tests/run_host_tests.sh'])
        run(['scripts/portable-test.sh'],{'TEST_PYTHON':sys.executable})
        run(['scripts/conductor-persistence-test.sh'],{'TEST_PYTHON':sys.executable})
        run([sys.executable,'tests/test_patch_io.py'])
    if a.browser=='stock-firefox':run([sys.executable,'tests/test_headless_firefox.py'])
    elif a.browser!='none':
        run([sys.executable,'tests/test_headless_browser.py'],{'MIDI_BROWSER':a.browser})
        # The generic editor currently uses Chromium's explicit executable route.
        if a.browser=='chromium':
            run([sys.executable,'tests/test_update_controls_browser.py'])
            if a.jack:
                # #68 verifies actual channel-voice JACK output as well as UI;
                # never make a --browser none run silently require Chromium.
                run(['scripts/phrase-output-test.sh'],{'TEST_PYTHON':sys.executable})
            else:
                run([sys.executable,'tests/test_phrase_output_browser.py'])
            run([sys.executable,'tests/test_headless_editor.py'])
            run([sys.executable,'tests/test_conductor_execution_browser.py'])
            run([sys.executable,'tests/test_conductor_editor_browser.py'])
            run([sys.executable,'tests/test_movement_browser.py'])
            run([sys.executable,'tests/conductor_diagnostics/pending_edit.py'],{'COMPARE_ROOT':os.getcwd()})
            run([sys.executable,'tests/conductor_diagnostics/editor_click.py'],{'COMPARE_ROOT':os.getcwd()})
            run([sys.executable,'tests/test_controller_browser.py'])
            run([sys.executable,'tests/test_snapshot_browser.py'])
            run([sys.executable,'tests/test_product_browser.py'])
            run([sys.executable,'tests/test_web_parity_browser.py'])
            run([sys.executable,'tests/test_tactile_browser.py'])
            run([sys.executable,'tests/test_performance_density.py'])
            run([sys.executable,'tests/test_phrase_midi_browser.py'])
            run([sys.executable,'tests/test_native_hold_browser.py'])
            run([sys.executable,'tests/test_phrase_mute_groups_browser.py'])
            run([sys.executable,'tests/test_recovery_browser.py'])
            run([sys.executable,'tests/test_hardware_feedback_browser.py'])
            run([sys.executable,'tests/test_module_picker_browser.py'])
            run([sys.executable,'tests/test_issue53_browser.py'])
    if a.web_access:run(['scripts/az-hub-test.sh'],{'TEST_PYTHON':sys.executable})
    print('PASS selected combined regression suite',flush=True)
except (RuntimeError,subprocess.TimeoutExpired,KeyboardInterrupt) as error:
    print(f'FAILED: {error}',file=sys.stderr);sys.exit(1)
