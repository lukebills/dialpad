"""Cross-platform instance ownership; Windows locking is mocked on Mac."""
import errno
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock, patch

import app


class SingleInstanceTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / 'instance.lock'

    def test_windows_locks_first_byte_and_returns_live_handle(self):
        locker = Mock()
        module = SimpleNamespace(locking=locker, LK_NBLCK=2)
        with patch.object(sys, 'platform', 'win32'), patch.dict(sys.modules, msvcrt=module):
            handle = app.acquire_instance_lock(self.path)
        self.addCleanup(handle.close)
        locker.assert_called_once_with(handle.fileno(), 2, 1)
        self.assertEqual(handle.tell(), 0)
        self.assertEqual(self.path.read_bytes(), b'\0')

    def test_windows_busy_lock_closes_handle_and_returns_none(self):
        descriptors = []
        def busy(fd, mode, size):
            descriptors.append(fd)
            raise OSError(errno.EACCES, 'held by existing instance')
        module = SimpleNamespace(locking=busy, LK_NBLCK=2)
        with patch.object(sys, 'platform', 'win32'), patch.dict(sys.modules, msvcrt=module):
            self.assertIsNone(app.acquire_instance_lock(self.path))
        with self.assertRaises(OSError):
            os.fstat(descriptors[0])

    @unittest.skipIf(sys.platform == 'win32', 'POSIX flock behavior')
    def test_posix_lock_releases_on_close(self):
        first = app.acquire_instance_lock(self.path)
        self.assertIsNotNone(first)
        try:
            self.assertIsNone(app.acquire_instance_lock(self.path))
        finally:
            first.close()
        second = app.acquire_instance_lock(self.path)
        self.assertIsNotNone(second)
        second.close()

    def test_reopen_existing_session_posts_only_show(self):
        session = self.path.with_name('session.json')
        session.write_text(json.dumps({'base': 'http://127.0.0.1:12345/', 'token': 'test-only'}), encoding='utf-8')
        with patch('urllib.request.urlopen', return_value=MagicMock()) as urlopen:
            app.reopen_existing_instance(session)
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, 'http://127.0.0.1:12345/api/show')
        self.assertEqual(request.data, b'{}')
        self.assertEqual(request.get_header('Authorization'), 'Bearer test-only')
