

class Item(object):

    def __init__(self, identifier):
        self.identifier = identifier

    def __str__(self):
        return str(self.identifier)