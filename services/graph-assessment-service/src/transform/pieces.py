'''
What is left over at the edge of the mapping -- cut into pieces.

A piece is a connected group of nodes that have no partner, plus the paired
nodes they hang on (the "anchors"). Paired nodes are the border: a piece does
not grow across them.

    reference    Auto is paired, IS-A and the two subtypes are free
                 -> one piece {isa, entity, entity} with the anchor Auto
    submission   "Kategorie" is unclaimed
                 -> one piece {attribute} with the anchor Auto

Connected means here: via an edge that a unit fulfils
(-> src/notation/diagram/units.py). An edge that belongs to no unit -- two
entities connected directly, a notation violation -- does not glue two pieces
together; otherwise half the diagram would hang on one broken edge.
'''

from collections import Counter
from dataclasses import dataclass, field

from src.notation.diagram import node_type, unit_neighbours


@dataclass
class Piece:
    '''Free nodes that are connected, and the paired nodes at the edge.'''

    nodes: list = field(default_factory=list)
    anchors: list = field(default_factory=list)
    types: Counter = field(default_factory=Counter)

    def __len__(self):
        return len(self.nodes)


def free_pieces(graph, free):
    '''
    The pieces made of the free nodes of "graph".

    "free" are the nodes without a partner. Nodes without neighbours form a
    piece of their own; a piece without any anchor (nothing around it is
    paired) occurs and is returned too -- whether one with zero anchors is
    allowed is decided by the declaration (-> src/notation/transformations.py:
    "anker").
    '''
    free = set(free)
    neighbours = unit_neighbours(graph)
    seen, pieces = set(), []

    for start in graph.nodes:
        if start not in free or start in seen:
            continue

        piece = Piece()
        stack = [start]
        seen.add(start)
        anchors = set()

        while stack:
            node = stack.pop()
            piece.nodes.append(node)
            piece.types[node_type(graph.nodes[node])] += 1

            for neighbour in neighbours.get(node, ()):
                if neighbour not in free:
                    anchors.add(neighbour)
                elif neighbour not in seen:
                    seen.add(neighbour)
                    stack.append(neighbour)

        piece.nodes.sort(key=str)
        piece.anchors = sorted(anchors, key=str)
        pieces.append(piece)

    return pieces
