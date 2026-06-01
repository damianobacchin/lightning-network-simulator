import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx
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


if __name__ == "__main__":
    plot_graph()
