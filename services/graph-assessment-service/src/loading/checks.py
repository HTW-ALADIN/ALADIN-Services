'''
The single checks for loaded graph data.

Two areas: the data format (structure and field types against the JSON
schema) and the graph structure (unique node IDs, valid endpoints). Every
violation is reported as a GraphInputError.

Which values a property may take is deliberately not checked here: that is
up to the notation, and a value it does not know is a finding, not a
rejection (-> src/loading/validate.py).

A rejected error names the rule it breaks -- just like a notation violation
does (-> src/loading/validate.py, RULES). The name is the one under which
the error catalog lists the class; it does not depend on the notation, so
this module may hand it out without knowing the catalog.

The error texts end up in the feedback (the rejection reason) and stay German.
'''

from jsonschema import Draft202012Validator

#: The file is not a notation file at all: missing, not readable, not text,
#: not valid JSON (gate 1).
WRONG_KIND = "wrong_diagram_kind"

#: It is one, but does not follow the exchange format or the graph structure
#: (gates 2 and 3).
REJECTED = "submission_rejected"

#: The rules under which an input is rejected -- one per way of not being
#: processable. The name is also the class in the error catalog
#: (-> module docstring).
REJECTION_RULES = (WRONG_KIND, REJECTED)


class GraphInputError(ValueError):
    '''
    The input data does not work as a graph.

    "rule" says what caused it -- one of the names from REJECTION_RULES. The
    default holds for gates 2 and 3: the file is readable but does not follow
    the exchange format or the graph structure. Gate 1 sets it explicitly
    (-> src/loading/load.py).

    "gate" says at which of the three it happened -- 1, 2 or 3. The rule
    cannot tell: gates 2 and 3 both reject as a format violation. Whoever
    triggers the check does not know the number (checks.py checks for both),
    so load.py fills it in and the default stays empty.
    '''

    def __init__(self, text, rule=REJECTED, gate=None):
        super().__init__(text)
        self.rule = rule
        self.gate = gate


def check_file_format(data, file_format):
    '''
    Checks the loaded data against the JSON schema.

    Without a schema nothing is checked: a notation does not have to write
    down its file format, and then every file that can be turned into a graph
    is allowed (-> src/notation/files.py).
    '''
    if not file_format:
        return

    error = next(Draft202012Validator(file_format).iter_errors(data), None)

    if error is not None:
        raise GraphInputError(f"{error.json_path}: {error.message}")


def require_dict(value, where):
    '''Checks that an input value is a dict, and returns it.'''
    if not isinstance(value, dict):
        raise GraphInputError(
            f"{where}: muss ein dict sein, ist {type(value).__name__}: {value!r}"
        )

    return value


def require_str_id(entry, where):
    '''Checks that an entry has a non-empty string ID, and returns it.'''
    node_id = entry.get("id")

    if not isinstance(node_id, str) or not node_id.strip():
        raise GraphInputError(
            f"{where}: 'id' muss ein nicht-leerer String sein, ist {node_id!r}"
        )

    return node_id


def reject_dupe_node(g, node_id, where):
    '''Checks whether the node ID is already taken in the graph.'''
    if node_id in g.nodes:
        raise GraphInputError(f"{where}: doppelte id {node_id!r}")


def reject_dupe_edge(g, u, v, where):
    '''
    Checks whether there already is an edge on this node pair.

    Only for notations whose graph class has no parallel edges
    (-> src/notation/notation.py, graph_class): there networkx would silently
    put the second edge on top of the first and mix its values in -- the
    submission would be assessed against a graph it does not contain. So the
    same as for a duplicate node ID: reject.
    '''
    if not g.is_multigraph() and g.has_edge(u, v):
        raise GraphInputError(f"{where}: zweite Kante zwischen {u!r} und {v!r}; "
                              f"diese Notation erlaubt nur eine je Knotenpaar")


def require_known_endpoint(g, endpoint, where):
    '''Checks that the endpoint of an edge points to an existing node.'''
    if endpoint not in g.nodes:
        raise GraphInputError(f"{where}: {endpoint!r} ist kein bekannter Knoten")
