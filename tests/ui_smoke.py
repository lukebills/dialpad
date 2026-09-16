"""Optional Playwright smoke: isolated settings, read-only USB, no Apply writes."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
settings = tempfile.TemporaryDirectory()
command = ([str(ROOT / 'dist/Dialpad.app/Contents/MacOS/Dialpad'), '--no-browser']
           if '--packaged' in sys.argv else [sys.executable, str(ROOT / 'app.py'), '--no-browser'])
server = subprocess.Popen(command + ['--settings-dir', settings.name], stdout=subprocess.PIPE, text=True)
try:
    url = server.stdout.readline().strip()
    assert url.startswith('http://127.0.0.1:')
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless=True)
        page = browser.new_page(viewport={'width':1280,'height':1100})
        errors, writes = [], []
        page.on('pageerror', lambda error: errors.append(str(error)))
        def prevent_write(route):
            writes.append(route.request.url)
            route.abort()
        page.route('**/api/apply', prevent_write)
        page.route('**/api/setups/cycle', prevent_write)
        page.goto(url)
        expect(page.locator('#connection')).to_have_text('Keypad connected')
        expect(page.locator('#setup-select option')).to_have_count(4)
        assert page.locator('.key').count() == 6
        assert page.locator('#template-list, #save-setup, #setup-editor').count() == 0
        expect(page.locator('#key-editor')).to_be_hidden()
        expect(page.locator('#cycling-panel')).to_be_visible()

        def state():
            return page.evaluate("api('setups')")
        def saved():
            expect(page.locator('#autosave-status')).to_have_text('Saved in app')
        def current_saved():
            data = state()
            name = page.locator('#setup-select').input_value()
            return next(item for item in data['profiles'] if item['name'] == name)
        def settings_open():
            if not page.locator('#setup-settings').evaluate('(el) => el.open'):
                page.locator('#setup-settings > summary').click()
        def export_profile():
            settings_open()
            with page.expect_download() as download:
                page.locator('#export').click()
            return json.loads(Path(download.value.path()).read_text())
        def import_profile(profile):
            page.locator('#file').set_input_files({'name':'profile.json','mimeType':'application/json',
                                                  'buffer':json.dumps(profile).encode()})

        # The same live keypad is the editor; selecting a key swaps the side panel.
        page.locator('[data-control="key1"]').click()
        expect(page.locator('#key-editor')).to_be_visible()
        expect(page.locator('#cycling-panel')).to_be_hidden()
        page.locator('#label').fill('My media button')
        page.locator('#action').select_option('next')
        saved()
        assert current_saved()['labels']['key1'] == 'My media button'
        assert current_saved()['bindings']['key1']['action'] == 'next'
        page.locator('#close-key-editor').click()
        expect(page.locator('#key-editor')).to_be_hidden()
        expect(page.locator('#cycling-panel')).to_be_visible()

        # Rename updates the selected cycle entry in place, without duplication.
        settings_open()
        old_name = page.locator('#setup-select').input_value()
        old_order = state()['order']
        page.locator('#profile-name').fill('My media')
        saved()
        expect(page.locator('#setup-select')).to_have_value('My media')
        assert state()['order'] == ['My media' if n == old_name else n for n in old_order]
        assert len(state()['profiles']) == 4

        # Switching immediately after editing flushes the pending debounce.
        page.locator('[data-control="key1"]').click()
        page.locator('#label').fill('Flushed on switch')
        page.locator('#setup-select').select_option('Web browsing · Mac')
        expect(page.locator('#setup-select')).to_have_value('Web browsing · Mac')
        expect(page.locator('#key-editor')).to_be_hidden()
        assert next(p for p in state()['profiles'] if p['name'] == 'My media')['labels']['key1'] == 'Flushed on switch'
        page.locator('#setup-select').select_option('My media')
        expect(page.locator('[data-control="key1"] .key-label')).to_have_text('Flushed on switch')

        # Every saved setup is listed; selection is independent from editing.
        box = page.get_by_role('checkbox', name='Include My media in cycle', exact=True)
        box.uncheck()
        page.wait_for_function("() => !cycleOrder.includes('My media') && !orderSaving")
        assert 'My media' not in state()['order']
        expect(page.locator('.cycle-row')).to_have_count(4)
        box.check()
        page.wait_for_function("() => cycleOrder.at(-1) === 'My media' && !orderSaving")
        page.get_by_role('button', name='Move My media up', exact=True).click()
        page.wait_for_function("() => cycleOrder.at(-2) === 'My media' && !orderSaving")
        assert state()['order'][-2] == 'My media'

        page.locator('#create-setup').click()
        expect(page.locator('#profile-name')).to_have_value('New setup')
        saved()
        expect(page.locator('#setup-select option')).to_have_count(5)
        assert 'New setup' not in state()['order']
        settings_open()
        page.locator('#preset').select_option('claude')
        page.locator('#load-preset').click()
        saved()
        expect(page.locator('#setup-select')).to_have_value('Claude Code · Mac')
        page.locator('[data-control="key1"]').click()
        page.locator('#flow-mode').select_option('ptt')
        saved()
        assert current_saved()['bindings']['key1'] == {'type':'shortcut','key':'NONE','modifiers':['ctrl','alt']}

        # Real validation/preview uses read-only discovery; never click Apply.
        page.locator('#advanced-tools > summary').click()
        page.locator('#preview').click()
        expect(page.locator('#review')).to_be_visible()
        expect(page.locator('#review-content')).to_contain_text('Key 1  →  Ctrl + ⌥ / Alt')
        with page.expect_response('**/api/devices', timeout=6500):
            pass
        assert page.evaluate('preview !== null'), 'Discovery must preserve a pending review'
        page.get_by_role('button', name='Cancel', exact=True).click()
        page.locator('#flow-mode').select_option('handsfree')
        for control, key in [('dial_ccw','UP'),('dial_cw','DOWN')]:
            page.locator(f'[data-control="{control}"]').click()
            expect(page.locator('#key')).to_have_value(key)
        page.locator('#type').select_option('multi_tap')
        expect(page.locator('#type')).to_have_value('shortcut')

        # Legacy conversion, independent tap actions and timing autosave.
        page.locator('[data-control="key5"]').click()
        page.locator('#type').select_option('copy_paste')
        page.locator('#copy-format').select_option('formatted')
        page.locator('#convert-multi').click()
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
        saved()
        key5 = current_saved()['bindings']['key5']
        assert key5['window_ms'] == 450
        assert key5['single']['formatting'] == 'plain'
        assert key5['double'] == {'type':'shortcut','key':'V','modifiers':['cmd']}
        assert key5['triple'] == {'type':'media','action':'play_pause'}
        page.locator('#tap-window').fill('99')
        page.locator('#tap-window').press('Tab')
        expect(page.locator('#tap-window')).to_have_value('450')
        page.locator('[data-control="key6"]').click()
        page.locator('#type').select_option('multi_tap')
        expect(page.locator('#tap-window')).to_have_value('350')
        page.locator('#tap-double-type').select_option('mouse')
        page.locator('#tap-double-action').select_option('middle_click')
        saved()
        exported = export_profile()
        assert exported['bindings']['key5'] == key5
        assert exported['bindings']['key6']['double']['action'] == 'middle_click'
        exported['name'] = 'Imported coding'
        import_profile(exported)
        expect(page.locator('#profile-name')).to_have_value('Imported coding')
        saved()
        assert current_saved()['bindings'] == exported['bindings']
        assert len(state()['profiles']) == 5
        bad = json.loads(json.dumps(exported))
        bad['bindings']['dial_ccw'] = {'type':'mouse','action':'wheel_up','modifiers':['ctrl']}
        import_profile(bad)
        expect(page.locator('#message')).to_contain_text('Mouse modifiers')
        assert current_saved()['bindings'] == exported['bindings']

        page.evaluate('window.scrollTo(0,0)')
        page.screenshot(path='/private/tmp/dialpad-key-editor-desktop.png', full_page=True)
        page.set_viewport_size({'width':390,'height':844})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.locator('.editor').screenshot(path='/private/tmp/dialpad-multi-tap-editor.png')
        page.set_viewport_size({'width':1280,'height':1100})
        page.locator('#close-key-editor').click()
        # Simulate only desktop readiness; the temporary settings have no active cycle.
        page.evaluate("api('desktop-ready', {ready:true}).then(showRuntime)")
        page.get_by_role('checkbox', name='Include Imported coding in cycle', exact=True).check()
        page.wait_for_function('() => !orderSaving')
        page.locator('#cycle-enabled').click()
        expect(page.locator('#review')).to_be_visible()
        expect(page.locator('#review-content')).to_contain_text('Imported coding')
        expect(page.locator('#review-content')).to_contain_text('F18')
        page.get_by_role('button', name='Cancel', exact=True).click()
        expect(page.locator('#cycle-enabled')).not_to_be_checked()
        assert state()['enabled'] is False

        # New setups persist immediately; capacity errors preserve the current setup.
        for count in [6,7,8]:
            page.locator('#create-setup').click()
            expect(page.locator('#setup-select option')).to_have_count(count)
            saved()
        last_name = page.locator('#setup-select').input_value()
        page.locator('#create-setup').click()
        expect(page.locator('#message')).to_contain_text('up to eight setups')
        assert len(state()['profiles']) == 8
        expect(page.locator('#setup-select')).to_have_value(last_name)
        page.once('dialog', lambda dialog: dialog.accept())
        page.locator('#delete-setup').click()
        expect(page.locator('#setup-select option')).to_have_count(7)
        page.locator('#test-input').fill('Test typing')
        page.locator('#test-input').press('Enter')
        expect(page.locator('#test-event')).to_contain_text('Enter')
        page.locator('#setup-settings > summary').click()
        page.locator('#advanced-tools > summary').click()
        page.evaluate('window.scrollTo(0,0)')
        page.screenshot(path=str(ROOT/'research'/'ui-preview.png'),full_page=True)
        page.set_viewport_size({'width':390,'height':844})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert not errors, errors
        assert not writes, writes
        page.locator('#quit').click()
        browser.close()
        print('UI smoke passed: live editing, autosave/switch/rename, independent cycle checkboxes, multi-tap import/export, capacity, preview/cancel and mobile layout. No hardware writes.')
finally:
    server.terminate()
    server.wait(timeout=5)
    settings.cleanup()
