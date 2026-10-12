#!/usr/bin/env python3
"""Real application screenshots; reuses the native integration-test lifecycle."""
import argparse
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
VIEWPORTS=[(320,240),(800,480),(1366,768),(1440,900),(1904,1032)]
sys.path.insert(0, str(ROOT / 'tests'))
from test_headless_mvp import HeadlessTests
from playwright.sync_api import sync_playwright

# Vertical scrolling is intentional. Hidden/clip ancestors, oversized controls and
# content outside the horizontal viewport are not. Modal background is inert.
AUDIT = r"""() => {
 const root=document.querySelector('dialog[open]') || document.body, errors=[];
 if(document.documentElement.scrollWidth>innerWidth+1) errors.push('document horizontal overflow');
 const positions=[...document.querySelectorAll('*')].map(e=>[e,e.scrollLeft,e.scrollTop]);
 const controls=[...root.querySelectorAll('button,input,select,textarea,a[href],summary')];
 for(const el of controls){
  const r=el.getBoundingClientRect();
  if(!el.checkVisibility({checkVisibilityCSS:true}) || !r.width || !r.height) continue;
  // Descendants of closed details have no client rects, despite their computed box.
  if(!el.getClientRects().length) continue;
  const name=el.getAttribute('aria-label') || el.textContent.trim() || el.id || el.tagName;
  if(r.width>innerWidth+1 || r.left< -1 || r.right>innerWidth+1) errors.push(name+': horizontal overflow');
  for(let p=el.parentElement;p;p=p.parentElement){
   const ps=getComputedStyle(p), pr=p.getBoundingClientRect();
   if(['hidden','clip'].includes(ps.overflowX) && (r.left<pr.left-1 || r.right>pr.right+1)) errors.push(name+': clipped horizontally');
   if(['hidden','clip'].includes(ps.overflowY) && (r.top<pr.top-1 || r.bottom>pr.bottom+1)) errors.push(name+': clipped vertically');
  }
  if(el.tagName==='BUTTON' && (el.scrollWidth>el.clientWidth+1 || el.scrollHeight>el.clientHeight+1)) errors.push(name+': clipped button label');
  if(!el.disabled && el.tabIndex<0) errors.push(name+': inaccessible to keyboard');
  if(!el.disabled){
   el.scrollIntoView({block:'nearest',inline:'nearest'});
   const visible=el.getBoundingClientRect();
   if(visible.top< -1 || visible.bottom>innerHeight+1) errors.push(name+': cannot scroll into viewport');
  }
 }
 for(const [e,x,y] of positions){e.scrollLeft=x;e.scrollTop=y;}
 return [...new Set(errors)];
}"""

def verify_png(path, width, height):
    data=path.read_bytes()
    if data[:8]!=b'\x89PNG\r\n\x1a\n' or len(data)<100:
        raise AssertionError(f'Invalid PNG: {path}')
    if struct.unpack('>II',data[16:24])!=(width,height):
        raise AssertionError(f'Unexpected PNG dimensions: {path}')


def run(output, performance=False):
    destination=output
    destination.mkdir(parents=True,exist_ok=True)
    staging=tempfile.TemporaryDirectory(prefix='mbmf-screenshots-')
    output=Path(staging.name)
    artifacts=[]
    started=False
    try:
        HeadlessTests.setUpClass()
        started=True
        api=HeadlessTests('test_real_engine_and_fifo')
        # Actual engine demo: recorded source notes, three independent instruments.
        api.command('panic')
        api.command('controller_source',sourceId=101,kind=2,channel=2,number=21)
        with sync_playwright() as pw:
            options=dict(headless=True,args=['--no-sandbox','--disable-gpu'])
            if os.environ.get('CHROMIUM_PATH'): options['executable_path']=os.environ['CHROMIUM_PATH']
            browser=pw.chromium.launch(**options)
            viewports=[(800,480),(1366,768)] if performance else VIEWPORTS
            for width,height in viewports:
                context=browser.new_context(viewport=dict(width=width,height=height),device_scale_factor=1,locale='en-US',timezone_id='UTC',reduced_motion='reduce')
                page=context.new_page(); errors=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(api.base)
                page.get_by_text('CONNECTED · Engine running',exact=True).wait_for()
                page.locator('[data-instrument-id="3"]').wait_for()
                page.locator('[data-source-id]').wait_for(state='attached')
                page.evaluate('document.fonts.ready')
                def capture(name,selector=None):
                    if 'editor' in name and 'name-editor' not in name:page.locator('#editor').wait_for(state='visible')
                    if performance and name not in ('phrases','instruments','transformer-editor'): return
                    if selector:
                        page.locator(selector).first.evaluate("e=>e.scrollIntoView({block:'start'})")
                    findings=page.evaluate(AUDIT)
                    path=output/f'{name}-{width}x{height}.png'
                    page.evaluate('() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')
                    # Prime Chromium's software raster before persisting the frame.
                    page.screenshot(animations='disabled')
                    page.wait_for_timeout(80)
                    page.screenshot(path=str(path),animations='disabled')
                    verify_png(path,width,height)
                    artifacts.append(dict(view=name,viewport=[width,height],file=path.name,checks=findings))
                    print(f'{path.name}: {"PASS" if not findings else findings}',flush=True)
                    modal=page.locator('dialog[open]')
                    if modal.count() and modal.evaluate('e=>e.scrollHeight>e.clientHeight+1'):
                        modal.evaluate('e=>e.scrollTop=e.scrollHeight')
                        bottom=output/f'{name}-bottom-{width}x{height}.png'
                        page.screenshot(path=str(bottom),animations='disabled')
                        verify_png(bottom,width,height)
                        artifacts.append(dict(view=name+'-bottom',viewport=[width,height],file=bottom.name,checks=page.evaluate(AUDIT)))
                        modal.evaluate('e=>e.scrollTop=0')
                if performance:
                    capture('phrases','#phrase-pagination')
                    api.command('module_structure',instrumentId=1,operation='add',engineType=1)
                    page.reload();page.get_by_text('CONNECTED · Engine running',exact=True).wait_for()
                    page.locator('.transformers .module').first.wait_for()
                    capture('instruments','#instruments')
                    page.locator('.transformers .module').first.get_by_role('button',name='EDIT',exact=True).click()
                    page.locator('#editor').wait_for(state='visible');capture('transformer-editor')
                    page.keyboard.press('Escape')
                    tf=api.call()['instruments'][0]['transformers'][0]
                    api.command('module_structure',instrumentId=1,moduleId=tf['id'],operation='delete')
                    if errors:raise AssertionError(errors)
                    context.close();continue
                capture('patch', 'header')
                capture('snapshots','#snapshots-section')
                capture('smart-switches','#switches')
                page.locator('[data-switch-id="1"] .switch-test').evaluate('e=>e.open=true')
                page.locator('[data-switch-id="1"]').get_by_role('button',name='TEST TAP',exact=True).click()
                page.locator('.switch-test-feedback').first.wait_for(state='visible');capture('smart-switch-test','#switches')
                api.command('panic')
                page.locator('[data-switch-id="1"]').get_by_role('button',name='OPTIONS',exact=True).click()
                capture('smart-switch-editor');page.keyboard.press('Escape')
                capture('phrases','#phrase-pagination')
                page.get_by_role('button',name='Edit Phrase 1 name',exact=True).click()
                capture('phrase-name-editor');page.keyboard.press('Escape')
                page.locator('[data-phrase-id="1"]').get_by_role('button',name='PHRASE OPTIONS',exact=True).click()
                capture('phrase-editor');page.keyboard.press('Escape')
                capture('instruments','#instruments')
                page.locator('[data-instrument-id="1"]').get_by_label('Transformer type for Instrument 1',exact=True).select_option('empty')
                page.locator('[data-instrument-id="1"]').get_by_role('button',name='ADD TRANSFORMER',exact=True).click()
                capture('empty-transformer');page.get_by_role('button',name='CANCEL',exact=True).click()
                page.get_by_role('button',name='Edit Instrument 1 name',exact=True).click()
                capture('instrument-name-editor');page.keyboard.press('Escape')
                page.locator('[data-instrument-id="1"]').get_by_role('button',name='EDIT',exact=True).first.click()
                capture('instrument-editor');page.keyboard.press('Escape')
                page.locator('#controller-section').evaluate('e=>e.open=true')
                capture('controllers','#controller-section')
                page.get_by_role('slider',name='TEST SOURCE 101',exact=True).fill('96')
                capture('controller-live-test','#controller-section')
                page.get_by_role('button',name='ADD MAPPING',exact=True).click()
                capture('controller-editor')
                page.locator('#editor details summary').first.click()
                capture('controller-advanced');page.keyboard.press('Escape')
                page.get_by_role('button',name='+ CAPTURE SNAPSHOT',exact=True).click()
                page.locator('[data-snapshot-id]').first.wait_for()
                page.get_by_role('button',name='+ CAPTURE SNAPSHOT',exact=True).click()
                page.wait_for_function('() => document.querySelectorAll("[data-snapshot-id]").length===2')
                capture('snapshot-manager','#snapshots-section')
                page.locator('#snapshots details summary').first.click()
                capture('snapshot-menu','#snapshots-section')
                page.locator('#snapshots').get_by_role('button',name='EDIT',exact=True).first.click()
                capture('snapshot-editor');page.keyboard.press('Escape')
                page.get_by_text('MANUAL A/B MORPH',exact=True).click()
                page.get_by_role('button',name='CONFIGURE A/B',exact=True).click()
                capture('snapshot-ab-editor')
                page.locator('#editor').get_by_role('button',name='DONE',exact=True).click()
                page.locator('#editor').wait_for(state='hidden')
                capture('snapshot-ab','#snapshot-ab')
                # Restore minimal snapshot state for the next viewport.
                for record in api.call()['snapshots']:
                    api.command('snapshot_delete',snapshotId=record['id'])
                instrument=page.locator('[data-instrument-id="1"]')
                api.command('module_structure',instrumentId=1,operation='add',engineType=1)
                page.reload()
                page.get_by_text('CONNECTED · Engine running',exact=True).wait_for()
                instrument.locator('.module').wait_for()
                capture('transformer-chain','#instruments')
                instrument.locator('.module').get_by_role('button',name='EDIT',exact=True).click()
                capture('transformer-editor');page.keyboard.press('Escape')
                tf=api.call()['instruments'][0]['transformers'][0]
                api.command('module_structure',instrumentId=1,moduleId=tf['id'],operation='delete')
                page.locator('details').filter(has=page.locator('#metrics')).evaluate('e=>e.open=true')
                capture('diagnostics','#metrics')
                if errors: raise AssertionError(errors)
                context.close()
            browser.close()
        # Additional native --chain evidence uses the production recovery test.
        # It captures actual ARMED / RECORDING states, not mocked demo flags.
        if not performance:
            subprocess.run([sys.executable,str(ROOT/'tests/test_recovery_browser.py')],cwd=ROOT,env={**os.environ,'SCREENSHOT_RECOVERY_DIR':str(output)},check=True)
            recovery=json.loads((output/'recovery-manifest.json').read_text())
            artifacts.extend(recovery['artifacts'])
            for artifact in recovery['artifacts']:artifact['runtimeBuildRevision']=recovery['runtimeBuildRevision'];artifact['data']=recovery['data']
        manifest=dict(browser=browser.version,sourceRevision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),sourceDirty=bool(subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=ROOT,text=True).strip()),runtimeBuildRevision=api.call()['buildRevision'],application='MIDI BAD MOTHERFUCKER',data='Native --demo views plus actual native --chain recovery: named CC source, real ARP MIDI, observed recording states and explicitly configured reference chains',artifacts=artifacts,
                      unsupported={'CONDUCTOR':'No implemented CONDUCTOR editor on the integration candidate; no mock screenshot supplied.'})
        (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        failures=[a for a in artifacts if a['checks']]
        if failures:
            failure_dir=ROOT/'.build/screenshot-failures'
            shutil.copytree(output,failure_dir,dirs_exist_ok=True)
            raise AssertionError(f'{len(failures)} layouts failed; see {failure_dir}/manifest.json')
        views=sorted({a['view'] for a in artifacts})
        lines=['# Real Chromium screenshots','',
               'Generated by `scripts/screenshots.sh` against the actual native engine and HTTP editor.',
               'Vertical scrolling is intentional; scrolling dialogs include bottom views.',
               'CONDUCTOR is not implemented on this base and has no fabricated screenshot.','',
               '| View | '+ ' | '.join(f'{w}×{h}' for w,h in viewports)+' |', '| --- | '+ ' | '.join('---' for _ in viewports)+' |']
        for view in views:
            cells=[view]
            for w,h in viewports:
                name=f'{view}-{w}x{h}.png'
                cells.append(f'[PNG]({name})' if (output/name).exists() else '—')
            lines.append('| '+' | '.join(cells)+' |')
        (output/'README.md').write_text('\n'.join(lines)+'\n')
        # Publish only a complete passing run; interrupted runs leave old artifacts intact.
        for artifact in [*output.glob('*.png'),output/'manifest.json',output/'README.md']:
            temporary=destination/(artifact.name+'.tmp')
            shutil.copyfile(artifact,temporary)
            temporary.replace(destination/artifact.name)
    finally:
        if started:
            HeadlessTests.tearDownClass()
        else:
            # The reused harness may fail halfway through startup.
            for name in ('web','engine'):
                process=getattr(HeadlessTests,name,None)
                if process and process.poll() is None:
                    process.terminate()
                    try: process.communicate(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill();process.communicate()
            temporary=getattr(HeadlessTests,'temp',None)
            if temporary: temporary.cleanup()
        staging.cleanup()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'docs/screenshots')
    parser.add_argument('--performance',action='store_true',help='Only the three primary performance views, desktop and tablet')
    args=parser.parse_args();run(args.output,args.performance)
