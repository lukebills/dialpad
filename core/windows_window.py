"""Supervise the native Windows editor; keep the session token off command lines."""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading

_status = {'native': True, 'ready': False, 'visible': False}
_status_lock = threading.Lock()
_editor = None


def window_status():
    with _status_lock:
        return dict(_status)


def stop():
    if _editor is not None:
        _editor.close()


class WindowsEditor:
    def __init__(self, url, settings_folder, notify):
        global _editor
        root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1] / 'build'))
        executable = root / ('windows-window' if not getattr(sys, 'frozen', False) else 'windows') / 'DialpadWindow.exe'
        if not executable.is_file():
            raise RuntimeError('Windows editor is missing. Build the app or extract the entire portable ZIP.')
        self.lock = threading.Lock()
        self.process = subprocess.Popen([str(executable)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, encoding='utf-8', creationflags=0x08000000)
        _editor = self
        # WebView data stays writable when the EXE is in a read-only location.
        self.send({'url': url, 'user_data': str(Path(settings_folder) / 'WebView2'),
                   'smoke': os.environ.get('DIALPAD_WINDOW_SMOKE') == '1'})
        def watch():
            for line in self.process.stdout:
                try:
                    event = json.loads(line)
                    with _status_lock:
                        if event.get('kind') == 'error':
                            _status.update(ready=False, error=event.get('message', 'Window error'))
                        else:
                            _status.update({k: v for k, v in event.items() if k != 'kind'})
                    notify(event)
                except (ValueError, TypeError):
                    continue
            code = self.process.wait()
            with _status_lock:
                _status.update(ready=False, visible=False)
            notify({'kind': 'exit', 'code': code})
        threading.Thread(target=watch, name='Dialpad window', daemon=True).start()

    def send(self, command):
        with self.lock:
            if self.process.poll() is None:
                self.process.stdin.write(json.dumps(command) + '\n')
                self.process.stdin.flush()

    def show(self):
        self.send({'kind': 'show'})

    def status(self, name):
        self.send({'kind': 'status', 'name': name})

    def close(self):
        try:
            self.send({'kind': 'quit'})
            self.process.wait(timeout=3)
        except (OSError, subprocess.TimeoutExpired):
            self.process.terminate()
