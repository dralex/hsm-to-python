# The counter of the lint test: a component with one method
import hsmd


class Counter(hsmd.Component):

    def __init__(self, ident, dispatcher, **parameters):
        hsmd.Component.__init__(self, ident, dispatcher, **parameters)
        self.value = 0

    def add(self, amount):
        self.value += amount


hsmd.register('Counter', Counter)
