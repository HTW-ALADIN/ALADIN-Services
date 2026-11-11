'''
Apply an op list to a graph -- the other direction of diff.py.

diff.py writes the ops, here they are applied. The catalog needs the graph
as it would look WITH the ops (-> catalog/classify.py, rank 2). Applying the
whole diff to the submission must give the reference again -- this module is
also the way to check that.

The input graph is not changed.

Not to be confused with apply_ops in src/mapping/labels/normalization/ops:
those are text operations on a label, these are changes to a graph.
'''


def apply_ops(graph, ops):
    '''
    Apply ops in order. Returns (repaired, ineffective).

    "ineffective" are the ops that had no effect -- with reason and position.
    That is not an error of the caller: a removed node takes its edges along,
    a later remove for these edges then has no effect.
    '''
    repaired = graph.copy()
    ineffective = []

    for i, op in enumerate(ops):
        reason = _apply_one(repaired, op)

        if reason:
            ineffective.append(f"#{i} {reason}")

    return repaired, ineffective


def _apply_one(graph, op):
    '''Apply one op. Returns None on success, otherwise the reason in plain words.'''
    kind = op.get("op")
    properties = op.get("properties", {})

    if "endpoints" in op:
        u, v = op["endpoints"]

        if kind == "add":
            if u not in graph or v not in graph:
                return f"add edge {u}--{v}: endpoint missing"

            graph.add_edge(u, v, **properties)
            return None

        if kind == "remove":
            if not graph.has_edge(u, v):
                return f"remove edge {u}--{v}: not present"

            graph.remove_edge(u, v)
            return None

        if kind == "modify":
            if not graph.has_edge(u, v):
                return f"modify edge {u}--{v}: not present"

            _edge_attrs(graph, u, v).update(properties)
            return None

        return f"unknown op {kind!r}"

    node = op.get("id")

    if kind == "add":
        if node in graph:
            return f"add node {node}: already present"

        graph.add_node(node, type=op.get("type"), **properties)
        return None

    if kind == "remove":
        if node not in graph:
            return f"remove node {node}: not present"

        # networkx takes the attached edges along.
        graph.remove_node(node)
        return None

    if kind == "modify":
        if node not in graph:
            return f"modify node {node}: not present"

        graph.nodes[node].update(properties)

        if "type" in op:
            graph.nodes[node]["type"] = op["type"]

        return None

    return f"unknown op {kind!r}"


def _edge_attrs(graph, u, v):
    '''
    The attribute dict of the edge u--v.

    In a MultiGraph the first parallel edge. Which one is meant is not said
    by the op.
    '''
    if graph.is_multigraph():
        return graph[u][v][next(iter(graph[u][v]))]

    return graph[u][v]
