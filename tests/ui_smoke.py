"""Optional Playwright smoke test. Starts a local server; NEVER clicks Apply."""
import json
from pathlib import Path
import subprocess
import sys
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
server = subprocess.Popen(([str(ROOT / 'dist/Dialpad.app/Contents/MacOS/Dialpad'), '--no-browser'] if '--packaged' in sys.argv else [sys.executable, str(ROOT / 'app.py'), '--no-browser']), stdout=subprocess.PIPE, text=True)
try:
    url = server.stdout.readline().strip()
    assert url.startswith('http://127.0.0.1:')
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless=True)
        page = browser.new_page(viewport={'width':1280,'height':1500})
        errors=[]
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.route('**/api/apply', lambda route: (_ for _ in ()).throw(AssertionError('Smoke test must never program hardware')))
        page.goto(url)
        expect(page.locator('#connection')).not_to_have_text('Checking keypad…')
        assert page.locator('.key').count()==6
        assert page.locator('#connection').inner_text()=='Keypad connected'
        page.locator('#flow-mode').select_option('ptt')
        assert page.locator('#key').input_value()=='NONE'
        assert page.locator('[data-control="key1"] .key-shortcut').inner_text()=='Ctrl + ⌥ / Alt'
        page.locator('#preview').click()
        page.locator('#review').wait_for(state='visible')
        assert 'Key 1  →  Ctrl + ⌥ / Alt' in page.locator('#review-content').text_content()
        assert 'NONE' not in page.locator('#review-content').text_content()
        page.get_by_role('button',name='Cancel',exact=True).click()
        page.locator('#flow-mode').select_option('handsfree')
        page.locator('[data-control="key2"]').click()
        assert page.locator('#key').input_value()=='ENTER'
        page.locator('#preview').click()
        page.locator('#review').wait_for(state='visible')
        assert 'Key 2  →  ENTER' in page.locator('#review-content').text_content()
        page.get_by_role('button',name='Cancel',exact=True).click()
        page.locator('[data-control="dial_ccw"]').click()
        assert page.locator('#action').input_value()=='wheel_up'
        page.locator('#preset').select_option('desktop')
        page.locator('#load-preset').click()
        page.locator('[data-control="key1"]').click()
        assert page.locator('#key').input_value()=='SPACE'
        with page.expect_download() as download:
            page.locator('#export').click()
        exported = json.loads(Path(download.value.path()).read_text())
        assert exported['bindings']['key1']['modifiers']==['ctrl','alt']
        exported['name']='Imported test'
        page.locator('#file').set_input_files({'name':'profile.json','mimeType':'application/json','buffer':json.dumps(exported).encode()})
        expect(page.locator('#profile-name')).to_have_value('Imported test')
        exported['bindings']['dial_ccw']['modifiers']=['ctrl']
        page.locator('#file').set_input_files({'name':'bad.json','mimeType':'application/json','buffer':json.dumps(exported).encode()})
        expect(page.locator('#message')).to_contain_text('Mouse modifiers')
        page.locator('#preset').select_option('claude')
        page.locator('#load-preset').click()
        page.locator('#test-input').fill('Test typing')
        page.locator('#test-input').press('Enter')
        assert 'Enter' in page.locator('#test-event').inner_text()
        page.screenshot(path=str(ROOT/'research'/'ui-preview.png'),full_page=True)
        page.set_viewport_size({'width':390,'height':844})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert not errors, errors
        page.locator('#quit').click()
        browser.close()
        print('UI smoke passed: device discovery, editor, preview/cancel, profiles, validation, test area, responsive layout. No hardware writes.')
finally:
    server.terminate()
    server.wait(timeout=5)
