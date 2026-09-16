"""Exercise message ownership and shutdown without sending real OS input."""
import queue
import threading
import unittest

from core.windows_hotkeys import WindowsHotkeys


class FakeWin32:
    def __init__(self, fail=None):
        self.messages = queue.Queue()
        self.calls = []
        self.fail = fail

    def PeekMessageW(self, *args):
        self.calls.append(('queue', threading.get_ident()))
        return 0

    def GetCurrentThreadId(self):
        return threading.get_ident()

    def RegisterHotKey(self, hwnd, hotkey_id, modifiers, key):
        self.calls.append(('register', threading.get_ident(), hotkey_id))
        return hotkey_id != self.fail

    def UnregisterHotKey(self, hwnd, hotkey_id):
        self.calls.append(('unregister', threading.get_ident(), hotkey_id))
        return 1

    def GetMessageW(self, pointer, *args):
        message, identifier = self.messages.get(timeout=2)
        if message == -1:
            return -1
        pointer._obj.message = message
        pointer._obj.wParam = identifier
        return 0 if message == 0x0012 else 1

    def PostThreadMessageW(self, thread_id, message, wparam, lparam):
        self.messages.put((message, wparam))
        return 1


class WindowsHotkeyTests(unittest.TestCase):
    def make_worker(self, fail=None):
        driver = FakeWin32(fail)
        events = queue.Queue()
        worker = WindowsHotkeys(lambda kind, data: events.put((kind, data)), driver, driver)
        self.addCleanup(worker.stop)
        worker.start()
        return worker, driver, events

    def test_worker_owns_registration_dispatch_and_cleanup(self):
        worker, driver, events = self.make_worker()
        self.assertEqual(events.get(timeout=2), ('ready', {'ready': True}))
        driver.messages.put((0x0312, 8))
        self.assertEqual(events.get(timeout=2), ('hotkey', 8))
        worker.stop()
        self.assertFalse(worker.thread.is_alive())
        owners = {call[1] for call in driver.calls}
        self.assertEqual(owners, {worker.thread_id})
        self.assertNotIn(threading.get_ident(), owners)
        self.assertEqual([c[2] for c in driver.calls if c[0] == 'unregister'], list(range(1, 9)))

    def test_failed_registration_releases_partial_set(self):
        worker, driver, events = self.make_worker(fail=4)
        kind, data = events.get(timeout=2)
        self.assertEqual(kind, 'ready')
        self.assertFalse(data['ready'])
        worker.thread.join(timeout=2)
        self.assertFalse(worker.thread.is_alive())
        self.assertEqual([c[2] for c in driver.calls if c[0] == 'unregister'], [1, 2, 3])

    def test_message_loop_error_reports_not_ready_and_cleans_up(self):
        worker, driver, events = self.make_worker()
        events.get(timeout=2)
        driver.messages.put((-1, 0))
        kind, data = events.get(timeout=2)
        self.assertEqual(kind, 'ready')
        self.assertFalse(data['ready'])
        self.assertIn('message queue', data['error'])
        worker.thread.join(timeout=2)
        self.assertEqual(len([c for c in driver.calls if c[0] == 'unregister']), 8)


if __name__ == '__main__':
    unittest.main()
