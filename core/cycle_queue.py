"""UI-thread queue: retain distinct presses, serialize writes, cancel on failure."""

class CycleQueue:
    def __init__(self):
        self.pending = 0
        self.busy = False

    def press(self):
        self.pending += 1

    def start(self):
        if self.busy or not self.pending:
            return False
        self.pending -= 1
        self.busy = True
        return True

    def finish(self, success=True):
        self.busy = False
        if not success:
            self.cancel()

    def cancel(self):
        # An outstanding transfer still owns its slot until its response arrives.
        self.pending = 0
