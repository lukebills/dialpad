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
            assert name in page.locator('#saved-setup').text_content()
        expect(page.locator('#setup-editor')).not_to_have_attribute('open', '')
        expect(page.locator('.template-card')).to_have_count(4)
        page.get_by_role('button',name='Remove Media · Mac from cycle',exact=True).click()
        expect(page.locator('.cycle-row')).to_have_count(3)
        page.locator('.template-card').filter(has_text='Media · Mac').drag_to(page.locator('#cycle-list'), target_position={'x':10,'y':page.locator('#cycle-list').bounding_box()['height']-3})
        expect(page.locator('.cycle-row')).to_have_count(4)
        expect(page.locator('.cycle-row').last).to_contain_text('Media')
        page.get_by_role('button',name='Move Media · Mac up',exact=True).click()
        expect(page.locator('.cycle-row').nth(2)).to_contain_text('Media')
        page.locator('#setup-editor > summary').click()
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
        with page.expect_response('**/api/devices', timeout=6000):
            pass
        assert page.evaluate('preview !== null'), 'Automatic discovery must preserve the review'
        page.get_by_role('button',name='Cancel',exact=True).click()
        page.locator('#flow-mode').select_option('handsfree')
        page.locator('[data-control="key5"]').click()
        page.locator('#type').select_option('copy_paste')
        expect(page.locator('[data-control="key5"] .key-shortcut')).to_have_text('Copy ⇄ Paste')
        expect(page.locator('#toggle-note')).to_be_visible()
        expect(page.locator('#copy-format')).to_have_value('plain')
        expect(page.locator('#copy-reset')).to_have_value('10')
        expect(page.locator('#copy-double')).to_have_value('true')
        page.locator('#copy-format').select_option('formatted')
        page.locator('#copy-reset').select_option('30')
        page.locator('#copy-double').select_option('false')
        with page.expect_download() as toggle_download:
            page.locator('#export').click()
        toggle_profile=json.loads(Path(toggle_download.value.path()).read_text())
        assert toggle_profile['bindings']['key5']['formatting']=='formatted'
        assert toggle_profile['bindings']['key5']['reset_seconds']==30
        assert toggle_profile['bindings']['key5']['double_tap_cut'] is False
        page.locator('#file').set_input_files({'name':'toggle.json','mimeType':'application/json','buffer':json.dumps(toggle_profile).encode()})
        expect(page.locator('#copy-format')).to_have_value('formatted')
        expect(page.locator('#copy-reset')).to_have_value('30')
        expect(page.locator('#copy-double')).to_have_value('false')
        # Conversion is an explicit draft edit, retaining the legacy formatting choice.
        page.locator('#convert-multi').click()
        expect(page.locator('#type')).to_have_value('multi_tap')
        expect(page.locator('#tap-window')).to_have_value('350')
        for tap, action in [('single','copy'),('double','paste'),('triple','cut')]:
            expect(page.locator(f'#tap-{tap}-action')).to_have_value(action)
            expect(page.locator(f'#tap-{tap}-format')).to_have_value('formatted')
        page.locator('#tap-single-format').select_option('plain')
        page.locator('#tap-window').fill('450')
        page.locator('#tap-window').press('Tab')
        page.locator('#tap-double-type').select_option('shortcut')
        page.locator('#tap-double-key').select_option('V')
        page.locator('#tap-double-cmd').check()
        page.locator('#tap-triple-type').select_option('media')
        page.locator('#tap-triple-action').select_option('play_pause')
        # Each key gets independent tap actions, with default clipboard gestures.
        page.locator('[data-control="key6"]').click()
        page.locator('#type').select_option('multi_tap')
        expect(page.locator('#tap-window')).to_have_value('350')
        expect(page.locator('#tap-single-format')).to_have_value('plain')
        page.locator('#tap-double-type').select_option('mouse')
        page.locator('#tap-double-action').select_option('middle_click')
        with page.expect_download() as tap_download:
            page.locator('#export').click()
        tap_profile=json.loads(Path(tap_download.value.path()).read_text())
        key5=tap_profile['bindings']['key5']
        assert key5['window_ms']==450
        assert key5['single']['action']=='copy' and key5['single']['formatting']=='plain'
        assert key5['double']=={'type':'shortcut','key':'V','modifiers':['cmd']}
        assert key5['triple']=={'type':'media','action':'play_pause'}
        assert tap_profile['bindings']['key6']['double']['action']=='middle_click'
        page.locator('#file').set_input_files({'name':'multi.json','mimeType':'application/json','buffer':json.dumps(tap_profile).encode()})
        expect(page.locator('#tap-double-action')).to_have_value('middle_click')
        page.locator('[data-control="key5"]').click()
        expect(page.locator('#tap-window')).to_have_value('450')
        expect(page.locator('#tap-double-key')).to_have_value('V')
        expect(page.locator('#tap-double-cmd')).to_be_checked()
        expect(page.locator('[data-control="key5"] .key-shortcut')).to_contain_text('1× Copy')
        expect(page.locator('[data-control="key5"] .key-shortcut')).to_contain_text('2× ⌘ / Win + V')
        expect(page.locator('[data-control="key5"] .key-shortcut')).to_contain_text('3× play pause')
        page.set_viewport_size({'width':390,'height':844})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.locator('.editor').screenshot(path='/private/tmp/dialpad-multi-tap-editor.png')
        page.set_viewport_size({'width':1280,'height':1500})
        page.locator('#tap-window').fill('99')
        page.locator('#tap-window').press('Tab')
        expect(page.locator('#tap-window')).to_have_value('450')
        page.locator('[data-control="dial_ccw"]').click()
        page.locator('#type').select_option('multi_tap')
        expect(page.locator('#type')).to_have_value('shortcut')
        page.locator('#load-preset').click()
        page.locator('[data-control="key2"]').click()
        assert page.locator('#key').input_value()=='ENTER'
        page.locator('#preview').click()
        page.locator('#review').wait_for(state='visible')
        assert 'Key 2  →  ENTER' in page.locator('#review-content').text_content()
        page.get_by_role('button',name='Cancel',exact=True).click()
        page.locator('[data-control="dial_ccw"]').click()
        assert page.locator('#key').input_value()=='UP'
        page.locator('[data-control="dial_cw"]').click()
        assert page.locator('#key').input_value()=='DOWN'
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
        exported['bindings']['dial_ccw']={'type':'mouse','action':'wheel_up','modifiers':['ctrl']}
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
        expect(page.locator('#cycle-note')).to_contain_text('Choose your cycling templates')
        page.locator('#save-setup').click()
        expect(page.locator('#saved-setup option')).to_have_count(1)
        page.locator('#setup-editor > summary').click()
        page.locator('#preset').select_option('codex')
        page.locator('#load-preset').click()
        page.locator('#save-setup').click()
        expect(page.locator('#saved-setup option')).to_have_count(2)
        page.locator('#enable-cycle').click()
        expect(page.locator('#review-content')).to_contain_text('F18')
        expect(page.locator('#review-content')).to_contain_text('Claude Code')
        expect(page.locator('#review-content')).to_contain_text('Codex terminal')
        page.get_by_role('button', name='Cancel', exact=True).click()
        page.locator('.template-card').filter(has_text='Claude Code').get_by_role('button',name='Edit',exact=True).click()
        expect(page.locator('#profile-name')).to_have_value('Claude Code · Mac')
        page.once('dialog', lambda dialog: dialog.accept())
        page.locator('.template-card').filter(has_text='Claude Code').get_by_role('button',name='Delete',exact=True).click()
        expect(page.locator('#saved-setup option')).to_have_count(1)
        # Render the live diagram using a mocked active state; no hardware Apply.
        current = json.loads((ROOT / 'ui/starters.json').read_text())['mac']['media']
        current['labels']['dial_press'] = 'Next setup'
        current['bindings']['dial_press'] = {'type':'shortcut','key':'F18','modifiers':[]}
        saved_state.update(enabled=True, current=current, cycle_names=[current['name']], active=0, generation=1)
        expect(page.locator('#live-title')).to_contain_text('Media')
        expect(page.locator('.mini-key')).to_have_count(6)
        expect(page.locator('.mini-dial')).to_contain_text('Next setup')
        expect(page.locator('.mini-turn').first).to_contain_text('Volume down')
        page.locator('#live-keys').screenshot(path=str(ROOT/'research'/'live-layout-preview.png'))
        page.locator('#test-input').fill('Test typing')
        page.locator('#test-input').press('Enter')
        assert 'Enter' in page.locator('#test-event').inner_text()
        page.locator('#done-editing').click()
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
