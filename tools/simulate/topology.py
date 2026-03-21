from __future__ import annotations
import random


def full_mesh(nodes: list) -> list[tuple]:
    """Connect every node to every other node. N*(N-1)/2 pairs."""
    pairs = []
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            pairs.append((nodes[i], nodes[j]))
    return pairs


def sparse_random(nodes: list, k: int) -> list[tuple]:
    """Each node gets k random peers. No node is isolated.
    Returns deduplicated (a, b) pairs where a.index < b.index."""
    if len(nodes) < 2:
        return []
    n = len(nodes)
    k = min(k, n - 1)
    pair_set: set[tuple[int, int]] = set()

    for node in nodes:
        others = [o for o in nodes if o is not node]
        random.shuffle(others)
        chosen = others[:k]
        for peer in chosen:
            key = (min(node.index, peer.index), max(node.index, peer.index))
            pair_set.add(key)

    # Guarantee no isolated nodes: ensure every node appears in at least one pair
    involved = set()
    for a_idx, b_idx in pair_set:
        involved.add(a_idx)
        involved.add(b_idx)

    index_map = {n.index: n for n in nodes}
    for node in nodes:
        if node.index not in involved:
            others = [o for o in nodes if o is not node]
            peer = random.choice(others)
            key = (min(node.index, peer.index), max(node.index, peer.index))
            pair_set.add(key)

    return [(index_map[a], index_map[b]) for a, b in sorted(pair_set)]


def hub_sparse(nodes: list, k: int, hub_count: int) -> list[tuple]:
    """First hub_count nodes are hubs — connect to all others.
    Remaining leaf nodes connect to all hubs + k random non-hub peers."""
    hub_count = min(hub_count, len(nodes) - 1)
    hubs = nodes[:hub_count]
    leaves = nodes[hub_count:]
    pair_set: set[tuple[int, int]] = set()

    # Hubs connect to every other node
    for hub in hubs:
        for other in [o for o in nodes if o is not hub]:
            key = (min(hub.index, other.index), max(hub.index, other.index))
            pair_set.add(key)

    # Leaves connect to all hubs (already done) + k random non-hub peers
    for leaf in leaves:
        non_hub_others = [o for o in leaves if o is not leaf]
        random.shuffle(non_hub_others)
        for peer in non_hub_others[:k]:
            key = (min(leaf.index, peer.index), max(leaf.index, peer.index))
            pair_set.add(key)

    index_map = {n.index: n for n in nodes}
    return [(index_map[a], index_map[b]) for a, b in sorted(pair_set)]
