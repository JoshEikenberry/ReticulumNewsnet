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
