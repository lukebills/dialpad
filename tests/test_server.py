"""Exercise HTTP parsing and handlers in memory; every hardware operation is mocked."""
import copy
import io
import json
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import app
from core.transport import TransportError


def profile():
    return {'version': 1, 'name': 'Server test', 'layer': 1,
            'bindings': {control: {'type': 'shortcut', 'key': 'ENTER'}
                         for control in app.CONTROLS}}


class ServerTests(unittest.TestCase):
    def setUp(self):
        app.PREVIEWS.clear()
        self.write_patch = patch('core.transport.write_packets')
        self.write = self.write_patch.start()
        self.write.return_value = {'packets_written': 5, 'verified': False,
                                   'message': 'Transfer completed; test physical controls.'}
        self.devices_patch = patch('core.transport.list_devices', return_value=[])
        self.devices = self.devices_patch.start()
        self.addCleanup(self.write_patch.stop)
        self.addCleanup(self.devices_patch.stop)

    def request(self, path, body=None, headers=None, raw=None):
        request_headers = {'Host': '127.0.0.1:12345',
                           'Authorization': 'Bearer ' + app.TOKEN,
                           'Content-Type': 'application/json'}
        request_headers.update(headers or {})
        method = 'POST' if body is not None or raw is not None else 'GET'
        payload = raw if raw is not None else json.dumps(body) if body is not None else ''
        request_headers['Content-Length'] = str(len(payload.encode()))
        request = (f'{method} {path} HTTP/1.0\r\n' +
                   ''.join(f'{key}: {value}\r\n' for key, value in request_headers.items()) +
                   '\r\n' + payload).encode()
        incoming, outgoing = io.BytesIO(request), io.BytesIO()
        socket = SimpleNamespace(makefile=lambda *args: incoming,
                                 sendall=outgoing.write, settimeout=lambda value: None)
        app.Handler(socket, ('127.0.0.1', 55555), SimpleNamespace(server_port=12345))
        response_headers, response_body = outgoing.getvalue().split(b'\r\n\r\n', 1)
        return int(response_headers.split(b' ')[1]), json.loads(response_body)

    def preview(self):
        status, response = self.request('/api/preview', {'profile': profile(),
                                      'controls': ['key1'], 'device_id': 'mock-device'})
        self.assertEqual(status, 200)
        return response

    def test_discovery_never_programs(self):
        self.assertEqual(self.request('/api/devices')[0], 200)
        self.devices.assert_called_once()
        self.write.assert_not_called()

    def test_host_origin_token_gates(self):
        for headers, expected in [({'Host': 'attacker.example'}, 403),
                                  ({'Origin': 'https://attacker.example'}, 403),
                                  ({'Origin': 'null'}, 403),
                                  ({'Authorization': ''}, 401),
                                  ({'Authorization': 'Bearer wrong'}, 401)]:
            with self.subTest(headers=headers):
                self.assertEqual(self.request('/api/apply', {'nonce': 'bogus'}, headers)[0], expected)
        self.write.assert_not_called()

    def test_invalid_unselected_binding_rejected_before_preview(self):
        invalid = profile()
        invalid['bindings']['key6']['key'] = 'NOT_A_KEY'
        status, _ = self.request('/api/preview', {'profile': invalid,
                              'controls': ['key1'], 'device_id': 'mock-device'})
        self.assertEqual(status, 400)
        self.assertFalse(app.PREVIEWS)
        self.write.assert_not_called()

    def test_bad_json_and_shape(self):
        for raw in ('{bad', '[]', 'null', ''):
            with self.subTest(raw=raw):
                self.assertEqual(self.request('/api/preview', raw=raw)[0], 400)
        self.write.assert_not_called()

    def test_invalid_controls_never_program(self):
        for controls in ([], ['key1', 'key1'], ['unknown'], [['key1']], 'key1'):
            with self.subTest(controls=controls):
                self.assertEqual(self.request('/api/preview', {'profile': profile(),
                    'controls': controls, 'device_id': 'mock-device'})[0], 400)
        self.write.assert_not_called()

    def test_preview_snapshots_packets_and_apply_is_one_shot(self):
        preview = self.preview()
        self.write.assert_not_called()
        self.assertEqual(preview['packet_count'], 5)
        stored_packets = copy.deepcopy(app.PREVIEWS[preview['nonce']]['packets'])
        status, response = self.request('/api/apply', {'nonce': preview['nonce'],
                                       'device_id': 'different-device', 'profile': {}})
        self.assertEqual(status, 200)
        self.assertFalse(response['result']['verified'])
        self.write.assert_called_once_with('mock-device', stored_packets)
        self.assertEqual(stored_packets[0], bytes(64))
        self.assertEqual(self.request('/api/apply', {'nonce': preview['nonce']})[0], 400)
        self.assertEqual(self.write.call_count, 1)

    def test_expired_preview_cannot_write(self):
        preview = self.preview()
        app.PREVIEWS[preview['nonce']]['expires'] = time.monotonic() - 1
        self.assertEqual(self.request('/api/apply', {'nonce': preview['nonce']})[0], 400)
        self.write.assert_not_called()

    def test_partial_write_error_not_retried_or_reported_as_success(self):
        preview = self.preview()
        self.write.side_effect = TransportError('Hardware state may be partial; no automatic retry.', 2)
        status, response = self.request('/api/apply', {'nonce': preview['nonce']})
        self.assertEqual(status, 503)
        self.assertIn('partial', response['error'])
        self.assertNotIn('result', response)
        self.assertEqual(self.request('/api/apply', {'nonce': preview['nonce']})[0], 400)
        self.assertEqual(self.write.call_count, 1)


if __name__ == '__main__':
    unittest.main()
