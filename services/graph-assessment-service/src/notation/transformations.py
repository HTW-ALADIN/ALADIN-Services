'''
The transformations per notation -- declared, not derived.

A transformation is a place where the submission builds the same thing
differently from the reference: an attribute instead of an inheritance, an
entity instead of a relationship. The name of the declaration IS the class
in the error catalog (notations/<NOTATION>/<name>.fehlerkatalog.json, field
"id"): the finding brings its name along, the catalog is only looked up. How
to recognize the transformation is not said by the catalog -- that lives
here next to it, as data, so that a second notation can bring its own list
without any code changing:

    notations/<NOTATION>/<name>.umformungen.json   the declaration

The transformations have a file of their own and are not in the notation
file: a diagram with a transformation conforms to the notation -- they say
nothing about what may be drawn, but about when two diagrams build the same
thing differently. The declaration is read by -> src/transform.

The keys are the notation file's own vocabulary and stay as they are.

Every transformation carries two separate verdicts. Mixing them up would be
the most common mistake at this place:

    aequivalent   Is the information preserved? "ja" (yes), "nein" (no) or
                  "n. n." (not provable -- counts as not equivalent).
                  Documentation only.
    allowed       Does the course accept the transformation? That is policy
                  and drives the code: allowed means accept it and only point
                  it out, not allowed means keep it in the diff, but NAMED.

The two can differ: the course can exclude an equivalent transformation
because the task is meant to practise a building block, and accept one that
is not provably equivalent. The default here: what is equivalent is allowed.

How an entry is read ("kind": "piece"):

    At the ANCHOR -- a node the mapping has already paired -- a piece hangs
    on both sides that belongs to nobody: in the reference the nodes without
    a partner, in the submission those nobody claims. A piece is everything
    reachable from there via the references of the units
    (-> src/notation/notation.py) without crossing a paired node.

        anker   how many paired nodes the piece touches (1, 2, 3 ...)
        ref     the nodes of the reference piece, counted by type
        sub     the same count for the piece of the submission

    A count is a number ("exactly this many"), "n+" ("at least n") or "*"
    ("any number, including none"). A type that is not listed must not occur
    in the piece.

    The other fields are optional:

        variante    tells apart two entries of the same name that judge
                    differently (-> below)
        anker_sub   the piece of the submission may touch MORE paired nodes
                    than that of the reference -- a relationship drawn to an
                    existing entity instead of an attribute hangs on two
                    anchors, the attribute only on one. The partners of the
                    reference anchors must be among them; the number is a
                    count as above. Without the field the anchors must
                    correspond exactly.
        sub_mit     a value at a node of the sub piece, e.g.
        sub_ohne    {"attribute": {"key": ["primary", "partial"]}}: at least
                    one attribute in the piece carries a key (sub_mit, "with")
                    or none does (sub_ohne, "without"). This separates two
                    variants that are built alike and judge differently: an
                    intermediate entity with its own key is a different model
                    than one without. Here and with ref_mit/ref_ohne a
                    transformation is the only place that reads a property --
                    it decides the variant, never the pair (-> src/transform/match.py).
        ref_mit     the same question to the piece of the REFERENCE, e.g. for
        ref_ohne    "relationship instead of entity": does the intermediate
                    entity of the reference carry a key of its own (ref_mit:
                    the student's relationship is then poorer, not equivalent)
                    or not (ref_ohne: equivalent)? The mirror of sub_mit/sub_ohne.
        sub_verbund true means: the piece of the submission may consist of
                    SEVERAL pieces lying between the anchors -- each hangs on
                    at least two of the anchors and on no other paired node,
                    together they cover all anchors. Needed for "binary
                    instead of ternary": the binary relationships only touch
                    each other via paired entities and are therefore each a
                    piece of their own (-> src/transform/pieces.py). The
                    compound is counted like one piece.
        ref_kanten  a value at the EDGES of the piece, by the role of the
        sub_kanten  other end: "stueck" (a node in the piece), "anker" (an
                    anchor) or "zusatz" (sub only: an extra anchor from
                    anker_sub). {"stueck": {"cardinality": ["1", ""]},
                    "anker": {"cardinality": ["n", ""]}} means: every edge
                    from a node of the piece to a node in the piece that may
                    carry a cardinality carries 1, and every one to an anchor
                    n; equivalent values (n = m) count as equal, and per role
                    there must be at least one such edge. That way
                    "attribute instead of entity" requires that the replaced
                    relationship is n:1 to the entity: with n:m an object
                    would have several values, and an attribute cannot express
                    that. If the cardinality does not fit, the pattern does
                    not fit, and the place stays missing + extra
                    (-> src/transform/match.py, _edges_fit).
        bezeichner_gleich
                    true means: every free attribute of the reference needs a
                    name relative over there (identical, spelling, synonym,
                    compound) -- among the nodes of the sub piece or the
                    attributes of the extra anchors. This is the precondition
                    for comparing the two schemas (the attributes of both
                    diagrams are identified) and separates "relationship
                    instead of attribute" from "attribute forgotten and one
                    relationship too many".

What "allowed" does is in -> src/report/catalog/classify.py: the finding
stays an instance and claims its ops, but does not count as an error -- no
deduction, no step in the distance, a note in the feedback instead of an
objection. Nothing is rewritten.
'''

from . import files
from .notation import load_notation

#: The key under which the list is in the file. What the file is called is
#: in -> src/notation/files.py and only there.
KEY = "umformungen"

#: The kinds of transformation src/transform knows. Only one today.
KINDS = ("piece",)

#: The allowed values of the equivalence verdict: yes, no, or not provable
#: ("n. n.": counts as not equivalent).
JUDGEMENTS = ("ja", "nein", "n. n.")

#: The fields of an entry. "variante" separates two entries of the same name
#: -- these are variants of the same catalog pattern, and they judge differently.
REQUIRED_KEYS = {"name", "kind", "anker", "ref", "sub", "aequivalent", "allowed"}
OPTIONAL_KEYS = {"variante", "anker_sub", "sub_mit", "sub_ohne", "ref_mit", "ref_ohne", "ref_kanten",
                 "sub_kanten", "bezeichner_gleich", "sub_verbund"}

#: The condition fields per side: (field, must the piece carry the value?).
#: "sub_*" asks the piece of the submission, "ref_*" that of the reference.
CONDITIONS = {"ref": (("ref_mit", True), ("ref_ohne", False)),
              "sub": (("sub_mit", True), ("sub_ohne", False))}

#: The edge condition per side, and which roles the other end of an edge can
#: have there. "zusatz" only exists in the submission (-> anker_sub).
EDGE_CONDITIONS = {"ref": "ref_kanten", "sub": "sub_kanten"}
EDGE_ROLES = {"ref": ("stueck", "anker"), "sub": ("stueck", "anker", "zusatz")}


@files.cached
def load_transforms(name):
    '''
    The transformations of the notation, checked against its node types.

    A notation without a declaration file returns an empty list -- then
    src/transform knows no patterns and the diff stays what it is.
    '''
    data = files.read(name, "transformations", optional=True)
    transforms = data[KEY] if data else []

    if transforms:
        _check(name, transforms)

    return transforms


def counts(shape):
    '''
    A count as a pair (at least, at most) -- at most None means open.
    "*" is (0, None), "2+" is (2, None), 3 is (3, 3).
    '''
    limits = {}

    for node_type, count in shape.items():
        if isinstance(count, int):
            limits[node_type] = (count, count)
        elif count == "*":
            limits[node_type] = (0, None)
        else:
            limits[node_type] = (int(str(count).rstrip("+")), None)

    return limits


def _check(name, transforms):
    '''
    Every field must be there, every node type known to the notation, every
    count readable, every kind built. A typo in the file thus shows up at
    program start.
    '''
    notation = load_notation(name)
    known = set(notation.node_type_names())

    for i, transform in enumerate(transforms):
        where = f"{name}{files.SUFFIXES['transformations']}[{i}]"
        fields = set(transform)

        if not REQUIRED_KEYS <= fields or not fields <= REQUIRED_KEYS | OPTIONAL_KEYS:
            raise ValueError(f"{where}: expected the fields {sorted(REQUIRED_KEYS)} "
                             f"(plus optionally {sorted(OPTIONAL_KEYS)}), "
                             f"found {sorted(fields)}")

        if transform["kind"] not in KINDS:
            raise ValueError(f"{where}: unknown kind {transform['kind']!r}")

        if not isinstance(transform["anker"], int) or transform["anker"] < 1:
            raise ValueError(f"{where}: anker must be a number from 1")

        if transform["aequivalent"] not in JUDGEMENTS:
            raise ValueError(f"{where}: aequivalent must be one of "
                             f"{list(JUDGEMENTS)}, not "
                             f"{transform['aequivalent']!r}")

        if not isinstance(transform["allowed"], bool):
            raise ValueError(f"{where}: allowed must be true or false")

        for side in ("ref", "sub"):
            for node_type, count in transform[side].items():
                if node_type not in known:
                    raise ValueError(f"{where}.{side}: unknown node type {node_type!r}")

                if not _readable(count):
                    raise ValueError(f"{where}.{side}.{node_type}: unreadable count {count!r}")

        if "anker_sub" in transform and not _readable(transform["anker_sub"]):
            raise ValueError(f"{where}: anker_sub is a count like ref and sub, "
                             f"not {transform['anker_sub']!r}")

        for side in CONDITIONS:
            for field, _must in CONDITIONS[side]:
                _check_condition(where, field, transform.get(field, {}), notation)

        for side, field in EDGE_CONDITIONS.items():
            _check_edge_condition(where, field, side, transform.get(field, {}), notation)

        for flag in ("bezeichner_gleich", "sub_verbund"):
            if not isinstance(transform.get(flag, False), bool):
                raise ValueError(f"{where}: {flag} must be true or false")


def _check_condition(where, field, condition, notation):
    '''
    A condition names, per node type, values the notation knows on that
    type -- otherwise it could never apply and nobody would notice.
    '''
    if not isinstance(condition, dict):
        raise ValueError(f"{where}.{field}: expected {{node type: {{property: value}}}}")

    for node_type, wanted in condition.items():
        spec = notation.node_types.get(node_type)

        if spec is None:
            raise ValueError(f"{where}.{field}: unknown node type {node_type!r}")

        if not isinstance(wanted, dict) or not wanted:
            raise ValueError(f"{where}.{field}.{node_type}: expected {{property: value}}")

        for prop in wanted:
            if prop not in spec.properties:
                raise ValueError(f"{where}.{field}.{node_type}: {node_type!r} carries "
                                 f"no property {prop!r}")


def _check_edge_condition(where, field, side, condition, notation):
    '''
    An edge condition names, per role, values the notation knows on edges
    -- otherwise it could never apply and nobody would notice. The role
    "zusatz" only exists in the submission: the reference has no extra
    anchors.
    '''
    if not isinstance(condition, dict):
        raise ValueError(f"{where}.{field}: expected {{role: {{property: value}}}}")

    for role, wanted in condition.items():
        if role not in EDGE_ROLES[side]:
            raise ValueError(f"{where}.{field}: unknown role {role!r}, "
                             f"allowed are {list(EDGE_ROLES[side])}")

        if not isinstance(wanted, dict) or not wanted:
            raise ValueError(f"{where}.{field}.{role}: expected {{property: value}}")

        for prop in wanted:
            if prop not in notation.edge_properties:
                raise ValueError(f"{where}.{field}.{role}: the notation knows no "
                                 f"edge property {prop!r}")


def _readable(count):
    '''A number, "*" or "n+" -- nothing else.'''
    if isinstance(count, int):
        return count >= 0

    return count == "*" or (str(count).endswith("+") and str(count)[:-1].isdigit())
