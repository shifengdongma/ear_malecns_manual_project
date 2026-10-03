from __future__ import annotations

import networkx as nx
import numpy as np


def degree_preserving_rewire(g: nx.DiGraph, nswap_factor: int = 5, seed: int = 42) -> nx.DiGraph:
    """Create a topology control.

    NetworkX's directed_edge_swap availability differs by version, so we use a
    conservative custom endpoint swap that rejects self-loops/duplicate edges.
    Edge weights are then carried over in random order; record the seed.
    """
    rng = np.random.default_rng(seed)
    h = nx.DiGraph()
    h.add_nodes_from(g.nodes(data=True))
    edges = list(g.edges(data=True))
    pairs = [(u, v) for u, v, _ in edges]
    target_swaps = max(1, nswap_factor * len(pairs))
    attempts = 0
    swaps = 0
    edge_set = set(pairs)
    while len(pairs) >= 2 and swaps < target_swaps and attempts < target_swaps * 50:
        attempts += 1
        i, j = rng.choice(len(pairs), size=2, replace=False)
        a, b = pairs[i]
        c, d = pairs[j]
        if len({a, b, c, d}) < 4:
            continue
        x, y = (a, d), (c, b)
        if x[0] == x[1] or y[0] == y[1] or x in edge_set or y in edge_set:
            continue
        edge_set.remove((a, b)); edge_set.remove((c, d))
        edge_set.add(x); edge_set.add(y)
        pairs[i] = x; pairs[j] = y
        swaps += 1
    attrs = [data.copy() for _, _, data in edges]
    rng.shuffle(attrs)
    for (u, v), data in zip(pairs, attrs):
        h.add_edge(u, v, **data)
    h.graph.update(successful_swaps=swaps, attempted_swaps=attempts, requested_swaps=target_swaps)
    return h
