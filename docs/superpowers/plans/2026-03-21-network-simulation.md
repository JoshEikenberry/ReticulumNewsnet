# Network Simulation Toolset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a multi-process simulation harness that spins up N real newsnet nodes, posts articles across them, waits for full propagation, and prints a throughput/latency report.

**Architecture:** `Simulation` orchestrator class + thin `simulate.py` CLI. Each node is a real `newsnet_main.py` subprocess with an isolated temp dir. Two env var guards added to `newsnet_main.py` first.

**Tech Stack:** Python stdlib (`subprocess`, `tempfile`, `threading`, `argparse`, `dataclasses`), `httpx` (already a dev dep), `rich` (transitive dep via `textual`)

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `newsnet_main.py` | Modify | Add `NEWSNET_CONFIG_DIR` and `NEWSNET_NO_BROWSER` env var guards |
| `tools/__init__.py` | Create | Package marker |
| `tools/simulate/__init__.py` | Create | Package marker |
| `tools/simulate/models.py` | Create | `SimulationConfig`, `PostRecord`, `ConvergenceResult`, `Metrics` dataclasses |
| `tools/simulate/topology.py` | Create | `full_mesh`, `sparse_random`, `hub_sparse` topology builders |
| `tools/simulate/article_gen.py` | Create | `ArticleGenerator` — random articles with configurable params |
| `tools/simulate/node_process.py` | Create | `NodeProcess` — subprocess lifecycle + HTTP client |
| `tools/simulate/metrics.py` | Create | `collect_metrics`, `print_report` using rich |
| `tools/simulate/simulation.py` | Create | `Simulation` orchestrator |
| `tools/simulate/cli.py` | Create | argparse CLI, wires everything together |
| `simulate.py` | Create | Entry point: `from tools.simulate.cli import main; main()` |
| `tests/test_simulate_models.py` | Create | Tests for dataclasses |
| `tests/test_simulate_topology.py` | Create | Tests for topology builders |
| `tests/test_simulate_article_gen.py` | Create | Tests for ArticleGenerator |
| `tests/test_simulate_node_process.py` | Create | Tests for NodeProcess (config writing + HTTP logic) |
| `tests/test_simulate_metrics.py` | Create | Tests for metrics computation |

---

## Task 1: `newsnet_main.py` — env var prerequisites

**Files:**
- Modify: `newsnet_main.py:40-46` (`_load_config`) and `newsnet_main.py:77-79` (browser timer)

### Context

`NewsnetConfig` already has `config_dir_override: str | None = None`. The `_load_config()` function just needs to read `NEWSNET_CONFIG_DIR` and pass it in. `from_file()` doesn't preserve `config_dir_override`, so we restore it after loading.

The browser timer at line 79 needs a `NEWSNET_NO_BROWSER` guard.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_newsnet_main_env.py
import os
import importlib
from unittest.mock import patch, MagicMock
import tempfile
import pathlib


def test_config_dir_override_from_env(tmp_path):
    """NEWSNET_CONFIG_DIR sets config_dir_override on the loaded config."""
    # Write a minimal config.toml in tmp_path
    (tmp_path / "config.toml").write_text(
        'display_name = "tester"\napi_token = "tok"\napi_port = 9000\n'
        'retention_hours = 168\nsync_interval_minutes = 15\nstrict_filtering = false\n'
        'api_host = "127.0.0.1"\n',
        encoding="utf-8",
    )
    with patch.dict(os.environ, {"NEWSNET_CONFIG_DIR": str(tmp_path)}):
        import newsnet_main
        importlib.reload(newsnet_main)
        cfg = newsnet_main._load_config()
    assert str(cfg.config_dir) == str(tmp_path)
    assert cfg.display_name == "tester"


def test_no_browser_env_suppresses_timer():
    """NEWSNET_NO_BROWSER=1 means _open_browser_if_allowed skips the timer."""
    import newsnet_main
    importlib.reload(newsnet_main)

    with patch("threading.Timer") as mock_timer:
        with patch.dict(os.environ, {"NEWSNET_NO_BROWSER": "1"}):
            newsnet_main._open_browser_if_allowed("http://127.0.0.1:9999/")

    mock_timer.assert_not_called()


def test_no_browser_unset_creates_timer():
    """Without NEWSNET_NO_BROWSER, _open_browser_if_allowed creates a timer."""
    import newsnet_main
    importlib.reload(newsnet_main)

    env = {k: v for k, v in os.environ.items() if k != "NEWSNET_NO_BROWSER"}
    with patch.dict(os.environ, env, clear=True):
        with patch("threading.Timer") as mock_timer:
            mock_timer.return_value = MagicMock()
            newsnet_main._open_browser_if_allowed("http://127.0.0.1:9999/")

    mock_timer.assert_called_once()
```

- [ ] **Step 2: Run to confirm test fails**

```
cd C:/vibecode/reticulumnewsnet
python -m pytest tests/test_newsnet_main_env.py::test_config_dir_override_from_env -v
```
Expected: FAIL (env var not yet read in `_load_config`)

- [ ] **Step 3: Implement `NEWSNET_CONFIG_DIR` in `_load_config`**

Replace the existing `_load_config` function (lines 40-46):

```python
def _load_config():
    import os
    from newsnet.config import NewsnetConfig
    config_dir = os.environ.get("NEWSNET_CONFIG_DIR") or None
    cfg = NewsnetConfig(config_dir_override=config_dir)
    cfg.ensure_dirs()
    if cfg.config_file_path.exists():
        cfg = NewsnetConfig.from_file(cfg.config_file_path)
        cfg.config_dir_override = config_dir  # restore — from_file doesn't persist it
    return cfg
```

- [ ] **Step 4: Extract `_open_browser_if_allowed` helper and implement `NEWSNET_NO_BROWSER` guard**

Add a new helper function just before `_run_server`, and replace the timer lines (77-79) in `_run_server` with a call to it:

```python
def _open_browser_if_allowed(url: str) -> None:
    """Open browser after a short delay, unless NEWSNET_NO_BROWSER is set."""
    import os, threading, webbrowser
    if not os.environ.get("NEWSNET_NO_BROWSER"):
        threading.Timer(1.5, webbrowser.open, args=[url]).start()
```

Inside `_run_server`, replace the three browser lines with:

```python
    _open_browser_if_allowed(url)
```

- [ ] **Step 5: Run tests**

```
python -m pytest tests/test_newsnet_main_env.py -v
```
Expected: both PASS

- [ ] **Step 6: Commit**

```bash
git add newsnet_main.py tests/test_newsnet_main_env.py
git commit -m "feat: add NEWSNET_CONFIG_DIR and NEWSNET_NO_BROWSER env var guards"
```

---

## Task 2: Data Models (`tools/simulate/models.py`)

**Files:**
- Create: `tools/__init__.py`
- Create: `tools/simulate/__init__.py`
- Create: `tools/simulate/models.py`
- Test: `tests/test_simulate_models.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run to confirm test fails**

```
python -m pytest tests/test_simulate_models.py -v
```
Expected: FAIL (module doesn't exist)

- [ ] **Step 3: Create package markers and models**

```python
# tools/__init__.py
# (empty)
```

```python
# tools/simulate/__init__.py
# (empty)
```

```python
# tools/simulate/models.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import statistics


@dataclass
class SimulationConfig:
    nodes: int = 5
    articles: int = 100
    topology: str = "full-mesh"   # full-mesh | sparse | hub-sparse
    sparse_k: int = 3
    hub_count: int = 2
    freq: float = 2.0
    body_words_min: int = 50
    body_words_max: int = 200
    newsgroups: int = 3
    group_weights: list[float] = field(default_factory=list)
    thread_prob: float = 0.3
    timeout: int = 60
    base_port: int = 19000

    def newsgroup_names(self) -> list[str]:
        return [f"sim.group-{i}" for i in range(self.newsgroups)]

    def effective_weights(self) -> list[float]:
        weights = list(self.group_weights)
        while len(weights) < self.newsgroups:
            weights.append(1.0)
        return weights[:self.newsgroups]


@dataclass
class PostRecord:
    message_id: str
    posted_at: float
    node_index: int
    newsgroup: str


@dataclass
class ConvergenceResult:
    timed_out: bool
    convergence_time: float          # seconds from first post to full convergence (or timeout)
    first_seen: dict[str, dict[int, float]]  # msg_id -> {node_index -> time_seen}


@dataclass
class Metrics:
    node_count: int
    article_count: int
    topology: str
    convergence_time: float
    post_records: dict[str, PostRecord]     # msg_id -> PostRecord
    first_seen: dict[str, dict[int, float]] # msg_id -> {node_index -> time_seen}
    node_names: list[str]
    missing: dict[int, list[str]]           # node_index -> [missing msg_ids]

    def propagation_latencies(self) -> list[float]:
        """Per-article latency: time from posted_at to when the last node received it."""
        latencies = []
        for msg_id, record in self.post_records.items():
            seen = self.first_seen.get(msg_id, {})
            if not seen:
                continue
            last_seen = max(seen.values())
            latencies.append(last_seen - record.posted_at)
        return sorted(latencies)

    def throughput(self) -> float:
        if self.convergence_time <= 0:
            return 0.0
        return self.article_count / self.convergence_time

    def per_node_received(self) -> list[int]:
        """Articles received per node (all posted articles minus missing)."""
        result = []
        for i in range(self.node_count):
            missing_count = len(self.missing.get(i, []))
            result.append(self.article_count - missing_count)
        return result

    def per_node_posted(self) -> list[int]:
        """Articles originally posted by each node."""
        counts = [0] * self.node_count
        for record in self.post_records.values():
            counts[record.node_index] += 1
        return counts
```

- [ ] **Step 4: Run tests**

```
python -m pytest tests/test_simulate_models.py -v
```
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add tools/__init__.py tools/simulate/__init__.py tools/simulate/models.py tests/test_simulate_models.py
git commit -m "feat: add simulation data models"
```

---

## Task 3: Topology Builders (`tools/simulate/topology.py`)

**Files:**
- Create: `tools/simulate/topology.py`
- Test: `tests/test_simulate_topology.py`

Topology functions take a list of node objects with a `.port` attribute and return a list of `(node_a, node_b)` pairs. Since these are pure functions on any objects with `.port`, they're easy to test with simple stubs.

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run to confirm tests fail**

```
python -m pytest tests/test_simulate_topology.py -v
```
Expected: FAIL (module doesn't exist)

- [ ] **Step 3: Implement topology builders**

```python
# tools/simulate/topology.py
from __future__ import annotations
import random
from typing import Any


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
    all_non_hub = leaves
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
```

- [ ] **Step 4: Run tests**

```
python -m pytest tests/test_simulate_topology.py -v
```
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add tools/simulate/topology.py tests/test_simulate_topology.py
git commit -m "feat: add simulation topology builders"
```

---

## Task 4: Article Generator (`tools/simulate/article_gen.py`)

**Files:**
- Create: `tools/simulate/article_gen.py`
- Test: `tests/test_simulate_article_gen.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_simulate_article_gen.py
from tools.simulate.article_gen import ArticleGenerator
from tools.simulate.models import SimulationConfig


def test_generate_returns_tuple():
    cfg = SimulationConfig(newsgroups=2, body_words_min=5, body_words_max=10, thread_prob=0.0)
    gen = ArticleGenerator(cfg)
    newsgroup, subject, body, references = gen.generate([])
    assert isinstance(newsgroup, str)
    assert isinstance(subject, str)
    assert isinstance(body, str)
    assert references == []


def test_generate_newsgroup_is_valid():
    cfg = SimulationConfig(newsgroups=3)
    gen = ArticleGenerator(cfg)
    valid = cfg.newsgroup_names()
    for _ in range(20):
        newsgroup, _, _, _ = gen.generate([])
        assert newsgroup in valid


def test_generate_body_length_within_range():
    cfg = SimulationConfig(body_words_min=10, body_words_max=20, thread_prob=0.0)
    gen = ArticleGenerator(cfg)
    for _ in range(10):
        _, _, body, _ = gen.generate([])
        word_count = len(body.split())
        assert 10 <= word_count <= 20, f"body had {word_count} words"


def test_generate_root_post_when_no_existing():
    cfg = SimulationConfig(thread_prob=1.0)  # always reply if possible
    gen = ArticleGenerator(cfg)
    _, _, _, refs = gen.generate([])  # no existing articles
    assert refs == []  # can't reply to nothing


def test_generate_reply_when_thread_prob_one():
    cfg = SimulationConfig(thread_prob=1.0)
    gen = ArticleGenerator(cfg)
    existing = [{"message_id": "mid-abc", "newsgroup": "sim.group-0"}]
    _, _, _, refs = gen.generate(existing)
    assert refs == ["mid-abc"]


def test_generate_no_reply_when_thread_prob_zero():
    cfg = SimulationConfig(thread_prob=0.0)
    gen = ArticleGenerator(cfg)
    existing = [{"message_id": "mid-abc", "newsgroup": "sim.group-0"}]
    _, _, _, refs = gen.generate(existing)
    assert refs == []


def test_weighted_newsgroup_distribution():
    """Heavy weight on group-0 should mean it appears much more often."""
    cfg = SimulationConfig(newsgroups=2, group_weights=[100.0, 1.0], thread_prob=0.0)
    gen = ArticleGenerator(cfg)
    results = [gen.generate([])[0] for _ in range(200)]
    group0_count = results.count("sim.group-0")
    assert group0_count > 150, f"expected >150 hits for group-0, got {group0_count}"
```

- [ ] **Step 2: Run to confirm tests fail**

```
python -m pytest tests/test_simulate_article_gen.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement ArticleGenerator**

```python
# tools/simulate/article_gen.py
from __future__ import annotations
import random
from tools.simulate.models import SimulationConfig

_WORDS = [
    "alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel",
    "india", "juliet", "kilo", "lima", "mike", "november", "oscar", "papa",
    "quebec", "romeo", "sierra", "tango", "uniform", "victor", "whiskey",
    "xray", "yankee", "zulu", "apple", "banana", "cherry", "dragon",
    "elephant", "falcon", "grape", "harbor", "island", "jungle", "kitten",
    "lemon", "mango", "north", "ocean", "purple", "quiet", "river", "silver",
    "tiger", "under", "violet", "winter", "yellow", "zebra", "anchor", "bridge",
    "castle", "desert", "engine", "forest", "garden", "hammer", "igloo",
    "jacket", "kernel", "ladder", "mirror", "needle", "office", "planet",
    "quartz", "rocket", "sunset", "tunnel", "vacuum", "window", "barrel",
    "candle", "dancer", "empire", "flower", "gadget", "hollow", "impact",
    "jigsaw", "kettle", "lantern", "marble", "narrow", "outlaw", "pencil",
    "quarry", "riddle", "shadow", "timber", "vessel", "walnut", "battle",
    "copper", "dollar", "fabric", "gamble", "handle", "insult", "jargon",
    "launch", "magnet", "napkin", "output", "pillow", "quantum", "rabbit",
    "stable", "trophy", "unlock", "vendor", "walrus", "zealot", "absent",
    "beckon", "carbon", "dagger", "famine", "glitch", "hustle", "invent",
    "jostle", "luster", "mortal", "noodle", "onward", "pardon", "quiver",
    "ramble", "squire", "torque", "update", "velvet", "wander", "bonnet",
    "cobalt", "debris", "frenzy", "gossip", "hurdle", "influx", "jaunty",
    "karate", "lavish", "muffin", "osprey", "ponder", "radish", "turnip",
    "upbeat", "warren", "cactus", "donkey", "finger", "gravel", "hatch",
]


class ArticleGenerator:
    def __init__(self, config: SimulationConfig):
        self._groups = config.newsgroup_names()
        self._weights = config.effective_weights()
        self._body_min = config.body_words_min
        self._body_max = config.body_words_max
        self._thread_prob = config.thread_prob

    def generate(self, existing_articles: list[dict]) -> tuple[str, str, str, list[str]]:
        """Return (newsgroup, subject, body, references).

        existing_articles: list of dicts with at least 'message_id' key.
        """
        newsgroup = random.choices(self._groups, weights=self._weights, k=1)[0]
        subject = " ".join(random.choices(_WORDS, k=random.randint(3, 8)))
        word_count = random.randint(self._body_min, self._body_max)
        words = random.choices(_WORDS, k=word_count)
        # Break into sentences of 8-15 words
        sentences = []
        i = 0
        while i < len(words):
            chunk_size = random.randint(8, 15)
            chunk = words[i:i + chunk_size]
            sentences.append(" ".join(chunk).capitalize() + ".")
            i += chunk_size
        body = " ".join(sentences)

        references: list[str] = []
        if self._thread_prob > 0 and existing_articles and random.random() < self._thread_prob:
            parent = random.choice(existing_articles)
            references = [parent["message_id"]]

        return newsgroup, subject, body, references
```

- [ ] **Step 4: Run tests**

```
python -m pytest tests/test_simulate_article_gen.py -v
```
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add tools/simulate/article_gen.py tests/test_simulate_article_gen.py
git commit -m "feat: add simulation article generator"
```

---

## Task 5: NodeProcess (`tools/simulate/node_process.py`)

**Files:**
- Create: `tools/simulate/node_process.py`
- Test: `tests/test_simulate_node_process.py`

We test config writing and HTTP method construction. Subprocess spawning is integration-level — tested via `simulate.py` end-to-end.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_simulate_node_process.py
import tomllib
import tempfile
import pathlib
from unittest.mock import patch, MagicMock
from tools.simulate.node_process import NodeProcess, _write_config


def test_write_config_creates_valid_toml(tmp_path):
    _write_config(tmp_path, index=2, port=19002, token="test-tok-xyz")
    config_path = tmp_path / "config.toml"
    assert config_path.exists()
    with open(config_path, "rb") as f:
        data = tomllib.load(f)
    assert data["api_port"] == 19002
    assert data["api_token"] == "test-tok-xyz"
    assert data["display_name"] == "sim-node-2"
    assert data["strict_filtering"] == False
    assert data["api_host"] == "127.0.0.1"


def test_write_config_sets_sync_interval_to_one(tmp_path):
    _write_config(tmp_path, index=0, port=19000, token="tok")
    with open(tmp_path / "config.toml", "rb") as f:
        data = tomllib.load(f)
    assert data["sync_interval_minutes"] == 1


def test_node_process_url():
    node = NodeProcess.__new__(NodeProcess)
    node.port = 19003
    node.token = "abc"
    node.index = 3
    node._proc = None
    node._temp_dir = None
    assert node._url("/api/articles") == "http://127.0.0.1:19003/api/articles"


def test_node_process_post_article_calls_correct_endpoint():
    node = NodeProcess.__new__(NodeProcess)
    node.port = 19000
    node.token = "tok"
    node.index = 0
    node._proc = None
    node._temp_dir = None

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"message_id": "mid-abc"}

    with patch("httpx.post", return_value=mock_response) as mock_post:
        result = node.post_article("sim.group-0", "hello world", "body text")

    mock_post.assert_called_once_with(
        "http://127.0.0.1:19000/api/articles",
        json={"newsgroup": "sim.group-0", "subject": "hello world",
              "body": "body text", "references": []},
        headers={"Authorization": "Bearer tok"},
        timeout=10,
    )
    assert result == "mid-abc"


def test_node_process_list_article_ids():
    node = NodeProcess.__new__(NodeProcess)
    node.port = 19000
    node.token = "tok"
    node.index = 0
    node._proc = None
    node._temp_dir = None

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = [
        {"message_id": "mid-1"}, {"message_id": "mid-2"}
    ]

    with patch("httpx.get", return_value=mock_response):
        ids = node.list_article_ids()

    assert ids == {"mid-1", "mid-2"}


def test_node_process_add_tcp_peer():
    node = NodeProcess.__new__(NodeProcess)
    node.port = 19000
    node.token = "tok"
    node.index = 0
    node._proc = None
    node._temp_dir = None

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"address": "127.0.0.1:19001"}

    with patch("httpx.post", return_value=mock_response) as mock_post:
        node.add_tcp_peer("127.0.0.1", 19001)

    mock_post.assert_called_once_with(
        "http://127.0.0.1:19000/api/peers",
        json={"address": "127.0.0.1:19001"},
        headers={"Authorization": "Bearer tok"},
        timeout=10,
    )
```

- [ ] **Step 2: Run to confirm tests fail**

```
python -m pytest tests/test_simulate_node_process.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement NodeProcess**

```python
# tools/simulate/node_process.py
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

import httpx


def _write_config(config_dir: Path, index: int, port: int, token: str) -> None:
    config_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        f'display_name = "sim-node-{index}"',
        f'api_port = {port}',
        f'api_host = "127.0.0.1"',
        f'api_token = "{token}"',
        'retention_hours = 168',
        'sync_interval_minutes = 1',
        'strict_filtering = false',
    ]
    (config_dir / "config.toml").write_text("\n".join(lines) + "\n", encoding="utf-8")


class NodeProcess:
    def __init__(self, index: int, port: int):
        self.index = index
        self.port = port
        self.token = str(uuid.uuid4())
        self._temp_dir = Path(tempfile.mkdtemp(prefix=f"newsnet-sim-{index}-"))
        self._proc: subprocess.Popen | None = None

        _write_config(self._temp_dir, index, port, self.token)

    def start(self) -> None:
        """Spawn newsnet_main.py subprocess with isolated config dir."""
        env = os.environ.copy()
        env["NEWSNET_CONFIG_DIR"] = str(self._temp_dir)
        env["NEWSNET_NO_BROWSER"] = "1"
        # Suppress RNS noise
        env.setdefault("NEWSNET_DEBUG", "")

        main_py = Path(__file__).parents[2] / "newsnet_main.py"
        self._proc = subprocess.Popen(
            [sys.executable, str(main_py)],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def wait_ready(self, timeout: float = 15.0) -> None:
        """Poll /api/local-auth until 200 or timeout."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                r = httpx.get(
                    f"http://127.0.0.1:{self.port}/api/local-auth", timeout=2.0
                )
                if r.status_code == 200:
                    return
            except Exception:
                pass
            time.sleep(0.3)
        raise TimeoutError(f"sim-node-{self.index} (port {self.port}) did not start within {timeout}s")

    def _url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.port}{path}"

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    def post_article(
        self,
        newsgroup: str,
        subject: str,
        body: str,
        references: list[str] | None = None,
    ) -> str:
        """Post an article and return its message_id."""
        r = httpx.post(
            self._url("/api/articles"),
            json={
                "newsgroup": newsgroup,
                "subject": subject,
                "body": body,
                "references": references or [],
            },
            headers=self._headers(),
            timeout=10,
        )
        r.raise_for_status()
        return r.json()["message_id"]

    def list_article_ids(self) -> set[str]:
        """Return set of all message_ids this node currently holds."""
        r = httpx.get(self._url("/api/articles"), headers=self._headers(), timeout=10)
        r.raise_for_status()
        return {a["message_id"] for a in r.json()}

    def add_tcp_peer(self, host: str, port: int) -> None:
        """Tell this node to connect to another node as a TCP peer."""
        r = httpx.post(
            self._url("/api/peers"),
            json={"address": f"{host}:{port}"},
            headers=self._headers(),
            timeout=10,
        )
        r.raise_for_status()

    def close(self) -> None:
        """Terminate subprocess and delete temp dir."""
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        if self._temp_dir and self._temp_dir.exists():
            shutil.rmtree(self._temp_dir, ignore_errors=True)
```

- [ ] **Step 4: Run tests**

```
python -m pytest tests/test_simulate_node_process.py -v
```
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add tools/simulate/node_process.py tests/test_simulate_node_process.py
git commit -m "feat: add NodeProcess for simulation"
```

---

## Task 6: Metrics Collection & Report (`tools/simulate/metrics.py`)

**Files:**
- Create: `tools/simulate/metrics.py`
- Test: `tests/test_simulate_metrics.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_simulate_metrics.py
from tools.simulate.models import Metrics, PostRecord
from tools.simulate.metrics import compute_percentile, build_missing_map
import statistics


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
```

- [ ] **Step 2: Run to confirm tests fail**

```
python -m pytest tests/test_simulate_metrics.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement metrics module**

```python
# tools/simulate/metrics.py
from __future__ import annotations
import statistics
from tools.simulate.models import Metrics


def compute_percentile(data: list[float], p: int) -> float:
    if not data:
        return 0.0
    sorted_data = sorted(data)
    idx = int(len(sorted_data) * p / 100)
    idx = min(idx, len(sorted_data) - 1)
    return sorted_data[idx]


def build_missing_map(
    posted_ids: set[str], node_article_ids: list[set[str]]
) -> dict[int, list[str]]:
    """Return {node_index: [missing_msg_ids]} for nodes that didn't receive all articles."""
    missing = {}
    for i, node_ids in enumerate(node_article_ids):
        absent = sorted(posted_ids - node_ids)
        if absent:
            missing[i] = absent
    return missing


def print_report(m: Metrics) -> None:
    from rich.console import Console
    from rich.table import Table
    from rich import box

    console = Console()
    latencies = m.propagation_latencies()
    p50 = compute_percentile(latencies, 50)
    p95 = compute_percentile(latencies, 95)
    p_max = max(latencies) if latencies else 0.0
    throughput = m.throughput()

    status = "converged" if not m.missing else "TIMED OUT"

    console.print()
    console.print(
        f"[bold]Simulation complete[/bold] — "
        f"{m.node_count} nodes · {m.article_count} articles · "
        f"{m.topology} · {status} in [green]{m.convergence_time:.1f}s[/green]"
    )
    console.print()
    console.print(f"  Throughput:   [cyan]{throughput:.1f}[/cyan] articles/sec")
    console.print(
        f"  Propagation:  p50 [cyan]{p50:.2f}s[/cyan]  "
        f"p95 [cyan]{p95:.2f}s[/cyan]  "
        f"max [cyan]{p_max:.2f}s[/cyan]"
    )
    console.print()

    table = Table(box=box.SIMPLE)
    table.add_column("Node", style="bold")
    table.add_column("Posted", justify="right")
    table.add_column("Received", justify="right")
    table.add_column("Coverage", justify="right")

    posted_per_node = m.per_node_posted()
    received_per_node = m.per_node_received()

    for i, name in enumerate(m.node_names):
        received = received_per_node[i]
        coverage = f"{100 * received / m.article_count:.0f}%" if m.article_count else "—"
        color = "green" if received == m.article_count else "red"
        table.add_row(
            name,
            str(posted_per_node[i]),
            f"[{color}]{received}[/{color}]",
            f"[{color}]{coverage}[/{color}]",
        )

    console.print(table)

    if m.missing:
        console.print(f"[red]Warning: {sum(len(v) for v in m.missing.values())} article(s) did not propagate:[/red]")
        for node_idx, ids in m.missing.items():
            console.print(f"  {m.node_names[node_idx]}: missing {len(ids)} article(s)")
    else:
        console.print(f"[green]All {m.article_count} articles propagated to all {m.node_count} nodes.[/green]")
    console.print()
```

- [ ] **Step 4: Run tests**

```
python -m pytest tests/test_simulate_metrics.py -v
```
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add tools/simulate/metrics.py tests/test_simulate_metrics.py
git commit -m "feat: add simulation metrics and report formatting"
```

---

## Task 7: Simulation Orchestrator (`tools/simulate/simulation.py`)

**Files:**
- Create: `tools/simulate/simulation.py`
- Test: `tests/test_simulate_simulation.py`

We test the orchestrator with a mocked NodeProcess so no real subprocesses spawn.

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run to confirm tests fail**

```
python -m pytest tests/test_simulate_simulation.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement Simulation orchestrator**

```python
# tools/simulate/simulation.py
from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass, field

from tools.simulate.article_gen import ArticleGenerator
from tools.simulate.models import (
    ConvergenceResult,
    Metrics,
    PostRecord,
    SimulationConfig,
)
from tools.simulate.node_process import NodeProcess
from tools.simulate.topology import full_mesh, hub_sparse, sparse_random
from tools.simulate.metrics import build_missing_map


class Simulation:
    def __init__(self, config: SimulationConfig):
        self.config = config
        self.nodes: list[NodeProcess] = []
        self._post_records: dict[str, PostRecord] = {}
        self._posted_ids: set[str] = set()
        self._first_post_at: float = 0.0
        self._gen = ArticleGenerator(config)

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def setup(self) -> None:
        """Spawn all nodes in parallel, wait for ready, then connect topology."""
        cfg = self.config
        self.nodes = [
            NodeProcess(index=i, port=cfg.base_port + i)
            for i in range(cfg.nodes)
        ]

        # Start all subprocesses
        for node in self.nodes:
            node.start()

        # Wait for all nodes to be ready (in parallel)
        errors: list[Exception] = []
        lock = threading.Lock()

        def _wait(node):
            try:
                node.wait_ready()
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=_wait, args=(n,)) for n in self.nodes]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        if errors:
            self.teardown()
            raise errors[0]

        # Connect topology
        pairs = self._build_topology()
        for node_a, node_b in pairs:
            node_a.add_tcp_peer("127.0.0.1", node_b.port)

    def _build_topology(self):
        cfg = self.config
        if cfg.topology == "full-mesh":
            return full_mesh(self.nodes)
        elif cfg.topology == "sparse":
            return sparse_random(self.nodes, cfg.sparse_k)
        elif cfg.topology == "hub-sparse":
            return hub_sparse(self.nodes, cfg.sparse_k, cfg.hub_count)
        else:
            raise ValueError(f"Unknown topology: {cfg.topology!r}")

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Post article_count articles across nodes at configured frequency."""
        cfg = self.config
        self._first_post_at = time.time()
        posted_articles: list[dict] = []
        interval = 1.0 / cfg.freq if cfg.freq > 0 else 0.0

        for i in range(cfg.articles):
            node = random.choice(self.nodes)
            newsgroup, subject, body, references = self._gen.generate(posted_articles)
            try:
                msg_id = node.post_article(newsgroup, subject, body, references)
                record = PostRecord(
                    message_id=msg_id,
                    posted_at=time.time(),
                    node_index=node.index,
                    newsgroup=newsgroup,
                )
                self._post_records[msg_id] = record
                self._posted_ids.add(msg_id)
                posted_articles.append({"message_id": msg_id, "newsgroup": newsgroup})
            except Exception as e:
                print(f"  [warn] Failed to post article {i}: {e}")
            if interval > 0:
                time.sleep(interval)

    # ------------------------------------------------------------------
    # Convergence
    # ------------------------------------------------------------------

    def wait_for_convergence(self) -> ConvergenceResult:
        """Poll all nodes every 0.5s until all have all posted articles."""
        cfg = self.config
        deadline = time.time() + cfg.timeout
        first_seen: dict[str, dict[int, float]] = {}

        while time.time() < deadline:
            all_have_all = True
            for node in self.nodes:
                try:
                    ids = node.list_article_ids()
                except Exception:
                    all_have_all = False
                    continue

                now = time.time()
                for msg_id in ids:
                    if msg_id in self._posted_ids:
                        if msg_id not in first_seen:
                            first_seen[msg_id] = {}
                        if node.index not in first_seen[msg_id]:
                            first_seen[msg_id][node.index] = now

                missing = self._posted_ids - ids
                if missing:
                    all_have_all = False

            if all_have_all and self._posted_ids:
                return ConvergenceResult(
                    timed_out=False,
                    convergence_time=time.time() - self._first_post_at,
                    first_seen=first_seen,
                )
            time.sleep(0.5)

        return ConvergenceResult(
            timed_out=True,
            convergence_time=cfg.timeout,
            first_seen=first_seen,
        )

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def collect_metrics(self, result: ConvergenceResult) -> Metrics:
        node_ids = []
        for node in self.nodes:
            try:
                node_ids.append(node.list_article_ids())
            except Exception:
                node_ids.append(set())

        missing = build_missing_map(self._posted_ids, node_ids)
        return Metrics(
            node_count=len(self.nodes),
            article_count=len(self._posted_ids),
            topology=self.config.topology,
            convergence_time=result.convergence_time,
            post_records=self._post_records,
            first_seen=result.first_seen,
            node_names=[f"sim-node-{n.index}" for n in self.nodes],
            missing=missing,
        )

    # ------------------------------------------------------------------
    # Teardown
    # ------------------------------------------------------------------

    def teardown(self) -> None:
        """Terminate all subprocesses and clean up temp dirs."""
        for node in self.nodes:
            try:
                node.close()
            except Exception:
                pass
```

- [ ] **Step 4: Run tests**

```
python -m pytest tests/test_simulate_simulation.py -v
```
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add tools/simulate/simulation.py tests/test_simulate_simulation.py
git commit -m "feat: add Simulation orchestrator"
```

---

## Task 8: CLI + Entry Point (`tools/simulate/cli.py`, `simulate.py`)

**Files:**
- Create: `tools/simulate/cli.py`
- Create: `simulate.py`

No unit test for CLI (it's a thin wrapper). Verified by running manually.

- [ ] **Step 1: Create `tools/simulate/cli.py`**

```python
# tools/simulate/cli.py
from __future__ import annotations

import argparse
import sys

from tools.simulate.models import SimulationConfig
from tools.simulate.simulation import Simulation
from tools.simulate.metrics import print_report


def parse_body_words(value: str) -> tuple[int, int]:
    if "-" in value:
        parts = value.split("-", 1)
        return int(parts[0]), int(parts[1])
    n = int(value)
    return n, n


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Simulate a ReticulumNewsnet P2P network and measure throughput.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--nodes", type=int, default=5, help="Number of nodes")
    p.add_argument("--articles", type=int, default=100, help="Articles to post")
    p.add_argument(
        "--topology",
        choices=["full-mesh", "sparse", "hub-sparse"],
        default="full-mesh",
        help="Network topology",
    )
    p.add_argument("--sparse-k", type=int, default=3, dest="sparse_k",
                   help="Peers per node (sparse/hub-sparse)")
    p.add_argument("--hubs", type=int, default=2, dest="hub_count",
                   help="Hub node count (hub-sparse)")
    p.add_argument("--freq", type=float, default=2.0,
                   help="Article posting rate (articles/sec)")
    p.add_argument("--body-words", type=str, default="50-200", dest="body_words",
                   help="Body length range MIN-MAX words")
    p.add_argument("--newsgroups", type=int, default=3,
                   help="Number of simulated newsgroups")
    p.add_argument("--group-weights", type=float, nargs="+", default=[],
                   dest="group_weights", help="Relative weights per newsgroup")
    p.add_argument("--thread-prob", type=float, default=0.3, dest="thread_prob",
                   help="Probability a post is a reply (0.0-1.0)")
    p.add_argument("--timeout", type=int, default=60,
                   help="Convergence timeout in seconds")
    p.add_argument("--base-port", type=int, default=19000, dest="base_port",
                   help="Starting port for nodes")
    return p


def main(argv=None) -> None:
    args = build_parser().parse_args(argv)
    body_min, body_max = parse_body_words(args.body_words)

    cfg = SimulationConfig(
        nodes=args.nodes,
        articles=args.articles,
        topology=args.topology,
        sparse_k=args.sparse_k,
        hub_count=args.hub_count,
        freq=args.freq,
        body_words_min=body_min,
        body_words_max=body_max,
        newsgroups=args.newsgroups,
        group_weights=args.group_weights,
        thread_prob=args.thread_prob,
        timeout=args.timeout,
        base_port=args.base_port,
    )

    print(f"Starting simulation: {cfg.nodes} nodes, {cfg.articles} articles, "
          f"{cfg.topology}, {cfg.newsgroups} newsgroups")
    print(f"Posting at {cfg.freq} articles/sec, convergence timeout {cfg.timeout}s")
    print()

    sim = Simulation(cfg)
    try:
        print("Setting up nodes...")
        sim.setup()
        print(f"All {cfg.nodes} nodes ready. Posting articles...")
        sim.run()
        print(f"Posted {len(sim._posted_ids)} articles. Waiting for convergence...")
        result = sim.wait_for_convergence()
        metrics = sim.collect_metrics(result)
    finally:
        sim.teardown()

    print_report(metrics)
    sys.exit(0 if not metrics.missing else 1)
```

- [ ] **Step 2: Create `simulate.py`**

```python
# simulate.py
from tools.simulate.cli import main

if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Smoke test — verify the CLI parses args correctly**

```
python simulate.py --help
```
Expected: prints usage with all flags listed

- [ ] **Step 4: Smoke test — verify `--nodes 2 --articles 3` runs without crashing on CLI parsing**

```
python -c "from tools.simulate.cli import build_parser; p = build_parser(); args = p.parse_args(['--nodes','2','--articles','3']); print(args)"
```
Expected: prints `Namespace(nodes=2, articles=3, ...)`

- [ ] **Step 5: Commit**

```bash
git add tools/simulate/cli.py simulate.py
git commit -m "feat: add simulation CLI entry point"
```

---

## Task 9: Full test suite pass

- [ ] **Step 1: Run all simulation tests**

```
python -m pytest tests/test_simulate_models.py tests/test_simulate_topology.py tests/test_simulate_article_gen.py tests/test_simulate_node_process.py tests/test_simulate_metrics.py tests/test_simulate_simulation.py -v
```
Expected: all PASS

- [ ] **Step 2: Run full test suite to confirm no regressions**

```
python -m pytest tests/ -v --ignore=tests/test_newsnet_main_env.py -x
```
Expected: all existing tests PASS

- [ ] **Step 3: Commit any fixes**

```bash
git add -A
git commit -m "fix: resolve any test suite regressions"
```

---

## Task 10: Integration smoke test (manual)

This task requires a real RNS environment. If RNS is not configured, the nodes will fail to start (RNS requires at minimum a local loopback interface or TCP interface). Skip if RNS is not available on this machine.

- [ ] **Step 1: Run a minimal simulation**

```
python simulate.py --nodes 2 --articles 10 --freq 1.0 --timeout 30
```
Expected: nodes start, articles post, convergence detected, report printed.

- [ ] **Step 2: Run with sparse topology**

```
python simulate.py --nodes 5 --articles 50 --topology sparse --sparse-k 2 --timeout 60
```

- [ ] **Step 3: Run with hub topology and weighted newsgroups**

```
python simulate.py --nodes 6 --articles 50 --topology hub-sparse --hubs 2 --newsgroups 4 --group-weights 10 3 1 1 --thread-prob 0.5 --timeout 90
```

- [ ] **Step 4: Commit any fixes discovered during integration testing**

```bash
git add -A
git commit -m "fix: integration test fixes for simulation toolset"
```
