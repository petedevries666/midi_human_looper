#!/usr/bin/env python3
"""Real browser authoring/save/load -> native DSP -> private JACK receiver.

No mocked API or synthesized output. The source and sink are acyclic JACK
clients; receiver order is asserted as observed, never sorted after capture.
"""
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'headless'), str(ROOT / 'tests')]
from server import Control
from playwright.sync_api import sync_playwright
from test_conductor_editor_browser import save_draft


with tempfile.TemporaryDirectory(prefix='mbmf-m2-jack-') as tmp:
    env = dict(os.environ, JACK_DEFAULT_SERVER='mbmf-m2-gestures')
    logs = {n: open(Path(tmp) / (n + '.log'), 'w+') for n in ('jack', 'engine', 'web')}
    processes = []
    browser = probe = None
    try:
        jack = subprocess.Popen([env['JACKD'], '--name', env['JACK_DEFAULT_SERVER'],
                                 '--no-realtime', '-d', 'dummy', '-r', '48000', '-p', '8192'],
                                env=env, stdout=logs['jack'], stderr=subprocess.STDOUT)
        processes.append(jack)
        time.sleep(1)
        assert jack.poll() is None
        sock = str(Path(tmp) / 'engine.sock')
        engine = subprocess.Popen([env['HEADLESS_BINARY'], str(ROOT / 'midi_human_looper.jsfx'),
                                   sock, '--chain', '--chain-timing', '2', '--jack', '--client', 'mbmf_d'],
                                  env=env, stdout=logs['engine'], stderr=subprocess.STDOUT)
        processes.append(engine)

        def wait(fn, label):
            end = time.monotonic() + 10
            while time.monotonic() < end:
                assert all(p.poll() is None for p in processes), label
                if fn():
                    return
                time.sleep(.03)
            raise AssertionError(label)

        wait(lambda: Path(sock).exists(), 'native engine socket')
        control = Control(sock)

        def command(**args):
            s = control.request()
            r = control.request(revision=s['revision'], session=s['engineSessionId'], **args)
            assert r.get('status') == 'ok', r
            return r

        command(op=2)
        for instrument in (2, 3):
            command(op=32, target=instrument, arg=21, macro=[0, 0])
        for phrase, pitch in enumerate((48, 72)):
            command(op=32, target=phrase + 1, arg=20, macro=[0, 1])
            command(op=32, target=phrase + 1, arg=15, macro=[0, 1])
            command(op=35, target=phrase, arg=1,
                    phrase=dict(lengthSeconds=30, events=[[0, 144, pitch, 100], [29, 128, pitch, 0]]))
        settings = control.request()['switches'][0]['settings']
        settings[:4] = [1, 1, 0, 110]
        settings[8] = 250
        command(op=41, target=1, settings=settings + [0] * 64 + [0] * 16)
        with socket.socket() as port_socket:
            port_socket.bind(('127.0.0.1', 0))
            port = port_socket.getsockname()[1]
        base = f'http://127.0.0.1:{port}'
        web = subprocess.Popen([sys.executable, str(ROOT / 'headless/server.py'), '--socket', sock,
                                '--port', str(port), '--patch-dir', str(Path(tmp) / 'patches')],
                               env=env, stdout=logs['web'], stderr=subprocess.STDOUT)
        processes.append(web)

        def ready():
            try:
                return urllib.request.urlopen(base + '/api/v1/state', timeout=1).status == 200
            except OSError:
                return False

        wait(ready, 'actual editor HTTP')
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, executable_path=env.get('CHROMIUM_PATH', '/usr/bin/chromium'),
                                         args=['--no-sandbox', '--disable-gpu'])
            page = browser.new_page(viewport={'width': 1440, 'height': 900})
            page.goto(base)
            page.get_by_text('CONNECTED · Engine running', exact=True).wait_for()
            page.locator('[data-switch-id="1"]').get_by_role('button', name='CONDUCTOR', exact=True).click()
            first = page.locator('.conductor-step').first
            for layer in (1, 2):
                first.get_by_role('button', name=f'Add PHRASE STEP 1 LAYER {layer}', exact=True).click()
                first.get_by_role('button', name=re.compile(f'^PHRASE {layer:02d} ·')).click()
            first.get_by_role('button', name='EDIT BLOCK', exact=True).nth(1).click()
            page.get_by_label('TRIGGER inheritance', exact=True).select_option('OVERRIDE')
            page.get_by_label('TRIGGER override', exact=True).select_option('HOLD')
            save_draft(page)
            page.get_by_role('button', name='SAVE PATCH', exact=True).click()
            page.get_by_text('PATCH SAVED', exact=True).wait_for()
            page.get_by_role('button', name='LOAD PATCH', exact=True).click()
            page.wait_for_function('()=>!pending')
            page.reload()
            page.get_by_text('CONNECTED · Engine running', exact=True).wait_for()
            model = json.load(urllib.request.urlopen(base + '/api/v1/conductor'))['model']
            assert model['switches'][0]['steps'][0]['layers'][1]['block']['overrides']['trigger']['value'] == 'HOLD'
            assert not control.request()['instances'], 'SAVE/LOAD/reconnect cannot start pending HOLD'
            probe = subprocess.Popen([env['CONDUCTOR_JACK_PROBE']], env=env, stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, text=True)
            assert probe.stdout.readline().strip() == 'READY'

            def edge(status):
                probe.stdin.write(f'{status} 110 {127 if status == 144 else 0}\n')
                probe.stdin.flush()

            # Both edges queued in the SAME source callback: true short tap,
            # independent of Python/UI scheduling and wall-clock sleeps.
            edge(144)
            edge(128)
            wait(lambda: len(control.request()['instances']) == 1, 'short tap PRESS bass')
            time.sleep(.4)
            assert len(control.request()['instances']) == 1, 'early release cannot admit pad'
            command(op=2)
            wait(lambda: not control.request()['instances'], 'PANIC short tap cleanup')
            edge(144)
            wait(lambda: len(control.request()['instances']) == 2, 'sample-timed HOLD pad admission')
            owners = [v['id'] for v in control.request()['instances']]
            edge(128)
            time.sleep(.4)
            assert [v['id'] for v in control.request()['instances']] == owners, 'ONE_SHOT survives RELEASE'
            command(op=2)
            wait(lambda: not control.request()['instances'], 'PANIC held cleanup')
            # Existing browser TEST exercises exactly the same dispatcher.
            panel = page.locator('[data-switch-id="1"]')
            panel.locator('.switch-test').evaluate('e=>e.open=true')
            panel.get_by_role('button', name='TEST TAP', exact=True).click()
            wait(lambda: len(control.request()['instances']) == 1, 'browser TEST TAP')
            panel.get_by_role('button', name='TEST HOLD', exact=True).click()
            wait(lambda: len(control.request()['instances']) == 2, 'browser TEST HOLD')
            panel.get_by_role('button', name='TEST HOLD', exact=True).click()
            time.sleep(.3)
            assert len(control.request()['instances']) == 2, 'TEST HOLD cannot duplicate admission'
            command(op=2)
            time.sleep(.4)
            assert control.request()['outputOverflow'] == 0
            assert not control.request()['instances']
            probe.stdin.close()
            trace = [list(map(int, line.split())) for line in probe.stdout.read().splitlines()]
            assert probe.wait(timeout=5) == 0
            probe = None
            notes = [e for e in trace if e[2] & 240 == 144 and e[4] > 0]
            assert [e[3] for e in notes] == [48, 48, 72, 48, 72], trace
            assert notes[2][0] + notes[2][1] - notes[1][0] - notes[1][1] == 12000, trace
            assert all(a[0] + a[1] <= b[0] + b[1] for a, b in zip(trace, trace[1:])), trace
            assert not any(e[3] == 110 for e in trace), 'footswitch input leaked into musical output'
            assert any(e[2] & 240 == 176 and e[3] in (120, 123) for e in trace), 'missing PANIC cleanup'
            report = dict(events=trace, attacks=[e[3] for e in notes], holdDelaySamples=12000,
                          backend='actual private acyclic JACK + real Chromium/native editor',
                          sampleRate=48000, blockSize=8192, physicalHardware=False)
            evidence = os.environ.get('M2_EVIDENCE_DIR')
            if evidence:
                path = Path(evidence)
                path.mkdir(parents=True, exist_ok=True)
                (path / 'browser-jack-trace.json').write_text(json.dumps(report, indent=2) + '\n')
            print('PASS M2 browser SAVE/LOAD/reconnect -> JACK', json.dumps(report))
            browser.close()
            browser = None
    finally:
        if probe is not None:
            probe.terminate()
            probe.communicate(timeout=5)
        for process in reversed(processes):
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
                raise
        for name, log in logs.items():
            log.flush()
            log.seek(0)
            if os.environ.get('M2_EVIDENCE_DIR'):
                path = Path(os.environ['M2_EVIDENCE_DIR'])
                path.mkdir(parents=True, exist_ok=True)
                (path / (name + '.log')).write_text(log.read())
            log.close()
