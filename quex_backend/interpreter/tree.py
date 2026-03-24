from typing import Any


class Node:
    def __repr__(self) -> str:
        return self.type + ":\n\t" + \
            ("\n".join([str(x) for x in self.children])).replace("\n", "\n\t")

    def __init__(self, type: str, children: list[Any]) -> None:
        self.type = type
        self.children = children
