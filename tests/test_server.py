"""Exercise HTTP parsing and handlers in memory; every hardware operation is mocked."""
import copy
import io
import json
import time
import tempfile
from pathlib import Path
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
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        setups_patch = patch.object(app, 'SETUPS', app.Setups(app.validate_profile, Path(temporary.name) / 'setups.json'))
        setups_patch.start()
        self.addCleanup(setups_patch.stop)
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

    def prepare_cycle(self):
        first, second = profile(), profile()
        second['name'] = 'Second setup'
        second['bindings']['key1'] = {'type': 'shortcut', 'key': 'ESCAPE'}
        self.assertEqual(self.request('/api/setups/save', {'profiles': [first, second]})[0], 200)
        self.assertEqual(self.request('/api/desktop-ready', {'ready': True})[0], 200)
        status, preview = self.request('/api/setups/preview', {'device_id': 'mock-device'})
        self.assertEqual(status, 200)
        return preview

    def test_saving_and_preview_do_not_write_or_arm(self):
        preview = self.prepare_cycle()
        self.assertEqual(preview['profiles'][0]['bindings']['dial_press']['key'], 'F18')
        self.assertEqual(app.SETUPS.profiles[0]['bindings']['dial_press']['key'], 'ENTER')
        self.assertFalse(app.SETUPS.enabled)
        self.assertEqual(self.request('/api/setups/cycle', {})[0], 400)
        self.write.assert_not_called()

    def test_cycle_applies_snapshot_debounces_and_wraps(self):
        preview = self.prepare_cycle()
        self.assertEqual(self.request('/api/apply', {'nonce': preview['nonce']})[0], 200)
        app.SETUPS.profiles[1]['bindings']['key1']['key'] = 'TAB'
        self.assertEqual(self.request('/api/setups/cycle', {})[0], 200)
        self.assertEqual(self.write.call_count, 1)  # rapid press ignored
        app.SETUPS.last_switch = 0
        status, state = self.request('/api/setups/cycle', {})
        self.assertEqual(status, 200)
        self.assertEqual(state['current']['bindings']['key1']['key'], 'ESCAPE')
        self.assertEqual(state['active'], 1)
        self.assertEqual(self.write.call_args.args[1], app.profile_packets(state['current']))
        app.SETUPS.last_switch = 0
        self.assertEqual(self.request('/api/setups/cycle', {})[1]['active'], 0)
        self.assertEqual(self.write.call_count, 3)

    def test_cycle_write_failure_disarms_and_never_claims_active_layout(self):
        preview = self.prepare_cycle()
        self.request('/api/apply', {'nonce': preview['nonce']})
        self.write.side_effect = TransportError('partial write', 2)
        app.SETUPS.last_switch = 0
        self.assertEqual(self.request('/api/setups/cycle', {})[0], 503)
        state = self.request('/api/setups')[1]
        self.assertFalse(state['enabled'])
        self.assertIsNone(state['current'])
        self.assertIn('unknown', state['error'])
        self.assertEqual(self.request('/api/setups/cycle', {})[0], 400)
        self.assertEqual(self.write.call_count, 2)

    def test_restart_retains_setups_but_never_rearms(self):
        preview = self.prepare_cycle()
        self.request('/api/apply', {'nonce': preview['nonce']})
        reloaded = app.Setups(app.validate_profile, app.SETUPS.path)
        self.assertEqual(len(reloaded.profiles), 2)
        self.assertFalse(reloaded.enabled)
        self.assertFalse(reloaded.ready)

    def test_stop_and_regular_apply_disarm_cycle(self):
        preview = self.prepare_cycle()
        self.request('/api/apply', {'nonce': preview['nonce']})
        self.assertFalse(self.request('/api/setups/disable', {})[1]['enabled'])
        self.assertEqual(self.write.call_count, 1)
        preview = self.prepare_cycle()
        self.request('/api/apply', {'nonce': preview['nonce']})
        normal = self.preview()
        self.request('/api/apply', {'nonce': normal['nonce']})
        self.assertFalse(app.SETUPS.enabled)

    def test_cycle_requires_desktop_and_consistent_layer(self):
        self.prepare_cycle()
        self.request('/api/desktop-ready', {'ready': False})
        self.assertEqual(self.request('/api/setups/preview', {'device_id': 'mock'})[0], 400)
        self.request('/api/desktop-ready', {'ready': True})
        app.SETUPS.profiles[1]['layer'] = 2
        self.assertEqual(self.request('/api/setups/preview', {'device_id': 'mock'})[0], 400)
        self.write.assert_not_called()

    def test_busy_cycle_does_not_queue_another_transfer(self):
        preview = self.prepare_cycle()
        self.request('/api/apply', {'nonce': preview['nonce']})
        app.SETUPS.last_switch = 0
        with app.WRITE_LOCK:
            self.assertEqual(self.request('/api/setups/cycle', {})[0], 400)
        self.assertEqual(self.write.call_count, 1)


if __name__ == '__main__':
    unittest.main()
