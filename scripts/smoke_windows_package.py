"""Start the Windows package with isolated settings; no USB writes or OS input."""
import json
import os
import shutil
import struct
from pathlib import Path
import subprocess
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
# Both executables must be GUI-subsystem PE files, so ordinary launches show no console.
for executable in (ROOT / 'dist/Dialpad/Dialpad.exe', ROOT / 'dist/Dialpad/_internal/windows/DialpadWindow.exe'):
    image = executable.read_bytes()
    pe = struct.unpack_from('<I', image, 0x3c)[0]
    assert image[pe:pe + 4] == b'PE\0\0'
    assert struct.unpack_from('<H', image, pe + 24 + 68)[0] == 2, executable.name

with tempfile.TemporaryDirectory() as folder:
    process = subprocess.Popen([str(ROOT / 'dist/Dialpad/Dialpad.exe'), '--settings-dir', folder], env={**os.environ, 'DIALPAD_WINDOW_SMOKE': '1'})
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
        while True:
            window = api('desktop-window')
            if window['ready']:
                break
            if window.get('error') or process.poll() is not None or time.monotonic() > deadline:
                raise RuntimeError('Native Windows window failed: ' + str(window))
            time.sleep(.2)
        assert window['native'] and window['keys'] == 6
        assert window['hidden'] and window['reopened']
        shutil.copy2(Path(folder) / 'windows-preview.png', ROOT / 'build/windows-preview.png')
        assert 'guide' in api('agent')
        assert state['profiles'] and not state['enabled']
        assert isinstance(api('devices')['devices'], list)
        # A second launch must reuse the first backend and request editor reopening.
        previous = state['show_request']
        subprocess.run([str(ROOT / 'dist/Dialpad/Dialpad.exe'), '--settings-dir', folder], timeout=15, check=True)
        assert api('setups')['show_request'] > previous
        api('quit', {})
        process.wait(timeout=15)
        assert process.returncode == 0
        print('Windows packaged smoke passed: native WebView2 editor, six keys, hide/reopen, agent guide, presets, global hotkeys, discovery, singleton and quit. No hardware writes.')
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=10)
        # WebView2 releases its profile asynchronously after the host exits.
        # Require eventual release instead of racing TemporaryDirectory cleanup.
        for attempt in range(100):
            try:
                shutil.rmtree(folder)
                break
            except PermissionError:
                if attempt == 99:
                    raise
                time.sleep(.1)
