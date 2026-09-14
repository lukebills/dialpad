import unittest
from unittest.mock import patch

from core import transport


class TransportTests(unittest.TestCase):
    def test_keyboard_interfaces_never_marked_programmable(self):
        for size in (0, 2, 65):
            self.assertFalse(transport._description('x', usage_page=1,
                                                   output_report_bytes=size)['programmable'])

    def test_invalid_packets_do_not_initialize_backend(self):
        with patch.object(transport, '_backend') as backend:
            for packets in ([], [bytes(63)], [bytes(64)], [bytearray(64)], ['x']):
                with self.assertRaises(transport.TransportError):
                    transport.write_packets('x', packets)
            backend.assert_not_called()

    def test_concurrent_writes_rejected_before_backend(self):
        with transport._write_lock, patch.object(transport, '_backend') as backend:
            with self.assertRaisesRegex(transport.TransportError, 'already running'):
                transport.write_packets('x', [bytes([3]) + bytes(63)])
            backend.assert_not_called()

    def test_partial_failure_releases_lock_and_preserves_count(self):
        with patch.object(transport, '_backend') as backend:
            backend.return_value.send.side_effect = transport.TransportError('failed', 2)
            with self.assertRaises(transport.TransportError) as error:
                transport.write_packets('x', [bytes([3]) + bytes(63)])
            self.assertEqual(error.exception.packets_written, 2)
            self.assertFalse(transport._write_lock.locked())

    def test_success_is_not_claimed_verified(self):
        with patch.object(transport, '_backend') as backend:
            backend.return_value.send.return_value = 1
            result = transport.write_packets('x', [bytes([3]) + bytes(63)])
            self.assertEqual(result['packets_written'], 1)
            self.assertFalse(result['verified'])

    def test_raw_usb_keeps_initialization_once_at_start(self):
        with patch.object(transport.sys, 'platform', 'darwin'), patch.object(transport, '_USB') as usb:
            usb.return_value.send.return_value = 2
            reports = [bytes(64), bytes([3]) + bytes(63)]
            self.assertEqual(transport.write_packets('usb:1:9:1', reports)['packets_written'], 2)
            with self.assertRaises(transport.TransportError):
                transport.write_packets('usb:1:9:1', list(reversed(reports)))
            usb.return_value.send.assert_called_once_with('usb:1:9:1', reports)

    def test_native_hid_drops_raw_initialization_without_probing(self):
        packet = bytes([3]) + bytes(63)
        with patch.object(transport, '_backend') as backend:
            backend.return_value.send.return_value = 1
            result = transport.write_packets('win:test', [bytes(64), packet])
            backend.return_value.send.assert_called_once_with('win:test', [packet])
            self.assertEqual(result['packets_written'], 1)


if __name__ == '__main__':
    unittest.main()
