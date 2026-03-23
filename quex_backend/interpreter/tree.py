class Node:
    def __repr__(self):
        return self.type + ":\n\t" + ("\n".join([str(x) for x in self.children])).replace("\n", "\n\t")

    def __init__(self, type, children):
        self.type = type
        self.children = children
