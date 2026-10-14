# The battery of the vacuum cleaner: a component of the diagram
import hsmd


class Battery(hsmd.Component):
    """The charge level; the signal LOW is raised once when the level
    passes under the threshold of the declaration."""

    def __init__(self, ident, dispatcher, **parameters):
        hsmd.Component.__init__(self, ident, dispatcher, **parameters)
        self.threshold = int(parameters.get('threshold', 20))
        self.level = 100
        self.warned = False

    def drain(self, amount):
        self.level = max(0, self.level - amount)
        if self.level < self.threshold and not self.warned:
            self.warned = True
            self.signal('LOW', level=self.level)

    def charge(self, amount):
        self.level = min(100, self.level + amount)
        if self.level >= self.threshold:
            self.warned = False


hsmd.register('Battery', Battery)
