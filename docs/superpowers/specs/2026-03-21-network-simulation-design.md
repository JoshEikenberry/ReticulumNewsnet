# Network Simulation Toolset — Design Spec

**Goal:** A multi-process simulation harness that spins up N real newsnet nodes, posts articles across them, waits for full propagation, and reports throughput and latency metrics — making bottlenecks in the sync protocol visible and measurable.

**Architecture:** Orchestrator class (`Simulation`) + thin CLI entry point (`simulate.py`). Each node is a real `newsnet_main.py` subprocess with an isolated temp directory. Nodes communicate only via their TCP peer connections, exactly as real separate machines would.

**Tech Stack:** Python stdlib (`subprocess`, `tempfile`, `threading`, `argparse`), `httpx` (async-friendly HTTP client for polling nodes), `rich` (terminal table formatting for the report).

---

## Prerequisites: Two Small Changes to `newsnet_main.py`

Before the simulation toolset can work, `newsnet_main.py` needs two env var guards:

1. **`NEWSNET_CONFIG_DIR`** — if set, use this path as the config directory instead of `~/.config/reticulum-newsnet/`. Allows each subprocess to have an isolated config, identity, and database.
2. **`NEWSNET_NO_BROWSER`** — if set to `1`, skip the `threading.Timer` browser-open call. Prevents N browser tabs opening during simulation.

Both are one-liner additions to `newsnet_main.py`.

---

## File Structure

```
tools/
  simulate/
    __init__.py
    node_process.py   # NodeProcess: subprocess lifecycle + HTTP client
    topology.py       # TopologyBuilder: full_mesh, sparse_random, hub_sparse
    article_gen.py    # ArticleGenerator: random articles with configurable params
    simulation.py     # Simulation: orchestrator class
    metrics.py        # MetricsCollector: convergence tracking + report formatting
    cli.py            # argparse CLI, wires everything together
simulate.py           # entry point: from tools.simulate.cli import main; main()
```

Each file has one clear responsibility. `simulation.py` imports from all others but none of the others imports from `simulation.py` — the dependency graph is a DAG.

---

## Component Designs

### `node_process.py` — NodeProcess

Manages one simulated node's full lifecycle.

**Setup:**
- Creates a `tempfile.mkdtemp()` directory
- Writes a minimal `config.toml` with unique values:
  - `api_port`: starts at 19000, increments per node
  - `api_token`: `uuid4()`
  - `display_name`: `sim-node-{index}`
  - `retention_hours`: 168
  - `sync_interval_minutes`: 1 (minimum; simulation drives sync via TCP peers)
  - `strict_filtering`: false
- Spawns `newsnet_main.py` subprocess with env vars `NEWSNET_CONFIG_DIR` and `NEWSNET_NO_BROWSER=1`
- Polls `GET /api/local-auth` (no token required, localhost only) until HTTP 200 or 10s timeout

**HTTP methods (all use Bearer token auth):**
- `post_article(newsgroup, subject, body, references=[])` → `message_id`
- `list_article_ids()` → `set[str]` of message_ids currently in the store
- `add_tcp_peer(host, port)` → establishes TCP peer connection to another node

**Cleanup:**
- `close()`: terminate subprocess, `shutil.rmtree(temp_dir)`

---

### `topology.py` — TopologyBuilder

Takes a list of `NodeProcess` instances, returns a list of `(node_a, node_b)` pairs to connect. Connections are one-directional initiators (node_a calls `add_tcp_peer` pointing at node_b's port).

**`full_mesh(nodes)`**
All `N*(N-1)/2` pairs. Every node connects to every other node. Default topology.

**`sparse_random(nodes, k)`**
Each node gets `k` randomly chosen peers. Uses a shuffle-based approach to ensure no node is isolated (every node has at least one outbound connection). Deduplicates bidirectional pairs.

**`hub_sparse(nodes, k, hub_count)`**
First `hub_count` nodes are hubs. Hubs connect to every other node (fully connected among themselves and to all leaves). Each remaining leaf node connects to all hubs plus `k` random non-hub peers. This approximates a public network with always-on relay nodes.

---

### `article_gen.py` — ArticleGenerator

Generates random articles using a built-in word list (no external dependency). Configurable at construction time.

**Parameters:**
- `newsgroups`: list of newsgroup names (e.g. `["sim.group-0", "sim.group-1"]`)
- `group_weights`: list of relative weights, one per newsgroup. If shorter than `newsgroups`, remaining groups get weight 1. Newsgroup is sampled via `random.choices(newsgroups, weights=group_weights)`.
- `body_words_min`, `body_words_max`: random body length range
- `thread_prob`: probability (0.0–1.0) that a new article is a reply to an existing article rather than a root post

**`generate(existing_articles)`**
Returns `(newsgroup, subject, body, references)`. If `thread_prob > 0` and `existing_articles` is non-empty, samples a parent article with probability `thread_prob` and sets `references = [parent.message_id]`. Otherwise `references = []`.

Subject is 3–8 random words. Body is `body_words_min..body_words_max` random words joined into sentences.

---

### `simulation.py` — Simulation

The orchestrator. Calls components in order.

```python
class Simulation:
    def __init__(self, config: SimulationConfig): ...
    def setup(self) -> None: ...        # spawn nodes, connect topology
    def run(self) -> None: ...          # post articles, record timestamps
    def wait_for_convergence(self) -> ConvergenceResult: ...
    def collect_metrics(self) -> Metrics: ...
    def teardown(self) -> None: ...     # terminate all, clean temp dirs
```

**`setup()`**
1. Spawn all `NodeProcess` instances in parallel (threads), wait for all to be ready
2. Call topology builder to get peer pairs
3. Establish all peer connections via `add_tcp_peer()`

**`run()`**
Posts `article_count` articles at `freq` articles/second. Articles are distributed randomly across nodes. Each post records `{message_id: PostRecord(posted_at, node_index, newsgroup)}`. Uses `time.sleep(1/freq)` between posts.

**`wait_for_convergence(timeout)`**
Polls all nodes every 0.5s. On each poll, fetches `list_article_ids()` from every node and checks whether the full set of posted `message_ids` is present. Records per-article `{message_id: first_seen_at_per_node}` for latency calculation. Returns when all nodes have all articles or `timeout` is reached.

**`collect_metrics()`**
Computes from recorded timestamps:
- Per-article propagation latency: time from `posted_at` to when the *last* node received it
- Overall convergence time: `convergence_at - first_post_at`
- Throughput: `article_count / convergence_time`
- Per-node coverage: articles received / articles posted
- Missing articles (if timeout): list with node breakdown

**`teardown()`**
Terminates all subprocesses and deletes all temp dirs, even if `run()` raised an exception (wrapped in try/finally).

---

### `metrics.py` — Report Formatting

Takes a `Metrics` object, prints a formatted report using `rich.table.Table`.

```
Simulation complete — 5 nodes · 100 articles · full-mesh · converged in 8.3s

Throughput:        12.0 articles/sec
Propagation:       p50 1.2s   p95 3.4s   max 5.1s

Node            Posted  Received  Coverage
sim-node-0          23       100     100%
sim-node-1          18       100     100%
sim-node-2          21       100     100%
sim-node-3          19       100     100%
sim-node-4          19       100     100%

All 100 articles propagated to all 5 nodes.
```

If convergence timed out, an additional section lists missing articles per node.

---

### `cli.py` — CLI

```
python simulate.py [options]

  --nodes N              Number of nodes (default: 5)
  --articles N           Articles to post before waiting for convergence (default: 100)
  --topology TOPOLOGY    full-mesh | sparse | hub-sparse (default: full-mesh)
  --sparse-k K           Peers per node for sparse/hub-sparse (default: 3)
  --hubs N               Hub node count for hub-sparse (default: 2)
  --freq F               Article posting rate in articles/sec (default: 2.0)
  --body-words RANGE     Body length as MIN-MAX words (default: 50-200)
  --newsgroups N         Number of simulated newsgroups (default: 3)
  --group-weights W...   Space-separated relative weights per group (default: uniform)
  --thread-prob P        Probability a post is a reply 0.0–1.0 (default: 0.3)
  --timeout S            Convergence timeout in seconds (default: 60)
  --base-port PORT       Starting port for nodes (default: 19000)
```

Running `python simulate.py` with no arguments runs a baseline: 5 nodes, 100 articles, full mesh, 2 articles/sec, 3 newsgroups uniform, 30% replies.

---

## SimulationConfig Dataclass

```python
@dataclass
class SimulationConfig:
    nodes: int = 5
    articles: int = 100
    topology: str = "full-mesh"       # full-mesh | sparse | hub-sparse
    sparse_k: int = 3
    hub_count: int = 2
    freq: float = 2.0
    body_words_min: int = 50
    body_words_max: int = 200
    newsgroups: int = 3
    group_weights: list[float] = field(default_factory=list)  # empty = uniform
    thread_prob: float = 0.3
    timeout: int = 60
    base_port: int = 19000
```

---

## Error Handling

- **Node fails to start:** `NodeProcess.wait_ready()` raises `TimeoutError` with node index. `Simulation.setup()` calls `teardown()` before re-raising.
- **Article post fails:** logged as a warning, counted as unposted, excluded from convergence check.
- **Convergence timeout:** simulation does not raise; returns `ConvergenceResult(timed_out=True)` and the report shows missing articles.
- **`teardown()` always runs** via try/finally in `Simulation.run()` wrapper in `cli.py`.

---

## What This Measures

The simulation makes these bottlenecks directly observable:

| Bottleneck | Signal |
|---|---|
| SQLite write contention | High p95 propagation latency under concurrent syncs |
| RNS channel message limits | Throughput drops with large bodies or many articles per session |
| Sync round-trip overhead | Latency gap between posting and first remote receipt |
| zlib CPU cost | Throughput ceiling on high-freq posting |
| Topology effects | Compare full-mesh vs hub-sparse convergence times |
| Thread depth | Convergence slowdown when `--thread-prob` is high |
| Newsgroup skew | Whether busy groups block quiet ones from syncing |
