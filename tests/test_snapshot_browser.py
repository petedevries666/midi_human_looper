#!/usr/bin/env python3
"""Real browser controls against the native engine and HTTP worker."""
import sys
from pathlib import Path
from test_snapshots import SnapshotTests
from playwright.sync_api import sync_playwright
SnapshotTests.setUpClass()
try:
    case=SnapshotTests('test_worker_restart_preserves_engine_capture')
    case.setUp()
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':900,'height':900})
        page.goto(case.base)
        page.get_by_role('button',name='+ CAPTURE SNAPSHOT',exact=True).wait_for()
        case.wait_for(lambda:'CONNECTED' in page.locator('#connection').inner_text(),'connection')
        page.get_by_role('button',name='+ CAPTURE SNAPSHOT',exact=True).click()
        page.locator('[data-snapshot-name]').wait_for()
        assert page.locator('[data-snapshot-name]').input_value()=='SNAPSHOT 01'
        page.locator('[data-snapshot-name]').fill('VERSE')
        page.locator('#snapshots-section h2').click()
        case.wait_for(lambda:case.call()['snapshots'][0]['name']=='VERSE','inline rename')
        page.get_by_role('button',name='+ CAPTURE SNAPSHOT',exact=True).click()
        case.wait_for(lambda:page.locator('[data-snapshot-name]').count()==2,'second capture')
        case.command('instrument_route',instrumentId=1,field='level',value=64)
        case.wait_for(lambda:'MODIFIED' in page.locator('#snapshots').inner_text(),'dirty indicator')
        page.locator('#snapshots').get_by_role('button',name='UPDATE',exact=True).first.click()
        case.wait_for(lambda:not case.call()['snapshots'][0]['dirty'],'update')
        page.locator('#snapshots details summary').first.click()
        page.locator('#snapshots').get_by_role('button',name='EDIT',exact=True).first.click()
        page.get_by_label('Morph seconds',exact=True).fill('0.4')
        page.get_by_role('button',name='CANCEL',exact=True).click()
        assert case.call()['snapshots'][0]['seconds']==2
        page.locator('#snapshots details summary').first.click()
        page.locator('#snapshots').get_by_role('button',name='EDIT',exact=True).first.click()
        page.get_by_label('Morph seconds',exact=True).fill('0.4')
        page.get_by_label('CURVE',exact=True).select_option('0')
        page.get_by_role('button',name='DONE',exact=True).click()
        case.wait_for(lambda:case.call()['snapshots'][0]['seconds']==.4,'transactional settings')
        page.on('dialog',lambda d:d.accept())
        page.locator('#snapshots details summary').last.click()
        page.wait_for_timeout(600)
        assert page.locator('#snapshots details').last.get_attribute('open') is not None
        page.locator('#snapshots').get_by_role('button',name='DELETE',exact=True).last.click()
        case.wait_for(lambda:len(case.call()['snapshots'])==1,'confirmed deletion')
        browser.close()
    print('PASS actual Chromium snapshot capture, inline rename, dirty state, update, transactional settings DONE/CANCEL and confirmed deletion')
finally:
    SnapshotTests.tearDownClass()
