"""Dialpad local configurator. No device writes occur until preview + Apply."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).parent))
CONTROLS = [f'key{i}' for i in range(1, 7)] + ['dial_ccw', 'dial_press', 'dial_cw']
TOKEN = secrets.token_urlsafe(32)
WRITE_LOCK = threading.Lock()
PREVIEWS: dict = {}

def validate_profile(profile):
    from core.protocol import encode_binding
    if not isinstance(profile, dict) or (type(profile.get('version')) is not int or profile.get('version') != 1):
        raise ValueError('Expected a Dialpad version 1 profile.')
    layer = profile.get('layer')
    if type(layer) is not int or layer not in (1, 2, 3):
        raise ValueError('Layer must be 1, 2 or 3.')
    if not isinstance(profile.get('name'), str) or not 1 <= len(profile['name']) <= 80:
        raise ValueError('Profile name must contain 1–80 characters.')
    bindings = profile.get('bindings')
    if not isinstance(bindings, dict) or set(bindings) != set(CONTROLS):
        raise ValueError('Profile must contain six keys and three dial actions.')
    if sum(isinstance(a, dict) and a.get('type') == 'copy_paste' for a in bindings.values()) > 1:
        raise ValueError('Use one alternating Copy / Paste key per setup.')
    for control, action in bindings.items():
        encode_binding(control, action, layer)
    return profile

from core.setups import Setups
SETUPS = Setups(validate_profile)

def profile_packets(profile):
    from core.protocol import encode_binding
    return [bytes(64)] + [packet for c in CONTROLS for packet in encode_binding(c, profile['bindings'][c], profile['layer'])]

def make_preview(body):
    from core.protocol import encode_binding
    profile = validate_profile(body.get('profile'))
    if any(a.get('type') == 'copy_paste' for a in profile['bindings'].values()) and not body.get('_cycle'):
        raise ValueError('Save this template and enable it in the dial cycle to use Copy / Paste.')
    controls = body.get('controls')
    if not isinstance(controls, list) or not controls or any(c not in CONTROLS for c in controls) or len(set(controls)) != len(controls):
        raise ValueError('Select at least one distinct control to apply.')
    device_id = body.get('device_id')
    if not isinstance(device_id, str) or not device_id:
        raise ValueError('Select the connected keypad first.')
    packets = [bytes(64)]
    for c in controls:
        packets.extend(encode_binding(c, profile['bindings'][c], profile['layer']))
    nonce = secrets.token_urlsafe(24)
    with WRITE_LOCK:
        now = time.monotonic()
        for key in list(PREVIEWS):
            if PREVIEWS[key]['expires'] < now:
                del PREVIEWS[key]
        if len(PREVIEWS) >= 50:
            PREVIEWS.clear()
        PREVIEWS[nonce] = {'expires': now + 120, 'device_id': device_id, 'packets': packets}
    return {'nonce': nonce, 'controls': controls, 'layer': profile['layer'], 'packet_count': len(packets), 'sha256': hashlib.sha256(b''.join(packets)).hexdigest()}

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass  # Never log the session secret or profile contents.

    def reply(self, status, data, content_type='application/json'):
        raw = json.dumps(data).encode() if content_type == 'application/json' else data
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        self.end_headers()
        self.wfile.write(raw)

    def allowed(self):
        expected = f'127.0.0.1:{self.server.server_port}'
        if self.headers.get('Host') != expected:
            self.reply(403, {'error': 'Invalid host.'})
            return False
        origin = self.headers.get('Origin')
        if origin and origin != f'http://{expected}':
            self.reply(403, {'error': 'Invalid origin.'})
            return False
        if self.path.startswith('/api/') and not secrets.compare_digest(self.headers.get('Authorization', ''), f'Bearer {TOKEN}'):
            self.reply(401, {'error': 'Reopen Dialpad from its launcher to reconnect.'})
            return False
        return True

    def do_GET(self):
        if not self.allowed():
            return
        if self.path == '/api/setups':
            with WRITE_LOCK:
                self.reply(200, SETUPS.state())
            return
        if self.path == '/api/devices':
            try:
                from core.transport import list_devices
                self.reply(200, {'devices': list_devices(), 'platform': sys.platform})
            except Exception as exc:
                self.reply(503, {'error': str(exc)})
            return
        assets = {'/': ('index.html', 'text/html; charset=utf-8'), '/app.js': ('app.js', 'text/javascript'), '/style.css': ('style.css', 'text/css'), '/starters.json': ('starters.json', 'application/json; charset=utf-8'), '/icon.svg': ('icon.svg', 'image/svg+xml')}
        if self.path not in assets:
            self.reply(404, {'error': 'Not found.'})
            return
        name, mime = assets[self.path]
        self.reply(200, (ROOT / 'ui' / name).read_bytes(), mime)

    def do_POST(self):
        if not self.allowed():
            return
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 65536:
                raise ValueError('Request too large or empty.')
            self.connection.settimeout(10)
            body = json.loads(self.rfile.read(size))
            if not isinstance(body, dict):
                raise ValueError('Expected a JSON object.')
            if self.path == '/api/validate':
                validate_profile(body.get('profile'))
                self.reply(200, {'valid': True})
            elif self.path == '/api/preview':
                self.reply(200, make_preview({k: v for k, v in body.items() if k != '_cycle'}))
            elif self.path == '/api/setups/save':
                with WRITE_LOCK:
                    self.reply(200, SETUPS.save(body.get('profiles')))
            elif self.path == '/api/setups/order':
                with WRITE_LOCK:
                    self.reply(200, SETUPS.save_order(body.get('names')))
            elif self.path == '/api/desktop-ready':
                with WRITE_LOCK:
                    SETUPS.ready = body.get('ready') is True
                    if SETUPS.ready:
                        SETUPS.restore()
                    if not SETUPS.ready:
                        SETUPS.disable(body.get('error', 'Desktop shortcut unavailable.'))
                    self.reply(200, SETUPS.state())
            elif self.path == '/api/setups/preview':
                with WRITE_LOCK:
                    profiles = SETUPS.snapshot(body.get('names'))
                preview = make_preview({'profile': profiles[0], 'controls': CONTROLS, 'device_id': body.get('device_id'), '_cycle': True})
                with WRITE_LOCK:
                    PREVIEWS[preview['nonce']]['cycle_profiles'] = profiles
                self.reply(200, {**preview, 'profiles': profiles})
            elif self.path == '/api/setups/cycle':
                from core.transport import write_packets
                # Ignore a second press while a write is in progress; never queue writes.
                if not WRITE_LOCK.acquire(blocking=False):
                    raise ValueError('A keypad transfer is already in progress.')
                try:
                    self.reply(200, SETUPS.cycle(write_packets, profile_packets))
                finally:
                    WRITE_LOCK.release()
            elif self.path == '/api/setups/disable':
                with WRITE_LOCK:
                    SETUPS.disable()
                    self.reply(200, SETUPS.state())
            elif self.path == '/api/apply':
                from core.transport import write_packets
                with WRITE_LOCK:
                    nonce = body.get('nonce')
                    if not isinstance(nonce, str):
                        raise ValueError('Preview the changes first.')
                    preview = PREVIEWS.pop(nonce, None)
                    if not preview or preview['expires'] < time.monotonic():
                        raise ValueError('Preview expired. Review the changes again.')
                    if 'cycle_profiles' in preview and not SETUPS.ready:
                        raise ValueError('Desktop shortcut is unavailable. Reopen the app.')
                    SETUPS.disable()
                    try:
                        result = write_packets(preview['device_id'], preview['packets'])
                    except Exception as exc:
                        SETUPS.disable('Transfer failed; keypad state is unknown. ' + str(exc))
                        raise
                    if 'cycle_profiles' in preview:
                        SETUPS.activate(preview['cycle_profiles'], preview['device_id'])
                self.reply(200, {'result': result})
            elif self.path == '/api/show':
                with WRITE_LOCK:
                    SETUPS.show_request += 1
                    self.reply(200, {'shown': True})
            elif self.path == '/api/quit':
                self.reply(200, {'closed': True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
            else:
                self.reply(404, {'error': 'Not found.'})
        except (ValueError, TypeError, KeyError) as exc:
            self.reply(400, {'error': str(exc)})
        except Exception as exc:
            self.reply(503, {'error': str(exc)})

def main():
    global SETUPS
    parser = argparse.ArgumentParser()
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--settings-dir', type=Path, help='Optional separate directory for saved layouts.')
    args = parser.parse_args()
    if args.settings_dir:
        SETUPS = Setups(validate_profile, args.settings_dir / 'setups.json')
    instance_lock = None
    if sys.platform == 'darwin' and not args.no_browser:
        import fcntl
        import urllib.request
        SETUPS.path.parent.mkdir(parents=True, exist_ok=True)
        instance_lock = (SETUPS.path.parent / 'instance.lock').open('a')
        session_path = SETUPS.path.parent / 'session.json'
        try:
            fcntl.flock(instance_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            # Reopen the existing companion instead of competing for global hotkeys.
            for attempt in range(20):
                try:
                    session = json.loads(session_path.read_text())
                    request = urllib.request.Request(session['base'] + 'api/show', data=b'{}',
                        headers={'Authorization': 'Bearer ' + session['token'], 'Content-Type': 'application/json'})
                    with urllib.request.urlopen(request, timeout=1):
                        return
                except (OSError, ValueError, KeyError):
                    time.sleep(0.1)
            raise RuntimeError('Dialpad is already running but could not reopen its window. Use its menu-bar icon.')
    catalog = json.loads((ROOT / 'ui' / 'starters.json').read_text())
    SETUPS.install_defaults(list(catalog['mac' if sys.platform == 'darwin' else 'windows'].values()))
    if SETUPS.order is None and not SETUPS.load_failed:
        SETUPS.save_order([p['name'] for p in SETUPS.profiles])
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    url = f'http://127.0.0.1:{server.server_port}/#{TOKEN}'
    if instance_lock is not None:
        temporary = session_path.with_suffix('.tmp')
        descriptor = os.open(temporary, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, 'w') as stream:
            json.dump({'base': f'http://127.0.0.1:{server.server_port}/', 'token': TOKEN}, stream)
        temporary.replace(session_path)
    desktop = None
    if args.no_browser:
        print(url, flush=True)
    else:
        native = ROOT / 'DialpadDesktop'
        if sys.platform == 'darwin' and native.exists():
            desktop = subprocess.Popen([str(native)], stdin=subprocess.PIPE, text=True)
            desktop.stdin.write(url + '\n')
            desktop.stdin.close()
            def watch_desktop():
                desktop.wait()
                server.shutdown()
            threading.Thread(target=watch_desktop, daemon=True).start()
        elif sys.platform == 'win32':
            from core.windows_desktop import launch
            threading.Thread(target=launch, args=(url, server.shutdown), daemon=True).start()
        else:
            webbrowser.open(url)
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        if desktop and desktop.poll() is None:
            desktop.terminate()
        server.server_close()
        if instance_lock is not None:
            session_path.unlink(missing_ok=True)
            instance_lock.close()

if __name__ == '__main__':
    main()
