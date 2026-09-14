"""Dialpad local configurator. No device writes occur until preview + Apply."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
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
    for control, action in bindings.items():
        encode_binding(control, action, layer)
    return profile

def make_preview(body):
    from core.protocol import encode_binding
    profile = validate_profile(body.get('profile'))
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
        if self.path == '/api/devices':
            try:
                from core.transport import list_devices
                self.reply(200, {'devices': list_devices(), 'platform': sys.platform})
            except Exception as exc:
                self.reply(503, {'error': str(exc)})
            return
        assets = {'/': ('index.html', 'text/html; charset=utf-8'), '/app.js': ('app.js', 'text/javascript'), '/style.css': ('style.css', 'text/css')}
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
                self.reply(200, make_preview(body))
            elif self.path == '/api/apply':
                from core.transport import write_packets
                with WRITE_LOCK:
                    nonce = body.get('nonce')
                    if not isinstance(nonce, str):
                        raise ValueError('Preview the changes first.')
                    preview = PREVIEWS.pop(nonce, None)
                    if not preview or preview['expires'] < time.monotonic():
                        raise ValueError('Preview expired. Review the changes again.')
                    result = write_packets(preview['device_id'], preview['packets'])
                self.reply(200, {'result': result})
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
    parser = argparse.ArgumentParser()
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--port', type=int, default=0)
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    url = f'http://127.0.0.1:{server.server_port}/#{TOKEN}'
    if args.no_browser:
        print(url, flush=True)
    else:
        webbrowser.open(url)
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == '__main__':
    main()
