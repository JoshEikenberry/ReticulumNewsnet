from __future__ import annotations

import random
import threading
import time

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

    def teardown(self) -> None:
        """Terminate all subprocesses and clean up temp dirs."""
        for node in self.nodes:
            try:
                node.close()
            except Exception:
                pass
