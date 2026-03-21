from __future__ import annotations
from dataclasses import dataclass, field


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
