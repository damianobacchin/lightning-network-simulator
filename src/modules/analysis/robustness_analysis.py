import sys
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from modules.network.index import LightningNetwork
from modules.utils.logger import logger

data_dir = Path(__file__).resolve().parents[3] / "data"


def _giant_component_metrics(graph: nx.Graph) -> tuple[int, int]:
    if graph.number_of_nodes() == 0:
        return 0, 0

    giant = max(nx.connected_components(graph), key=len)
    size = len(giant)
    if size <= 1:
        return size, 0

    diameter = nx.diameter(graph.subgraph(giant), usebounds=True)
    return size, diameter


def degree_attack_simulation(
    input_path: str = "ln.json",
    output_path: str = "ln_robustness_degree_attack.pdf",
    max_fraction: float = 0.5,
    step_fraction: float = 0.0025,
    recompute_degree: bool = False,
):
    ln = LightningNetwork.load_graph(data_dir / input_path)
    total_nodes = ln.number_of_nodes()

    order = [
        node
        for node, _ in sorted(
            nx.degree_centrality(ln).items(), key=lambda kv: kv[1], reverse=True
        )
    ]

    max_remove = int(max_fraction * total_nodes)
    batch = max(1, round(step_fraction * total_nodes))

    fractions: list[float] = []
    gc_sizes: list[float] = []
    diameters: list[int] = []

    def record(removed: int):
        size, diameter = _giant_component_metrics(ln)
        fractions.append(removed / total_nodes)
        gc_sizes.append(size / total_nodes)
        diameters.append(diameter)

    record(0)
    removed = 0
    while removed < max_remove:
        k = min(batch, max_remove - removed)
        if recompute_degree:
            ranked = sorted(ln.degree(), key=lambda kv: kv[1], reverse=True)
            targets = [node for node, _ in ranked[:k]]
        else:
            targets = order[removed : removed + k]
        ln.remove_nodes_from(targets)
        removed += k
        record(removed)
        if len(fractions) % 20 == 0:
            logger.info(
                f"Removed {removed}/{total_nodes} nodes "
                f"({removed / total_nodes:.0%}) | "
                f"giant component {gc_sizes[-1]:.3f}N | diameter {diameters[-1]}"
            )

    logger.info(
        f"Degree attack complete: {len(fractions)} samples, "
        f"removed up to {fractions[-1]:.0%} of {total_nodes} nodes"
    )

    fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True, figsize=(9, 7))

    ax1.plot(fractions, gc_sizes, color="steelblue", lw=1.8)
    ax1.set_ylabel("Giant component size (fraction of N)")
    ax1.grid(True, ls="--", alpha=0.3)
    ax1.set_ylim(bottom=0)

    ax2.plot(fractions, diameters, color="firebrick", lw=1.8)
    ax2.set_ylabel("Giant component diameter")
    ax2.set_xlabel("Fraction of nodes removed (highest degree first)")
    ax2.grid(True, ls="--", alpha=0.3)
    ax2.set_ylim(bottom=0)

    fig.tight_layout()
    out = data_dir / output_path
    fig.savefig(out, format="pdf", bbox_inches="tight")
    plt.show()


if __name__ == "__main__":
    degree_attack_simulation()
