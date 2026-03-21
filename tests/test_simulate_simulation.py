# tests/test_simulate_simulation.py
from unittest.mock import MagicMock, patch, call
from tools.simulate.models import SimulationConfig
from tools.simulate.simulation import Simulation
import time


def make_mock_node(index, port, article_ids=None):
    node = MagicMock()
    node.index = index
    node.port = port
    node.token = f"tok-{index}"
    node.list_article_ids.return_value = set(article_ids or [])
    return node


def test_simulation_setup_spawns_correct_node_count():
    cfg = SimulationConfig(nodes=3, base_port=19000, topology="full-mesh")
    sim = Simulation(cfg)

    mock_nodes = [make_mock_node(i, 19000 + i) for i in range(3)]
    with patch("tools.simulate.simulation.NodeProcess", side_effect=mock_nodes):
        with patch("tools.simulate.simulation.full_mesh", return_value=[]) as mock_topo:
            sim.setup()

    assert len(sim.nodes) == 3


def test_simulation_setup_full_mesh_connects_peers():
    cfg = SimulationConfig(nodes=2, base_port=19000, topology="full-mesh")
    sim = Simulation(cfg)

    node0 = make_mock_node(0, 19000)
    node1 = make_mock_node(1, 19001)
    mock_nodes = [node0, node1]

    with patch("tools.simulate.simulation.NodeProcess", side_effect=mock_nodes):
        with patch("tools.simulate.simulation.full_mesh", return_value=[(node0, node1)]):
            sim.setup()

    node0.add_tcp_peer.assert_called_once_with("127.0.0.1", 19001)


def test_simulation_run_posts_correct_article_count():
    cfg = SimulationConfig(nodes=2, articles=5, freq=100.0, topology="full-mesh",
                           newsgroups=1, thread_prob=0.0)
    sim = Simulation(cfg)

    node0 = make_mock_node(0, 19000)
    node1 = make_mock_node(1, 19001)
    node0.post_article.return_value = "mid-0"
    node1.post_article.return_value = "mid-1"

    sim.nodes = [node0, node1]

    sim.run()

    total_posts = node0.post_article.call_count + node1.post_article.call_count
    assert total_posts == 5


def test_simulation_wait_for_convergence_detects_all_received():
    cfg = SimulationConfig(nodes=2, articles=2, timeout=5)
    sim = Simulation(cfg)

    node0 = make_mock_node(0, 19000, article_ids=["mid-1", "mid-2"])
    node1 = make_mock_node(1, 19001, article_ids=["mid-1", "mid-2"])
    sim.nodes = [node0, node1]
    sim._posted_ids = {"mid-1", "mid-2"}
    sim._post_records = {}
    sim._first_post_at = time.time()

    result = sim.wait_for_convergence()

    assert not result.timed_out
    assert result.convergence_time >= 0


def test_simulation_teardown_closes_all_nodes():
    cfg = SimulationConfig(nodes=3)
    sim = Simulation(cfg)
    mock_nodes = [MagicMock() for _ in range(3)]
    sim.nodes = mock_nodes

    sim.teardown()

    for node in mock_nodes:
        node.close.assert_called_once()
