"""Read-only smoke check of the packaged Mac WebKit window and F18 registration."""
import json
from pathlib import Path
import subprocess
import urllib.request
import tempfile

ROOT = Path(__file__).resolve().parents[1]
bundle = ROOT / 'dist/Dialpad.app/Contents'
settings = tempfile.TemporaryDirectory()
server = subprocess.Popen([str(bundle / 'MacOS/Dialpad'), '--no-browser', '--settings-dir', settings.name], stdout=subprocess.PIPE, text=True)
try:
    url = server.stdout.readline().strip()
    assert url.startswith('http://127.0.0.1:')
    host = bundle / 'Frameworks/DialpadDesktop'
    result = subprocess.run([str(host), '--smoke-test'], input=url + '\n', text=True,
                            capture_output=True, timeout=30, check=True)
    status = json.loads(next(line for line in result.stdout.splitlines() if line.startswith('{')))
    assert status['keys'] == 6, status
    assert status['ready'] is True, status
    assert status['background'] and status['reopened'] and status['hotkeys'], status
    assert status['connection'] == 'Keypad connected', status
    base, token = url.split('#', 1)
    with urllib.request.urlopen(urllib.request.Request(base + 'api/setups', headers={'Authorization': 'Bearer ' + token})) as response:
        state = json.load(response)
    assert state['enabled'] is False
    print('Native smoke passed: packaged WebKit editor loaded, six keys visible, F18/F19 registered, background hide/reopen verified, keypad discovered. No hardware writes.')
finally:
    server.terminate()
    server.wait(timeout=5)
    settings.cleanup()
