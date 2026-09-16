import unittest
from core.cycle_queue import CycleQueue

class CycleQueueTests(unittest.TestCase):
    def test_burst_during_slow_transfer_is_retained_and_serialized(self):
        queue = CycleQueue()
        queue.press()
        self.assertTrue(queue.start())
        for _ in range(10):
            queue.press()
            self.assertFalse(queue.start())
        for _ in range(10):
            queue.finish()
            self.assertTrue(queue.start())
        queue.finish()
        self.assertFalse(queue.start())

    def test_failure_or_disable_discards_waiting_presses(self):
        for failure in (True, False):
            queue = CycleQueue()
            queue.press()
            self.assertTrue(queue.start())
            queue.press()
            if failure:
                queue.finish(success=False)
            else:
                queue.cancel()
                self.assertTrue(queue.busy)
                queue.finish()
            self.assertFalse(queue.start())
            queue.press()
            self.assertTrue(queue.start())
