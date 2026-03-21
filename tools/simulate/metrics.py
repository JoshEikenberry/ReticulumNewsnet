from __future__ import annotations
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
