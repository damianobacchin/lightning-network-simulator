import sys
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from modules.network.index import LightningNetwork
from modules.utils.logger import logger

data_dir = Path(__file__).resolve().parents[3] / "data"

strategy_colors = {
    "degree": "steelblue",
    "betweenness": "firebrick",
    "random": "seagreen",
}


def _giant_component_metrics(graph: nx.Graph) -> tuple[int, int]:
    if graph.number_of_nodes() == 0:
        return 0, 0

    giant = max(nx.connected_components(graph), key=len)
    size = len(giant)
    if size <= 1:
        return size, 0

    giant_graph = graph.subgraph(giant).copy()
    diameter = nx.diameter(giant_graph, usebounds=True)
    return size, diameter


def _attack_order(
    graph: nx.Graph, strategy: str, betweenness_sample: int, seed: int
) -> list:
    if strategy == "random":
        nodes = list(graph.nodes())
        idx = np.random.default_rng(seed).permutation(len(nodes))
        return [nodes[i] for i in idx]

    if strategy == "degree":
        ranking = nx.degree_centrality(graph)
    elif strategy == "betweenness":
        k = min(betweenness_sample, graph.number_of_nodes())
        ranking = nx.betweenness_centrality(graph, k=k, seed=seed)
    else:
        raise ValueError(
            f"Unknown strategy: {strategy!r} (use 'degree', 'betweenness' or 'random')"
        )

    return [n for n, _ in sorted(ranking.items(), key=lambda kv: kv[1], reverse=True)]


def _simulate_attack(
    graph: nx.Graph, order: list, max_remove: int, batch: int
) -> tuple[list[float], list[float], list[int]]:
    g = graph.copy()
    total = graph.number_of_nodes()
    fractions: list[float] = []
    gc_sizes: list[float] = []
    diameters: list[int] = []

    def record(removed: int):
        size, diameter = _giant_component_metrics(g)
        fractions.append(removed / total)
        gc_sizes.append(size / total)
        diameters.append(diameter)

    record(0)
    removed = 0
    while removed < max_remove:
        k = min(batch, max_remove - removed)
        g.remove_nodes_from(order[removed : removed + k])
        removed += k
        record(removed)
    return fractions, gc_sizes, diameters


def attack_simulation(
    input_path: str = "ln.json",
    output_path: str = "ln_robustness_attacks.pdf",
    strategies: tuple[str, ...] = ("degree", "betweenness", "random"),
    max_fraction: float = 0.5,
    step_fraction: float = 0.0025,
    betweenness_sample: int = 500,
    seed: int = 42,
):
    ln = LightningNetwork.load_graph(data_dir / input_path)
    total_nodes = ln.number_of_nodes()
    max_remove = int(max_fraction * total_nodes)
    batch = max(1, round(step_fraction * total_nodes))

    results: dict[str, tuple[list[float], list[float], list[int]]] = {}
    for strategy in strategies:
        logger.info(f"Ranking {total_nodes} nodes for the {strategy} attack...")
        order = _attack_order(ln, strategy, betweenness_sample, seed)
        fractions, gc_sizes, diameters = _simulate_attack(ln, order, max_remove, batch)
        results[strategy] = (fractions, gc_sizes, diameters)
        logger.info(
            f"{strategy} attack done: {len(fractions)} samples, "
            f"final giant component {gc_sizes[-1]:.3f}N, diameter {diameters[-1]}"
        )

    fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True, figsize=(9, 7))
    for strategy, (fractions, gc_sizes, diameters) in results.items():
        color = strategy_colors.get(strategy)
        ax1.plot(fractions, gc_sizes, color=color, lw=1.8, label=strategy.capitalize())
        ax2.plot(fractions, diameters, color=color, lw=1.8, label=strategy.capitalize())

    ax1.set_ylabel("Giant component size (fraction of N)")
    ax1.grid(True, ls="--", alpha=0.3)
    ax1.set_ylim(bottom=0)
    ax1.legend()

    ax2.set_ylabel("Giant component diameter")
    ax2.set_xlabel("Fraction of nodes removed")
    ax2.grid(True, ls="--", alpha=0.3)
    ax2.set_ylim(bottom=0)

    fig.tight_layout()
    out = data_dir / output_path
    fig.savefig(out, format="pdf", bbox_inches="tight")
    plt.show()


if __name__ == "__main__":
    attack_simulation()
