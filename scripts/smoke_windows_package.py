"""Start the Windows package with isolated settings; no USB writes or OS input."""
import json
from pathlib import Path
import subprocess
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as folder:
    process = subprocess.Popen([str(ROOT / 'dist/Dialpad/Dialpad.exe'), '--settings-dir', folder])
    try:
        session_file = Path(folder) / 'session.json'
        deadline = time.monotonic() + 45
        while not session_file.exists():
            if process.poll() is not None or time.monotonic() > deadline:
                raise RuntimeError('Packaged Windows app did not start.')
            time.sleep(.2)
        session = json.loads(session_file.read_text(encoding='utf-8'))
        def api(path, body=None):
            request = urllib.request.Request(session['base'] + 'api/' + path,
                headers={'Authorization': 'Bearer ' + session['token'], 'Content-Type': 'application/json'},
                data=json.dumps(body).encode() if body is not None else None)
            with urllib.request.urlopen(request, timeout=5) as response:
                return json.load(response)
        while True:
            state = api('setups')
            if state['ready']:
                break
            if process.poll() is not None or time.monotonic() > deadline:
                raise RuntimeError('Windows companion or hotkeys unavailable: ' + state.get('error', ''))
            time.sleep(.2)
        assert state['profiles'] and not state['enabled']
        assert isinstance(api('devices')['devices'], list)
        # A second launch must reuse the first backend and request editor reopening.
        previous = state['show_request']
        subprocess.run([str(ROOT / 'dist/Dialpad/Dialpad.exe'), '--settings-dir', folder], timeout=15, check=True)
        assert api('setups')['show_request'] > previous
        api('quit', {})
        process.wait(timeout=15)
        assert process.returncode == 0
        print('Windows packaged smoke passed: startup, presets, global hotkeys, discovery, singleton and quit. No hardware writes.')
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=10)
