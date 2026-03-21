# tests/test_simulate_metrics.py
from tools.simulate.metrics import compute_percentile, build_missing_map


def test_compute_percentile_p50():
    data = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert compute_percentile(data, 50) == 3.0


def test_compute_percentile_p95():
    data = list(range(1, 101))  # 1..100
    p95 = compute_percentile(data, 95)
    assert 94 <= p95 <= 96


def test_compute_percentile_empty():
    assert compute_percentile([], 50) == 0.0


def test_build_missing_map_all_received():
    posted_ids = {"mid-1", "mid-2", "mid-3"}
    node_ids = [{"mid-1", "mid-2", "mid-3"}, {"mid-1", "mid-2", "mid-3"}]
    missing = build_missing_map(posted_ids, node_ids)
    assert missing == {}


def test_build_missing_map_partial():
    posted_ids = {"mid-1", "mid-2", "mid-3"}
    node_ids = [{"mid-1", "mid-2", "mid-3"}, {"mid-1"}]  # node 1 missing 2 and 3
    missing = build_missing_map(posted_ids, node_ids)
    assert 1 in missing
    assert set(missing[1]) == {"mid-2", "mid-3"}
    assert 0 not in missing
