'''
Find the transformations: which piece of the submission stands in place of
which piece of the reference?

Guided by the reference and anchored. The search only looks where the
mapping has already fixed something, and only among the nodes it left open:

    1  The mapping pairs what can be proven (Auto to Auto by name).
    2  The free leftovers of both sides are cut into pieces (-> pieces.py).
       Every piece knows its anchors.
    3  A declaration (-> src/notation/transformations.py) fits if the number
       of anchors and the type count of both pieces match AND the anchors
       correspond: the anchors of the sub piece are exactly the partners of
       the ref anchors.

So the search cannot overturn an existing pair -- it only sees free nodes --
and it runs once, not until a fixed point.

The declaration allows some freedom (-> src/notation/transformations.py):
"anker_sub" lets the sub piece hang on more paired nodes than the ref piece
(the partners of the ref anchors must be among them); "sub_mit" /
"sub_ohne" ask for a value at the nodes of the sub piece, "ref_mit" /
"ref_ohne" the same at the ref piece -- this separates two variants that are
built alike and judge differently; "ref_kanten" / "sub_kanten" ask for a
value at the EDGES of the piece, by the role of the other end
(-> _edges_fit) -- that is how "attribute instead of entity" requires the
replaced relationship to be n:1 to the entity, because with n:m an attribute
would not be equivalent.

One more reads labels, and deliberately so: "bezeichner_gleich" requires
every free attribute of the reference to have a name relative over there
(-> _names_fit). Without this condition "relationship instead of attribute"
could not be told apart from "attribute forgotten and one relationship too
many". That is not a word list but the precondition of the equivalence notion
itself: the attributes of both diagrams have to be identified before
equivalence can be discussed at all.

Unique or not at all, as in the mapping: if two declarations fit the same
piece, or two pieces of the submission fit the same place, no instance is
created. The diff then stays what it would be without a pattern -- many small
ops -- and the follow-up question comes the usual way.

What is NOT decided here: whether the finding is an error. The instance only
carries "allowed" (the course's policy) and "equivalent" (the equivalence
verdict) along; they are read in the catalog
(-> src/report/catalog/classify.py, "verdict") and in the sentence
(-> src/report/templates.py).
'''

from dataclasses import dataclass, field

from src.mapping.labels import label_kind
from src.notation.diagram import (adornment_types, node_label, node_props_raw, node_type, normalized,
                                  references)
from src.notation.transformations import CONDITIONS, EDGE_CONDITIONS, counts

from .pieces import Piece, free_pieces


@dataclass
class Transform:
    '''A transformation found -- one ref piece, one sub piece, one name.'''

    name: str
    variant: str = ""
    anchors: list = field(default_factory=list)      # the paired ref nodes
    ref_nodes: list = field(default_factory=list)
    sub_nodes: list = field(default_factory=list)
    equivalent: str = ""
    allowed: bool = False


def find_transforms(ref, sub, mapping, transforms, notation=None):
    '''
    All unique transformations between reference and submission.

    Without declarations (a notation without a transformation list) an empty
    list comes back and everything stays as it was. "notation" is only
    needed by a declaration with a condition (sub_mit / sub_ohne): with it a
    missing value counts as its default. Without a notation the raw value is
    read.
    '''
    if not transforms:
        return []

    ref_pieces = free_pieces(ref, _open_nodes(ref, set(mapping.pairs)))
    sub_pieces = free_pieces(sub, _open_nodes(sub, mapping.taken))

    hits = []

    for piece in ref_pieces:
        found = _hits_for(piece, sub_pieces, mapping, transforms, ref, sub, notation)

        # Several readings for the same place -- then none.
        if len(found) == 1:
            hits.append(found[0])

    return _without_double_claims(hits)


def _open_nodes(graph, paired):
    '''
    What is open for the search -- and that is more than "without a partner".

    A node without a partner is open, of course. But a paired node whose unit
    hangs in the air is open too: an attribute whose owner has no partner is
    not a specific attribute (-> src/notation/diagram/units.py), even if its
    name happens to show up elsewhere. Such a pair does not work as the
    border of a piece -- it would cut the transformation in the middle.

    Example: the student builds "Mietvorgang" as an entity with the
    attributes of the relationship "mietet". "Mietbeginn" has the same name
    on both sides and is paired; "mietet" itself stays without a partner.
    Without this rule the transformation would fall apart into fragments.
    '''
    open_nodes = []

    for node in graph:
        if node not in paired:
            open_nodes.append(node)
            continue

        targets = [t for found in references(graph, node).values() for t in found]

        if targets and not any(t in paired for t in targets):
            open_nodes.append(node)

    return open_nodes


def _hits_for(piece, sub_pieces, mapping, transforms, ref, sub, notation):
    '''All (declaration, sub piece) pairs that fit this ref piece.'''
    wanted = {mapping.pairs[anchor] for anchor in piece.anchors}
    found = []

    for declaration in transforms:
        if (len(piece.anchors) != declaration["anker"] or not _fits(piece, declaration["ref"])
                or not _conditions_fit(piece, ref, declaration, notation, "ref")
                or not _edges_fit(piece, ref, declaration, notation, "ref", set(piece.anchors))):
            continue

        candidates = list(sub_pieces)

        # "sub_verbund": no single piece fits, but several together -- the
        # pieces between the anchors read as one (-> _joined).
        if declaration.get("sub_verbund"):
            joined = _joined(sub_pieces, wanted)

            if joined is not None:
                candidates.append(joined)

        for other in candidates:
            if (_anchors_fit(other, wanted, declaration)
                    and _fits(other, declaration["sub"])
                    and _conditions_fit(other, sub, declaration, notation, "sub")
                    and _edges_fit(other, sub, declaration, notation, "sub", wanted)
                    and _names_fit(piece, other, wanted, ref, sub, mapping, declaration)):
                found.append((declaration, piece, other))

    return found


def _joined(sub_pieces, wanted):
    '''
    The pieces of the submission that lie between the wanted anchors, as one
    piece -- or None if there are fewer than two or together they do not
    touch all anchors.

    "Between the anchors" means: the piece hangs on at least two of the
    anchors and on no other paired node. That is how a ternary relationship
    falls apart into binary ones: every binary one is a piece of its own,
    because they only touch via paired entities (-> pieces.py), and only all
    of them together stand in place of the one relationship. A piece that
    hangs on only one anchor (a free attribute) does not belong to it.
    '''
    between = [piece for piece in sub_pieces
               if len(set(piece.anchors) & wanted) >= 2 and set(piece.anchors) <= wanted]

    if len(between) < 2 or set().union(*(piece.anchors for piece in between)) != wanted:
        return None

    joined = Piece()

    for piece in between:
        joined.nodes += piece.nodes
        joined.types.update(piece.types)

    joined.nodes.sort(key=str)
    joined.anchors = sorted(wanted, key=str)

    return joined


def _names_fit(piece, other, wanted, ref, sub, mapping, declaration):
    '''
    "bezeichner_gleich": does every free attribute of the reference have a
    name relative over there? Searched among the nodes of the sub piece and,
    where the piece touches extra anchors, among their attributes in the
    reference -- an attribute that leads to the existing entity "Zimmer" is
    named like its key ("Raum-Nr"), not like the relationship.

    Related means: identical, different spelling, synonym or compound -- the
    same verdict every pair gets (-> src/mapping/labels/kind.py).
    '''
    if not declaration.get("bezeichner_gleich"):
        return True

    adornments = adornment_types()
    partner = {s: r for r, s in mapping.pairs.items()}
    candidates = [node_label(sub.nodes[node]) for node in other.nodes]

    for anchor in other.anchors:
        if anchor in wanted or anchor not in partner:
            continue

        candidates += [node_label(ref.nodes[n]) for n in ref.neighbors(partner[anchor])
                       if node_type(ref.nodes[n]) in adornments]

    for node in piece.nodes:
        if node_type(ref.nodes[node]) not in adornments:
            continue

        label = node_label(ref.nodes[node])

        if not any(label_kind(label, candidate) not in ("different", "missing")
                   for candidate in candidates):
            return False

    return True


def _anchors_fit(other, wanted, declaration):
    '''
    Does the sub piece hang at the place the ref anchors mark?

    Without "anker_sub" that means: on exactly their partners. With
    "anker_sub" it may touch further paired nodes beyond that -- as many as
    the count allows.
    '''
    anchors = set(other.anchors)

    if "anker_sub" not in declaration:
        return anchors == wanted

    least, most = counts({"anker": declaration["anker_sub"]})["anker"]

    return (wanted <= anchors and len(anchors) >= least
            and (most is None or len(anchors) <= most))


def _conditions_fit(piece, graph, declaration, notation, side):
    '''
    Does the piece of this side carry the required values -- or not?

    "sub_mit" / "ref_mit": at least one node of the type carries the value.
    "sub_ohne" / "ref_ohne": none does. "side" chooses the fields of the side
    (-> CONDITIONS). A missing value counts as its default with a schema (an
    attribute without "key" has "none"), as not carried without one.
    '''
    for field, must in CONDITIONS[side]:
        for wanted_type, wanted in declaration.get(field, {}).items():
            carries = any(_carries(graph.nodes[node], wanted, notation)
                          for node in piece.nodes
                          if node_type(graph.nodes[node]) == wanted_type)

            if carries != must:
                return False

    return True


def _edges_fit(piece, graph, declaration, notation, side, main_anchors):
    '''
    Does every edge of the piece carry the required value -- by the role of
    its other end?

    "ref_kanten" / "sub_kanten": {role: {property: value}} (-> EDGE_CONDITIONS).
    The edges read are those from a node of the piece to a node with the
    role: "stueck" a node in the piece, "anker" an anchor -- in the
    submission the partner of a ref anchor --, "zusatz" another paired node
    at the piece (only with anker_sub). Compared via the notation, so that n
    and m count as equal; without a notation the raw value. An edge that may
    not carry the value (attribute to entity) does not count; per role at
    least one must count, otherwise the condition would be met vacuously and
    say nothing.
    '''
    condition = declaration.get(EDGE_CONDITIONS[side])

    if not condition:
        return True

    roles = {node: "stueck" for node in piece.nodes}
    roles.update({anchor: "anker" if anchor in main_anchors else "zusatz"
                  for anchor in piece.anchors})

    for role, wanted in condition.items():
        counted = 0

        for node in piece.nodes:
            for _u, other, attrs in graph.edges(node, data=True):
                if roles.get(other) != role:
                    continue

                types = (node_type(graph.nodes[node]), node_type(graph.nodes[other]))
                specs = notation.edge_property_specs(*types) if notation is not None else None

                for name, value in wanted.items():
                    if (name not in attrs) if specs is None else (name not in specs):
                        continue

                    spec = specs.get(name) if specs is not None else None
                    counted += 1

                    if not _same_value(attrs.get(name, getattr(spec, "default", None)), value, notation, spec):
                        return False

        if not counted:
            return False

    return True


def _same_value(actual, wanted, notation, spec):
    '''Equal in the sense of the notation (n = m) -- without a notation equal as raw values.'''
    if notation is None:
        return actual == wanted

    return normalized(actual, notation, spec) == normalized(wanted, notation, spec)


def _carries(attributes, wanted, notation):
    '''Does this node have every required value with one of the allowed values?'''
    props = node_props_raw(attributes, notation) if notation is not None else attributes

    return all(props.get(name) in (value if isinstance(value, list) else [value])
               for name, value in wanted.items())


def _without_double_claims(hits):
    '''
    A node of the submission belongs to at most one transformation. If more
    than one wants it, the assignment is a guess -- then both drop out,
    together with their instances. Counted per node, not per piece: a
    compound (-> _joined) shares its nodes with the pieces it consists of.
    '''
    claimed = {}

    for _declaration, _piece, other in hits:
        for node in other.nodes:
            claimed[node] = claimed.get(node, 0) + 1

    return [_transform(declaration, piece, other)
            for declaration, piece, other in hits
            if all(claimed[node] == 1 for node in other.nodes)]


def _transform(declaration, piece, other):
    '''The declaration and the two pieces as an instance.'''
    return Transform(
        name=declaration["name"],
        variant=declaration.get("variante", ""),
        anchors=list(piece.anchors),
        ref_nodes=list(piece.nodes),
        sub_nodes=list(other.nodes),
        equivalent=declaration.get("aequivalent", ""),
        allowed=bool(declaration.get("allowed", False)),
    )


def _fits(piece, shape):
    '''
    Does the type count of the piece fit the declaration?

    A type that does not occur in the declaration must not occur in the
    piece -- otherwise something would hang on the piece that the
    transformation does not explain.
    '''
    limits = counts(shape)

    for node_type, seen in piece.types.items():
        if node_type not in limits:
            return False

        least, most = limits[node_type]

        if seen < least or (most is not None and seen > most):
            return False

    return all(piece.types.get(node_type, 0) >= least
               for node_type, (least, _most) in limits.items())
