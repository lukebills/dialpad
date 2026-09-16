"""Per-button tap grouping with an inactivity window; no system I/O."""


class MultiTapGesture:
    def __init__(self):
        self.reset()

    def reset(self):
        self.count = 0
        self.last_tap = None

    def tap(self, now, window_ms=350):
        """Return completed groups; a late tap ends the old group and starts a new one."""
        completed = []
        if self.last_tap is not None and now - self.last_tap > window_ms / 1000:
            completed.append(self.flush())
        self.count += 1
        self.last_tap = now
        if self.count == 3:
            completed.append(self.flush())
        return completed

    def flush(self):
        name = {1: 'single', 2: 'double', 3: 'triple'}.get(self.count)
        self.reset()
        return name
