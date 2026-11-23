'''
Shared fixtures for all tests.

The layout has three levels:

    unit/          one module on its own; the folders mirror src/
    integration/   several modules together, e.g. a notation file with
                   src/transform/match.py
    system/        the whole run (src/start.py): every set under
                   data/synthetic/ against its expected.json

Run from the service folder:

    pytest                  everything
    pytest test/unit        only one level
'''

import pytest

from src import config
from src.loading.convert import nx_from_dict
from src.notation import load_notation


@pytest.fixture(scope="session")
def notation():
    '''The notation a run uses (config.NOTATION), loaded once.'''
    return load_notation(config.NOTATION)


@pytest.fixture
def graph(notation):
    '''
    A small graph from nodes and edges, built the way the loader builds it.

        graph(nodes=[{"id": "k", "type": "entity", "label": "Kunde"}, ...],
              edges=[("k", "k_nr"), ("k", "r", {"cardinality": ["1", ""]})])

    An edge is (u, v) or (u, v, properties).
    '''
    def build(nodes, edges=()):
        data = {
            "schema": f"{config.NOTATION}.v1",
            "graph": {},
            "nodes": [dict(node) for node in nodes],
            "edges": [_edge(*edge) for edge in edges],
        }
        return nx_from_dict(data, notation)

    return build


def _edge(u, v, properties=None):
    edge = {"endpoints": [{"id": u}, {"id": v}]}

    if properties:
        edge["properties"] = dict(properties)

    return edge
