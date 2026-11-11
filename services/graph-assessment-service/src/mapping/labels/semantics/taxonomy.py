'''Hypernyms/hyponyms -- generic over a ``broader`` graph.'''
from __future__ import annotations

from collections import deque
from typing import Mapping, Optional, Sequence

#: A taxonomy is nothing more than this: term -> more general terms.
BroaderMap = Mapping[str, Sequence[str]]


def _neighbours(broader: BroaderMap, term: str) -> list[str]:
    """The more general terms of a term, sorted stably."""
    return sorted(broader.get(term, ()))


def ancestors(term: str, broader: BroaderMap, *,
              max_depth: Optional[int] = None) -> dict[str, tuple[int, tuple[str, ...]]]:
    '''All reachable hypernyms -> (distance in edges, path).'''
    found: dict[str, tuple[int, tuple[str, ...]]] = {}
    seen = {term}
    queue: deque[tuple[str, tuple[str, ...]]] = deque([(term, (term,))])

    while queue:
        current, path = queue.popleft()
        depth = len(path) - 1
        if max_depth is not None and depth >= max_depth:
            continue
        for uppers in _neighbours(broader, current):
            if uppers in seen:
                continue
            seen.add(uppers)
            new_path = (*path, uppers)
            found[uppers] = (depth + 1, new_path)
            queue.append((uppers, new_path))
    return found


def root_depth(term: str, broader: BroaderMap) -> int:
    '''Depth of a term, 1-based: a root is at 1.'''
    ancestor_map = ancestors(term, broader)
    if not ancestor_map:
        # No hypernyms -- or only a self-loop that the breadth-first search
        # swallowed. Both mean: this is the top.
        return 1

    roots = [depth for uppers, (depth, _) in sorted(ancestor_map.items())
               if not broader.get(uppers)]
    if roots:
        return 1 + min(roots)

    # Pure cycle: no term without a hypernym is reachable. Then the furthest
    # point reached counts -- a large number is much better here than an
    # exception in the middle of a similarity score.
    return 1 + max(depth for depth, _ in ancestor_map.values())


def lowest_common_subsumer(
        a: str, b: str, broader: BroaderMap, *,
        max_depth: Optional[int] = None) -> Optional[tuple[str, int, int]]:
    '''The nearest common hypernym: ``(term, distance to a, distance to b)``.'''
    above_a = {a: (0, (a,)), **ancestors(a, broader, max_depth=max_depth)}
    above_b = {b: (0, (b,)), **ancestors(b, broader, max_depth=max_depth)}

    shared = set(above_a) & set(above_b)
    if not shared:
        return None

    def key(term: str) -> tuple[int, str]:
        return (above_a[term][0] + above_b[term][0], term)

    best = min(sorted(shared), key=key)
    return best, above_a[best][0], above_b[best][0]


def wu_palmer(a: str, b: str, broader: BroaderMap, *,
              max_depth: Optional[int] = None) -> Optional[tuple[float, str, int]]:
    '''Wu-Palmer similarity: ``(value, subsumer, depth of the subsumer)``.'''
    hit = lowest_common_subsumer(a, b, broader, max_depth=max_depth)
    if hit is None:
        return None
    subsumer, d_a, d_b = hit
    depth = root_depth(subsumer, broader)
    denominator = d_a + d_b + 2 * depth
    if denominator == 0:  # only reachable if the depth were 0 -- it is >= 1
        return None
    return (2 * depth) / denominator, subsumer, depth


def directed_path(a: str, b: str, broader: BroaderMap, *,
                  max_depth: Optional[int] = None) -> Optional[tuple[str, ...]]:
    '''
    The ascent from ``a`` to ``b``, if ``b`` is strictly above ``a``.

        Returns the path including both ends, or ``None``.
        ``a == b`` returns ``None`` and not the single-element path.
    '''
    if a == b:
        return None
    hit = ancestors(a, broader, max_depth=max_depth).get(b)
    return None if hit is None else hit[1]
