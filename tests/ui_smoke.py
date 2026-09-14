"""Optional Playwright smoke test. Starts a local server; NEVER clicks Apply."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
settings = tempfile.TemporaryDirectory()
server = subprocess.Popen(([str(ROOT / 'dist/Dialpad.app/Contents/MacOS/Dialpad'), '--no-browser'] if '--packaged' in sys.argv else [sys.executable, str(ROOT / 'app.py'), '--no-browser']) + ['--settings-dir', settings.name], stdout=subprocess.PIPE, text=True)
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
        expect(page.locator('#saved-setup option')).to_have_count(4)
        for name in ['Media', 'Web browsing', 'Word', 'Apple Mail']:
            assert name in page.locator('#saved-setup').inner_text()
        for kind, first_key in [('media','play_pause'),('web','L'),('word','NONE'),('mail','NONE')]:
            page.locator('#preset').select_option(kind)
            page.locator('#load-preset').click()
            page.locator('[data-control="key1"]').click()
            assert page.locator('#action' if kind=='media' else '#key').input_value() == first_key
            if kind=='media':
                expect(page.locator('#flow-setting')).to_be_hidden()
                expect(page.locator('[data-control="dial_ccw"] span')).to_have_text('Volume down')
            if kind=='mail':
                page.locator('[data-control="key2"]').click()
                assert page.locator('#key').input_value() == 'N'
        page.locator('#preset').select_option('claude')
        page.locator('#load-preset').click()
        page.locator('[data-control="key1"]').click()
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
        assert page.locator('#key').input_value()=='NONE'
        with page.expect_download() as download:
            page.locator('#export').click()
        exported = json.loads(Path(download.value.path()).read_text())
        assert exported['bindings']['key1']['modifiers']==['ctrl','cmd','alt']
        exported['name']='Imported test'
        page.locator('#file').set_input_files({'name':'profile.json','mimeType':'application/json','buffer':json.dumps(exported).encode()})
        expect(page.locator('#profile-name')).to_have_value('Imported test')
        exported['bindings']['dial_ccw']['modifiers']=['ctrl']
        page.locator('#file').set_input_files({'name':'bad.json','mimeType':'application/json','buffer':json.dumps(exported).encode()})
        expect(page.locator('#message')).to_contain_text('Mouse modifiers')
        page.locator('#preset').select_option('claude')
        page.locator('#load-preset').click()
        # Isolate saved-setup UI testing from the user's on-disk setups.
        saved_state = {'profiles': [], 'enabled': False, 'ready': True, 'active': None,
                       'generation': 0, 'current': None, 'cycle_names': [], 'error': ''}
        page.route('**/api/setups', lambda route: route.fulfill(json=saved_state))
        def save_setups(route):
            saved_state['profiles'] = route.request.post_data_json['profiles']
            route.fulfill(json=saved_state)
        page.route('**/api/setups/save', save_setups)
        def cycle_preview(route):
            profiles = json.loads(json.dumps(saved_state['profiles']))
            for item in profiles:
                item['bindings']['dial_press'] = {'type':'shortcut','key':'F18','modifiers':[]}
            route.fulfill(json={'nonce':'mock-never-apply','layer':1,'profiles':profiles})
        page.route('**/api/setups/preview', cycle_preview)
        expect(page.locator('#cycle-note')).to_contain_text('Desktop dial shortcut ready')
        page.locator('#save-setup').click()
        expect(page.locator('#saved-setup option')).to_have_count(1)
        page.locator('#preset').select_option('codex')
        page.locator('#load-preset').click()
        page.locator('#save-setup').click()
        expect(page.locator('#saved-setup option')).to_have_count(2)
        page.locator('#enable-cycle').click()
        expect(page.locator('#review-content')).to_contain_text('F18')
        expect(page.locator('#review-content')).to_contain_text('Claude Code')
        expect(page.locator('#review-content')).to_contain_text('Codex terminal')
        page.get_by_role('button', name='Cancel', exact=True).click()
        page.locator('#saved-setup').select_option('0')
        page.locator('#edit-setup').click()
        expect(page.locator('#profile-name')).to_have_value('Claude Code · Mac')
        page.locator('#remove-setup').click()
        expect(page.locator('#saved-setup option')).to_have_count(1)
        # Render the live diagram using a mocked active state; no hardware Apply.
        current = json.loads((ROOT / 'ui/starters.json').read_text())['mac']['media']
        current['labels']['dial_press'] = 'Next setup'
        current['bindings']['dial_press'] = {'type':'shortcut','key':'F18','modifiers':[]}
        saved_state.update(enabled=True, current=current, cycle_names=[current['name']], active=0, generation=1)
        expect(page.locator('#live-title')).to_contain_text('Media')
        page.locator('#live-title').click()
        expect(page.locator('.mini-key')).to_have_count(6)
        expect(page.locator('.mini-dial')).to_contain_text('Next setup')
        expect(page.locator('.mini-turn').first).to_contain_text('Volume down')
        page.locator('#live-keys').screenshot(path=str(ROOT/'research'/'live-layout-preview.png'))
        page.locator('#test-input').fill('Test typing')
        page.locator('#test-input').press('Enter')
        assert 'Enter' in page.locator('#test-event').inner_text()
        page.evaluate('window.scrollTo(0,0)')
        page.screenshot(path=str(ROOT/'research'/'ui-preview.png'),full_page=True)
        page.set_viewport_size({'width':390,'height':844})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert not errors, errors
        page.locator('#quit').click()
        browser.close()
        print('UI smoke passed: device discovery, editor, preview/cancel, saved setups and cycle review, profiles, validation, test area, responsive layout. No hardware writes.')
finally:
    server.terminate()
    server.wait(timeout=5)
    settings.cleanup()
