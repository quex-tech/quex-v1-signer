class JqIterator:
    def __init__(self, obj: list):
        self.obj = obj

    def __iter__(self):
        return self.obj.__iter__()

    def __eq__(self, other):
        if isinstance(other, JqIterator):
            return self.obj == other.obj
        return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return f"Iterator{self.obj}"
