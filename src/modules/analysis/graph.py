import json
import sys
from collections import Counter
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


def plot_graph(
    input_path: str = "ln.json",
    output_path: str = "ln_degree_heatmap.pdf",
):
    ln = LightningNetwork.load_graph(data_dir / input_path)

    largest_cc = max(nx.connected_components(ln), key=len)
    ln_cc = ln.subgraph(largest_cc).copy()

    degrees = dict(ln_cc.degree())
    node_values = [degrees[node] for node in ln_cc.nodes()]
    pos = nx.nx_agraph.graphviz_layout(ln_cc, prog="sfdp")

    vmin = max(1, min(node_values))
    vmax = max(node_values)
    norm = LogNorm(vmin=vmin, vmax=vmax)
    cmap = plt.get_cmap("viridis")
    node_colors = cmap(norm(node_values))

    plt.figure(figsize=(16, 9))
    nx.draw_networkx_nodes(
        ln_cc,
        pos,
        node_size=5,
        node_color=node_colors,
        alpha=0.7,
    )
    nx.draw_networkx_edges(ln_cc, pos, width=0.1, alpha=0.9, edge_color="black")
    sm = ScalarMappable(norm=norm, cmap=cmap)
    sm.set_array([])
    plt.axis("off")
    plt.tight_layout()

    out = data_dir / output_path
    plt.savefig(out, format="pdf", bbox_inches="tight")
    plt.show()


def graph_statistics(
    input_path: str = "ln.json",
):
    path = data_dir / input_path
    ln = LightningNetwork.load_graph(path)

    with open(path) as f:
        data = json.load(f)

    total_channels = len(data["edges"])
    network_capacity = sum(e["capacity"] for e in data["edges"])

    total_nodes = ln.number_of_nodes()
    degrees = [d for _, d in ln.degree()]
    avg_degree = sum(degrees) / total_nodes
    avg_weighted_degree = 2 * total_channels / total_nodes

    largest_cc = max(nx.connected_components(ln), key=len)
    ln_cc = ln.subgraph(largest_cc)
    diameter = nx.diameter(ln_cc)

    logger.info(f"Total nodes: {total_nodes}")
    logger.info(f"Total channels: {total_channels}")
    logger.info(f"Density: {nx.density(ln):.6f}")
    logger.info(f"Network capacity: {network_capacity} sat")
    logger.info(f"Diameter: {diameter}")
    logger.info(f"Average node degree: {avg_degree:.4f}")
    logger.info(f"Average weighted degree: {avg_weighted_degree:.4f}")
    logger.info(f"Average clustering coefficient: {nx.average_clustering(ln):.4f}")
    logger.info(
        f"Assortativity coefficient: {nx.degree_assortativity_coefficient(ln):.4f}"
    )


def avg_neighbor_degree(input_path: str = "ln.json"):
    path = data_dir / input_path
    ln = LightningNetwork.load_graph(path)

    knn = nx.average_degree_connectivity(ln)

    k_values = sorted(knn.keys())
    knn_values = [knn[k] for k in k_values]

    plt.figure(figsize=(7, 5))
    plt.scatter(
        k_values,
        knn_values,
        alpha=0.6,
        color="dodgerblue",
        edgecolor="black",
        s=40,
    )
    plt.xscale("log")
    plt.yscale("log")
    plt.xlabel("Degree (k)")
    plt.ylabel(r"Average Neighbor Degree $\langle k_{nn} \rangle$")
    plt.grid(True, which="both", ls="--", alpha=0.3)
    plt.tight_layout()
    plt.show()


def degree_distribution(input_path: str = "ln.json"):
    path = data_dir / input_path
    ln = LightningNetwork.load_graph(path)

    plt.figure(figsize=(7, 4))

    degree_cent = list(nx.degree_centrality(ln).values())

    plt.hist(degree_cent, bins=50, color="steelblue", edgecolor="black", alpha=0.7)
    plt.grid(True, which="both", alpha=0.3)
    plt.xlabel("Degree Centrality")
    plt.ylabel("Frequency")
    plt.semilogy()
    plt.tight_layout()
    plt.show()


def power_law_fit(
    input_path: str = "ln.json",
    metric: str = "degree",
    log_binning: bool = False,
    k: int | None = 500,
):
    path = data_dir / input_path
    ln = LightningNetwork.load_graph(path)

    if metric == "degree":
        values = [d for _, d in ln.degree() if d > 0]
        xlabel, ylabel = "k (log)", "P(k) (log)"
    elif metric == "betweenness":
        sample = k if k is None else min(k, ln.number_of_nodes())
        betweenness = nx.betweenness_centrality(ln, k=sample, seed=42)
        values = [b for b in betweenness.values() if b > 0]
        log_binning = True
        xlabel, ylabel = "Betweenness centrality (log)", "P(b) (log)"
    else:
        raise ValueError(f"Unknown metric: {metric!r} (use 'degree' or 'betweenness')")

    if log_binning:
        bins = np.logspace(np.log10(min(values)), np.log10(max(values)), num=20)
        counts, bin_edges = np.histogram(values, bins=bins, density=True)
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2

        nonzero = counts > 0
        x = np.log10(bin_centers[nonzero])
        y = np.log10(counts[nonzero])
        label = "Data with log-binning"
    else:
        value_counts = Counter(values)
        v = np.array(list(value_counts.keys()))
        pv = np.array(list(value_counts.values()))
        x = np.log10(v)
        y = np.log10(pv)
        label = "LN data (log-log)"

    m, c = np.polyfit(x, y, 1)
    gamma = -m
    logger.info(f"Power-law exponent for {metric} (gamma): {gamma:.4f}")

    plt.figure(figsize=(8, 5))
    plt.scatter(x, y, alpha=0.5, label=label)
    plt.plot(x, m * x + c, color="red", label=f"Linear fit (gamma={gamma:.2f})")
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.grid(True, which="both", ls="--", alpha=0.3)
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    power_law_fit(log_binning=True)
