# tests/test_simulate_topology.py
from dataclasses import dataclass
from tools.simulate.topology import full_mesh, sparse_random, hub_sparse


@dataclass
class FakeNode:
    index: int
    port: int


def make_nodes(n):
    return [FakeNode(i, 19000 + i) for i in range(n)]


def test_full_mesh_pair_count():
    nodes = make_nodes(5)
    pairs = full_mesh(nodes)
    assert len(pairs) == 10  # 5*4/2


def test_full_mesh_no_self_pairs():
    nodes = make_nodes(4)
    for a, b in full_mesh(nodes):
        assert a is not b


def test_full_mesh_no_duplicates():
    nodes = make_nodes(4)
    pairs = full_mesh(nodes)
    # Check no (a,b) and (b,a) both present
    seen = set()
    for a, b in pairs:
        key = (min(a.index, b.index), max(a.index, b.index))
        assert key not in seen
        seen.add(key)


def test_full_mesh_two_nodes():
    nodes = make_nodes(2)
    pairs = full_mesh(nodes)
    assert len(pairs) == 1


def test_sparse_random_each_node_has_peers():
    nodes = make_nodes(6)
    pairs = sparse_random(nodes, k=2)
    # Every node must appear in at least one pair
    involved = set()
    for a, b in pairs:
        involved.add(a.index)
        involved.add(b.index)
    assert involved == {0, 1, 2, 3, 4, 5}


def test_sparse_random_no_self_pairs():
    nodes = make_nodes(5)
    for a, b in sparse_random(nodes, k=2):
        assert a is not b


def test_sparse_random_k_exceeds_nodes_clamps():
    # k >= n-1 should not crash; effectively full mesh
    nodes = make_nodes(3)
    pairs = sparse_random(nodes, k=10)
    assert len(pairs) >= 2  # at least ring-like


def test_hub_sparse_hubs_connected_to_all():
    nodes = make_nodes(6)
    pairs = hub_sparse(nodes, k=1, hub_count=2)
    # Hubs are nodes[0] and nodes[1]
    # Every non-hub node must connect to both hubs
    non_hubs = nodes[2:]
    hub_set = {nodes[0].index, nodes[1].index}
    for leaf in non_hubs:
        leaf_partners = {b.index for a, b in pairs if a is leaf} | \
                        {a.index for a, b in pairs if b is leaf}
        assert hub_set.issubset(leaf_partners), \
            f"node {leaf.index} missing hub connections: {leaf_partners}"


def test_hub_sparse_no_self_pairs():
    nodes = make_nodes(5)
    for a, b in hub_sparse(nodes, k=1, hub_count=2):
        assert a is not b
