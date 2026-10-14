"""Real native editor + actual update worker; kernel/root and release API fixtures."""
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
from unittest.mock import patch
from playwright.sync_api import sync_playwright,expect
from test_headless_mvp import HeadlessTests
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'headless'))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'zynthian/update'))
import backend
from server import make_server
from test_update_controls import PASSWORD,release_fetch,SHA
HeadlessTests.setUpClass();api=HeadlessTests('runTest')
try:
    with tempfile.TemporaryDirectory(prefix='update-browser-') as temporary:
        directory=Path(temporary);config=directory/'install.json'
        config.write_text(json.dumps(dict(version=1,runtime_revision=api.call()['buildRevision'],repository=str(Path(__file__).resolve().parents[1]),binary=os.environ['HEADLESS_BINARY'])))
        (directory/'update-admin.json').write_text(json.dumps(backend.password_record(PASSWORD)))
        worker_backend=backend.Backend(config,fetch=release_fetch);stop=threading.Event();sock=directory/'update.sock'
        with patch.object(backend,'peer_uid',return_value=0):
            worker=threading.Thread(target=backend.serve,args=(worker_backend,sock,stop),daemon=True);worker.start()
            while not sock.exists():time.sleep(.01)
            original=backend.client
            with patch.object(backend,'client',side_effect=lambda action,**fields:original(action,sock,**fields)):
                web=make_server('127.0.0.1',0,api.sock,patch_dir=str(directory))
                webthread=threading.Thread(target=web.serve_forever,daemon=True);webthread.start()
                try:
                    with sync_playwright() as pw:
                        browser=pw.chromium.launch(executable_path=os.environ['CHROMIUM_PATH'],args=['--no-sandbox','--disable-gpu']);page=browser.new_page(viewport=dict(width=800,height=480))
                        page.goto('http://127.0.0.1:'+str(web.server_port));page.get_by_text('CONNECTED · Engine running',exact=True).wait_for()
                        page.locator('#runtime-update > summary').click();expect(page.locator('#update-version')).to_contain_text(api.call()['buildRevision'])
                        page.once('dialog',lambda dialog:dialog.accept('wrong'))
                        page.locator('#update-check').click();expect(page.locator('#update-progress')).to_contain_text('authorization required')
                        page.once('dialog',lambda dialog:dialog.accept(PASSWORD))
                        page.locator('#update-check').click();expect(page.locator('#update-changes')).to_contain_text(SHA,timeout=6000)
                        expect(page.locator('#update-install')).to_be_enabled()
                        calls=[]
                        with patch.object(worker_backend.u,'build',side_effect=lambda *a:calls.append(a)):
                            # Cancel destructive confirmation: no password request/job/build.
                            page.once('dialog',lambda dialog:dialog.dismiss());page.locator('#update-install').click()
                            assert not calls and not worker_backend.busy
                        page.screenshot(path=str(Path(__file__).resolve().parents[1]/'docs/screenshots/update-controls-release-fixture-800x480.png'))
                        page.reload();page.locator('#runtime-update > summary').click();expect(page.locator('#update-changes')).to_contain_text('Reviewed changes')
                        browser.close()
                    assert api.call()['buildRevision'] and api.call()['schemaVersion']==7
                    print('PASS actual native editor, separate password refusal, reviewed CHECK, confirmation cancellation, reload, no engine activation; root/release authority explicitly fixtured')
                finally:web.shutdown();web.server_close();webthread.join(2)
            stop.set();worker.join(2)
finally:HeadlessTests.tearDownClass()
