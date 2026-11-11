'''
The units of a notation, held against a diagram.

A unit is an anchor node plus the references without which it is not
determined: an attribute without its owner is not a specific attribute, a
relationship without its participants not a specific relationship. An entity
stands on its own. So it is the minimum context a node takes its identity from.

The units are declared in the notation file (block "units") and checked
there at load time (-> src/notation/notation.py). Here they are only
interpreted and applied to a diagram.

The class Units is built ONCE and then asked -- below it is NOTATION_UNITS
for the notation config.NOTATION names, and on top of it the shortcuts the
rest of the program works with. Whoever wants to check a different notation
builds their own Units(...) and asks that one; that is why no function here
takes a units argument.

Asked by the piece search (-> src/mapping): the skeleton says what is paired
first, owner_of and adornment_types attach the attributes to the partners of
their owners.
'''

from dataclasses import dataclass, field

from src import config

from ..notation import load_notation
from .properties import node_type

#: Why an edge belongs to no unit -- the label in the result.
NO_REFERENCE = "fulfils no reference"
TWO_CLAIMS = "both ends claim it"


@dataclass
class Unit:
    '''An anchor with its reference targets and the edges to them.'''

    anchor: object
    anchor_type: str
    targets: dict = field(default_factory=dict)  # role -> [nodes]
    edges: list = field(default_factory=list)    # [(u, v, key)]

    @property
    def neighbours(self):
        '''All reference targets, roles thrown together.'''
        return [n for targets in self.targets.values() for n in targets]


@dataclass
class Decomposition:
    '''All units of a graph -- and what fit into none.'''

    units: dict = field(default_factory=dict)      # anchor -> Unit
    unclaimed: list = field(default_factory=list)  # [(u, v, key, reason)]

    def __getitem__(self, node):
        return self.units[node]

    def __len__(self):
        return len(self.units)

    def __iter__(self):
        return iter(self.units.values())


class Units:
    '''
    The units of a notation, and what one does with them on a diagram.

    Built from the declaration (the block "units" of the notation file),
    which was already checked at load time. An empty declaration means: the
    notation knows no references, every node stands on its own -- then
    references() returns an empty dict everywhere and claims() False everywhere.
    '''

    def __init__(self, declared):
        self.declared = list(declared)

        #: The units, looked up by their anchor type.
        self.by_anchor = {unit["anchor"]: unit for unit in self.declared}

        #: The anchor types that carry "adornment": true (ERD: the attributes)
        #: -- types that hang on their owner and carry no skeleton.
        self.adornments = {unit["anchor"] for unit in self.declared if unit.get("adornment")}

        #: In which order the anchors become determinable -- the declaration
        #: order of the notation file: whoever has no references comes first.
        self.anchor_order = [unit["anchor"] for unit in self.declared]

    # -- what the identity consists of ------------------------------------

    def adornment_types(self):
        '''The anchor types that are an adornment (ERD: the attributes).'''
        return self.adornments

    def references(self, graph, node):
        '''
        The references of a node: {role: [neighbours]}.

        A node without a unit returns an empty dict. The direct neighbours
        with the target type of the role are counted.
        '''
        unit = self.by_anchor.get(node_type(graph.nodes[node]))

        if unit is None:
            return {}

        found = {}

        for reference in unit["references"]:
            targets = set(reference["target"])
            direct = [n for n in graph.neighbors(node) if node_type(graph.nodes[n]) in targets]
            found[reference["role"]] = list(dict.fromkeys(direct))

        return found

    def owner_of(self, graph, node):
        '''
        The owner of an adornment -- or None if it is not exactly one.

        The graph is undirected, and an adornment may carry adornments itself
        (composite attribute): its neighbours then include the owner AND the
        children. The owner is the neighbour that is not an adornment; if
        there is none, the node is a leaf on a composite, and its only
        neighbour is the owner. Two owners are a notation violation -- then none.
        '''
        candidates = [target for targets in self.references(graph, node).values()
                      for target in targets]
        solid = [n for n in candidates if node_type(graph.nodes[n]) not in self.adornments]

        if len(solid) == 1:
            return solid[0]

        if not solid and len(candidates) == 1:
            return candidates[0]

        return None

    def claims(self, anchor_type, target_type):
        '''
        Does an edge anchor_type--target_type fulfil a reference of the anchor?

        By types and not by nodes: the question depends on the notation alone.
        '''
        unit = self.by_anchor.get(anchor_type)

        if unit is None:
            return False

        return any(target_type in reference["target"] for reference in unit["references"])

    def claims_exclusively(self, type_a, type_b):
        """
        Which end of an edge fulfils a reference -- and only that one?

        Returns "a", "b" or None. None means: both ends fulfil a reference or
        neither does; then the notation does not say whom the edge belongs to,
        and whoever needs it has to decide otherwise.

        The question is asked three times in the report, each time with a
        different way out: -> src/report/catalog/classify.py (_edge_owner then
        takes the first end, _claiming_end gives up) and
        src/report/sentences.py (_anchor_of then asks which end has an op of
        its own).
        """
        a_claims, b_claims = self.claims(type_a, type_b), self.claims(type_b, type_a)

        if a_claims == b_claims:
            return None

        return "a" if a_claims else "b"

    # -- decompose a diagram ----------------------------------------------

    def decompose(self, graph):
        '''
        Split a graph into its units.

        Two invariants carry the decomposition: every node is the anchor of
        exactly one unit, every edge belongs to at most one. Edge ownership is
        set nowhere, it follows from the references -- an edge belongs to the
        unit whose reference it fulfils.

        Every node becomes the anchor of a unit, even an untyped or unknown
        one -- that one then simply has no reference targets. Edges that fulfil
        no reference (entity--entity, a notation violation) or that both ends
        claim (attribute--attribute, undecidable without direction) are not
        assigned but listed in "unclaimed" -- with a reason. Assigned, they
        would invent a role; left out, they would show up nowhere.
        '''
        decomposition = Decomposition()

        for node in graph.nodes:
            decomposition.units[node] = Unit(
                anchor=node,
                anchor_type=node_type(graph.nodes[node]),
                targets=self.references(graph, node),
            )

        # Go through parallel edges one by one: a reflexive relationship hangs
        # on the same node pair twice, and each of the two belongs to a unit
        # on its own. Without a multi class there is no key -- then None, so
        # the units have the same shape everywhere (-> subgraph below).
        if graph.is_multigraph():
            edges = graph.edges(keys=True)
        else:
            edges = ((u, v, None) for u, v in graph.edges())

        for u, v, key in edges:
            claimants = self._claimants(graph, u, v)

            if len(claimants) == 1:
                decomposition.units[claimants[0]].edges.append((u, v, key))
            else:
                reason = TWO_CLAIMS if claimants else NO_REFERENCE
                decomposition.unclaimed.append((u, v, key, reason))

        return decomposition

    def skeleton(self, graph):
        '''
        The graph without its adornments -- the skeleton.

        A copy without all nodes whose type carries "adornment": true in the
        declaration, together with their edges (ERD: the attributes). Asked by
        -> src/mapping/build.py.
        '''
        return graph.subgraph(
            [n for n in graph if node_type(graph.nodes[n]) not in self.adornments]).copy()

    def unit_neighbours(self, graph):
        '''
        Who hangs on whom -- but only via edges a unit fulfils.

        Read from the decomposition above: every edge assigned to a unit
        connects; whatever is in "unclaimed" does not. An edge between two
        entities (a notation violation) thus glues nothing together --
        otherwise half the diagram would hang on one broken edge.

        Asked by -> src/transform/pieces.py and -> src/mapping.
        '''
        found = {}

        for unit in self.decompose(graph):
            for u, v, _key in unit.edges:
                found.setdefault(u, set()).add(v)
                found.setdefault(v, set()).add(u)

        return found

    def _claimants(self, graph, u, v):
        '''
        Which ends of the edge claim it? -- 0, 1 or 2 nodes.

        Only with exactly one claim is it assigned; zero and two both end up
        in "unclaimed".
        '''
        type_u = node_type(graph.nodes[u])
        type_v = node_type(graph.nodes[v])

        claimants = []

        if self.claims(type_u, type_v):
            claimants.append(u)

        # A loop has only one end. Without this check the same node would be
        # in the list twice and the edge would be "contested" with itself.
        if v != u and self.claims(type_v, type_u):
            claimants.append(v)

        return claimants


def subgraph(graph, unit):
    '''
    A unit as a graph of its own -- anchor, targets and the edges in between.

    key is None if the notation does not choose a multi class (-> decompose
    above): then there is only one edge per node pair, and it is created
    without key.
    '''
    part = graph.__class__()
    part.add_node(unit.anchor, **graph.nodes[unit.anchor])

    for neighbour in unit.neighbours:
        part.add_node(neighbour, **graph.nodes[neighbour])

    for u, v, key in unit.edges:
        if key is None:
            part.add_edge(u, v, **graph.edges[u, v])
        else:
            part.add_edge(u, v, key=key, **graph.edges[u, v, key])

    return part


#: The units of the current notation -- built once at import, just as
#: start.py loads the schema once. This is the one place where the notation
#: comes in here.
NOTATION_UNITS = Units(load_notation(config.NOTATION).units)

# The shortcuts on it: so the rest of the program writes
# references(graph, node) and not NOTATION_UNITS.references(graph, node).
adornment_types = NOTATION_UNITS.adornment_types
claims = NOTATION_UNITS.claims
claims_exclusively = NOTATION_UNITS.claims_exclusively
decompose = NOTATION_UNITS.decompose
owner_of = NOTATION_UNITS.owner_of
references = NOTATION_UNITS.references
skeleton = NOTATION_UNITS.skeleton
unit_neighbours = NOTATION_UNITS.unit_neighbours
