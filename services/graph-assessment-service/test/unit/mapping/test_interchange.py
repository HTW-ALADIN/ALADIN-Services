'''
src/mapping/interchange.py: interchangeable candidates are assigned the same
way, whatever IDs the drawing tool gave them.

The case: several attributes at the same entity, structurally
interchangeable, with equal values, and no name looks like a reference name.
Then every assignment scores the same and the order of the candidates
decides. That order must come from what the student wrote (the label), not
from the IDs the drawing tool handed out -- otherwise renaming the IDs flips
which reference attribute is read as which.

Both paths are covered: up to EXHAUSTIVE_UP_TO candidates every assignment
is tried (_assign), above that greedily (_best_candidate).
'''

import pytest

from src.mapping import Mapping
from src.mapping.groups import Candidates
from src.mapping.interchange import EXHAUSTIVE_UP_TO, resolve
from src.mapping.labels import label_similarity

# No reference name shares a character bigram with a submission name, so the
# name similarity is 0 everywhere and cannot break the tie.
REF_LABELS = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta", "Eta", "Theta"]
SUB_LABELS = ["Uno", "Dos", "Tres", "Cuatro", "Cinco", "Seis", "Nueve", "Ocho"]


def _entity_with_attributes(graph, ids, labels):
    nodes = [{"id": "kunde", "type": "entity", "label": "Kunde"}]
    nodes += [{"id": node, "type": "attribute", "label": label} for node, label in zip(ids, labels)]

    return graph(nodes, [("kunde", node) for node in ids])


def _assignment(graph, notation, count, sub_ids):
    '''Which submission label each reference attribute gets -- {ref id: sub label}.'''
    ref_ids = [f"r{i}" for i in range(count)]
    ref = _entity_with_attributes(graph, ref_ids, REF_LABELS[:count])
    sub = _entity_with_attributes(graph, sub_ids, SUB_LABELS[:count])

    mapping = Mapping(pairs={"kunde": "kunde"}, source={"kunde": "exact"})
    candidates = {r: Candidates(list(sub_ids), "region") for r in ref_ids}

    open_cases = resolve(mapping, candidates, ref, sub, notation)

    assert open_cases == {}
    assert all(mapping.source[r] == "interchangeable" for r in ref_ids)

    return {r: sub.nodes[mapping.pairs[r]]["label"] for r in ref_ids}


@pytest.mark.parametrize("count", [2, EXHAUSTIVE_UP_TO + 1], ids=["exhaustive", "greedy"])
def test_swapped_ids_give_the_same_assignment(graph, notation, count):
    assert all(label_similarity(r, s) == 0
               for r in REF_LABELS[:count] for s in SUB_LABELS[:count])

    ids = [f"s{i}" for i in range(count)]

    assert (_assignment(graph, notation, count, ids)
            == _assignment(graph, notation, count, list(reversed(ids))))
