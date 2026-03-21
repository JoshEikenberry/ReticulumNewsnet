# tests/test_simulate_models.py
from tools.simulate.models import SimulationConfig, PostRecord, ConvergenceResult, Metrics
import time


def test_simulation_config_defaults():
    cfg = SimulationConfig()
    assert cfg.nodes == 5
    assert cfg.articles == 100
    assert cfg.topology == "full-mesh"
    assert cfg.sparse_k == 3
    assert cfg.hub_count == 2
    assert cfg.freq == 2.0
    assert cfg.body_words_min == 50
    assert cfg.body_words_max == 200
    assert cfg.newsgroups == 3
    assert cfg.group_weights == []
    assert cfg.thread_prob == 0.3
    assert cfg.timeout == 60
    assert cfg.base_port == 19000


def test_simulation_config_newsgroup_names():
    cfg = SimulationConfig(newsgroups=4)
    names = cfg.newsgroup_names()
    assert names == ["sim.group-0", "sim.group-1", "sim.group-2", "sim.group-3"]


def test_simulation_config_effective_weights_uniform():
    cfg = SimulationConfig(newsgroups=3, group_weights=[])
    assert cfg.effective_weights() == [1.0, 1.0, 1.0]


def test_simulation_config_effective_weights_partial():
    cfg = SimulationConfig(newsgroups=4, group_weights=[10.0, 3.0])
    assert cfg.effective_weights() == [10.0, 3.0, 1.0, 1.0]


def test_post_record_fields():
    t = time.time()
    r = PostRecord(message_id="mid-1", posted_at=t, node_index=2, newsgroup="sim.group-0")
    assert r.message_id == "mid-1"
    assert r.node_index == 2


def test_convergence_result_converged():
    r = ConvergenceResult(
        timed_out=False,
        convergence_time=8.3,
        first_seen={},
    )
    assert not r.timed_out
    assert r.convergence_time == 8.3


def test_metrics_propagation_latencies():
    records = {
        "mid-1": PostRecord("mid-1", posted_at=0.0, node_index=0, newsgroup="sim.group-0"),
        "mid-2": PostRecord("mid-2", posted_at=1.0, node_index=1, newsgroup="sim.group-0"),
    }
    # first_seen[msg_id][node_index] = time_seen
    first_seen = {
        "mid-1": {0: 0.0, 1: 2.0, 2: 3.0},
        "mid-2": {0: 2.5, 1: 1.0, 2: 4.0},
    }
    m = Metrics(
        node_count=3,
        article_count=2,
        topology="full-mesh",
        convergence_time=4.0,
        post_records=records,
        first_seen=first_seen,
        node_names=["sim-node-0", "sim-node-1", "sim-node-2"],
        missing={},
    )
    lats = m.propagation_latencies()
    # mid-1: last seen at t=3.0, posted at t=0.0 → latency 3.0
    # mid-2: last seen at t=4.0, posted at t=1.0 → latency 3.0
    assert lats == [3.0, 3.0]


def test_metrics_throughput():
    records = {f"mid-{i}": PostRecord(f"mid-{i}", 0.0, 0, "g") for i in range(10)}
    m = Metrics(
        node_count=2, article_count=10, topology="full-mesh",
        convergence_time=5.0, post_records=records, first_seen={},
        node_names=["a", "b"], missing={},
    )
    assert m.throughput() == 2.0
