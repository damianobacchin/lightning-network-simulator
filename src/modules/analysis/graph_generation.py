import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
from matplotlib.cm import ScalarMappable
from matplotlib.colors import LogNorm

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from modules.network.index import LightningNetwork
from modules.utils.logger import logger

data_dir = Path(__file__).resolve().parents[3] / "data"


def _choose_targets(rng, degrees, is_leaf, n_existing, alpha, m):
    candidates = np.nonzero(~is_leaf[:n_existing])[0]
    weights = degrees[candidates] ** alpha
    total = weights.sum()
    if total > 0:
        probs = weights / total
    else:
        probs = np.full(len(candidates), 1.0 / len(candidates))

    if int(np.count_nonzero(probs)) >= m:
        return candidates[rng.choice(len(candidates), size=m, replace=False, p=probs)]

    forced = np.nonzero(probs)[0]
    pool = np.nonzero(probs == 0)[0]
    extra = rng.choice(pool, size=m - len(forced), replace=False)
    return candidates[np.concatenate([forced, extra])]


def generate_graph(
    nodes: int = 1000,
    edges: int = 3000,
    alpha: float = 1.0,
    leaf_fraction: float = 0.5,
    n0: int = 6,
    output_path: str = "ba.json",
) -> nx.Graph:
    if not 0.0 <= leaf_fraction < 1.0:
        raise ValueError(f"leaf_fraction must be in [0, 1), got {leaf_fraction}")
    if nodes <= n0:
        raise ValueError(f"nodes ({nodes}) must be greater than n0 ({n0})")

    t = nodes - n0
    n_leaf = round(leaf_fraction * nodes)
    n_core = t - n_leaf
    if n_core < 1:
        raise ValueError(f"leaf_fraction ({leaf_fraction}) too high; no core nodes left")

    base, rem = divmod(edges - n_leaf, n_core)
    if base < 1 or base + 1 > n0:
        raise ValueError(
            f"infeasible edge budget: core nodes need {base}..{base + 1} edges, "
            f"must stay within 1..{n0}; adjust edges, leaf_fraction, nodes or n0"
        )

    rng = np.random.default_rng(42)

    attach = np.empty(t, dtype=int)
    leaf_step = np.zeros(t, dtype=bool)
    attach[:n_leaf] = 1
    leaf_step[:n_leaf] = True
    attach[n_leaf : n_leaf + rem] = base + 1
    attach[n_leaf + rem :] = base
    perm = rng.permutation(t)
    attach, leaf_step = attach[perm], leaf_step[perm]

    graph = nx.Graph()
    graph.add_nodes_from(str(i) for i in range(1, n0 + 1))
    degrees = np.zeros(nodes, dtype=float)
    is_leaf = np.zeros(nodes, dtype=bool)

    for step, new_pos in enumerate(range(n0, nodes)):
        m = int(attach[step])
        targets = _choose_targets(rng, degrees, is_leaf, new_pos, alpha, m)

        new_id = str(new_pos + 1)
        graph.add_node(new_id)
        for pos in targets:
            graph.add_edge(new_id, str(int(pos) + 1))

        degrees[new_pos] = m
        degrees[targets] += 1.0
        is_leaf[new_pos] = leaf_step[step]

    degree_one = sum(1 for _, d in graph.degree() if d == 1)
    logger.info(
        f"Barabasi-Albert graph (alpha={alpha}, leaf_fraction={leaf_fraction}): "
        f"{graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges, "
        f"{degree_one} of degree 1"
    )

    _write_ln_json(graph, output_path)
    return graph


def _write_ln_json(graph: nx.Graph, output_path: str) -> None:
    nodes = [{"id": node} for node in graph.nodes()]
    edges = [{"nodes": [{"id": u}, {"id": v}]} for u, v in graph.edges()]

    out = data_dir / output_path
    with open(out, "w") as f:
        json.dump({"nodes": nodes, "edges": edges}, f, indent=4)
    logger.info(f"Graph saved to {out}")


def plot_graph(
    input_path: str = "ba.json",
    output_path: str = "ba.pdf",
):
    ln = LightningNetwork.load_graph(data_dir / input_path)

    largest_cc = max(nx.connected_components(ln), key=len)
    ln_cc = ln.subgraph(largest_cc).copy()

    degrees = dict(ln_cc.degree())
    node_values = [degrees[node] for node in ln_cc.nodes()]
    pos = nx.nx_agraph.graphviz_layout(ln_cc, prog="sfdp")

    norm = LogNorm(vmin=max(1, min(node_values)), vmax=max(node_values))
    cmap = plt.get_cmap("viridis")
    node_colors = cmap(norm(node_values))
    node_sizes = [10 + 5 * d for d in node_values]

    plt.figure(figsize=(16, 9))
    nx.draw_networkx_nodes(
        ln_cc,
        pos,
        node_size=node_sizes,
        node_color=node_colors,
        alpha=0.85,
    )
    nx.draw_networkx_edges(ln_cc, pos, width=0.15, alpha=0.5, edge_color="gray")
    sm = ScalarMappable(norm=norm, cmap=cmap)
    sm.set_array([])
    plt.colorbar(sm, ax=plt.gca(), label="Degree", fraction=0.025, pad=0.01)
    plt.axis("off")
    plt.tight_layout()

    out = data_dir / output_path
    plt.savefig(out, format="pdf", bbox_inches="tight")
    plt.show()


if __name__ == "__main__":
    generate_graph(nodes=13000, edges=32000, alpha=0.5, leaf_fraction=0.2, n0=20)
    plot_graph()
