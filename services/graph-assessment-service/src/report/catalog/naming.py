'''
What a finding of the diff is called.

Every other step names its own finding: the notation check names its rule
("edge_not_allowed"), the transformation search its declaration
("attribute_for_isa"), the label comparison its verdict. Only the ops of the
diff (src/report/diff.py) arrive without a name -- an op is not one. Here they
get one, computed rather than looked up: everything the name needs is
already in the op.

    {"op": "modify", "id": "customer_name", "properties": {"key": "primary"}}
    and the submission carries key="none", the notation's default
    ->  key_missing_primary

The name is as specific as the facts allow -- plus, level by level, the
coarser readings of the same finding:

    key_missing_primary  ->  key_missing  ->  key_changed

Which level applies is decided by the catalog, by listing it or not
(-> instances.py, entry_for_facts): the catalog separates "primary key not
marked" from "partial key not marked", so the fine level is listed there. It
does not separate one ternary relationship too many from an ordinary one, so
"ternary_relationship_extra" falls back to "relationship_extra". No catalog
entry has to say anything about ops for that, and no line of code has to know
which distinctions a course makes.

The three kinds of a changed property follow from the default the notation
declares for it (notations/<NOTATION>/<name>.notation.json):

    missing   the submission leaves the property at the default, the reference does not
    extra     the submission sets it, the reference leaves it at the default
    wrong     both set it, to different values

This does not depend on the notation: the notation says which value is the
default, and the catalog says whether the three kinds are told apart at all.
'''

#: How an ordered property deviates (-> classify.py, _ordered_bundles):
#: the rank of the values says it, not their content.
DIRECTIONS = {"narrower": "too_narrow", "looser": "too_loose", "mixed": "swapped"}


def finding_names(facts):
    '''
    The names of a finding, from most specific to most general -- the
    catalog takes the first one it lists. An empty list means: nothing to say.
    '''
    if facts.get("target") == "edge":
        return _edge_names(facts)

    return _node_names(facts)


def _node_names(facts):
    kind, type_name = facts.get("op"), facts.get("type")

    if kind in ("add", "remove"):
        # "add" means: the reference has it, the submission does not.
        suffix = "missing" if kind == "add" else "extra"
        name = f"{type_name}_{suffix}"
        form = facts.get("form")

        return [f"{form}_{name}", name] if form else [name]

    if facts.get("property") == "type":
        return ["type_changed"]

    return _property_names(facts)


def _edge_names(facts):
    kind = facts.get("op")

    if kind in ("add", "remove"):
        return ["edge_missing" if kind == "add" else "edge_extra"]

    return _property_names(facts)


def _property_names(facts):
    '''
    The levels of a changed property: kind and value, only the kind, only the
    property. An ordered property (the cardinality) carries its direction
    instead of the kind -- the bundle has already worked that out.
    '''
    prop = facts.get("property")

    if prop is None:
        return []

    if facts.get("missing"):
        return [f"{prop}_missing", f"{prop}_changed"]

    if "direction" in facts:
        direction = DIRECTIONS.get(facts["direction"], facts["direction"])
        return [f"{prop}_{direction}", f"{prop}_changed"]

    if "expected" not in facts:
        return [f"{prop}_changed"]

    default = facts.get("default")
    expected, actual = facts["expected"], facts.get("actual")

    if actual == default and expected != default:
        suffix, value = "missing", expected
    elif expected == default and actual != default:
        suffix, value = "extra", actual
    else:
        suffix, value = "wrong", actual

    return [f"{prop}_{suffix}_{value}", f"{prop}_{suffix}", f"{prop}_changed"]
