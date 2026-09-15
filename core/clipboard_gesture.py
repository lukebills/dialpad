"""Single/double tap decisions, with no keyboard or clipboard access."""
class ClipboardGesture:
    delay = 0.320

    def __init__(self):
        self.reset()

    def reset(self):
        self.copy_next = True
        self.last_action = None
        self.pending = None

    def tap(self, now, reset_seconds=10, double_tap=True):
        if self.pending is not None and now - self.pending <= self.delay:
            self.pending = None
            return 'cut'
        if self.last_action is not None and reset_seconds and now - self.last_action >= reset_seconds:
            self.copy_next = True
        if double_tap:
            self.pending = now
            return None
        return 'copy' if self.copy_next else 'paste'

    def flush(self):
        self.pending = None
        return 'copy' if self.copy_next else 'paste'

    def complete(self, operation, now):
        self.copy_next = operation == 'paste'
        self.last_action = now
