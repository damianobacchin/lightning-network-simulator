import json
import random
import sys
from pathlib import Path

import networkx as nx
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from modules.data.schema import LightningNetworkData
from modules.network.index import LightningNetwork
from modules.utils.logger import logger

data_dir = Path(__file__).resolve().parents[3] / "data"


def graph_converter(input_path: str = "raw.json", output_path: str = "ln.json"):
    logger.info(f"Converting graph from {input_path}...")

    with open(data_dir / input_path) as f:
        raw = json.load(f)

    pub_key_to_id: dict[str, str] = {}
    nodes = []
    for i, node in enumerate(raw["nodes"], start=1):
        node_id = str(i)
        pub_key_to_id[node["pub_key"]] = node_id
        nodes.append({"id": node_id, "alias": node["alias"]})

    edges = []
    skipped = 0
    for edge in raw["edges"]:
        node1_pub = edge["node1_pub"]
        node2_pub = edge["node2_pub"]

        if node1_pub not in pub_key_to_id or node2_pub not in pub_key_to_id:
            skipped += 1
            continue

        node1_policy = edge.get("node1_policy")
        node2_policy = edge.get("node2_policy")

        if node1_policy is None or node2_policy is None:
            skipped += 1
            continue

        edges.append(
            {
                "nodes": [
                    {
                        "id": pub_key_to_id[node1_pub],
                        "fee_base": int(node1_policy["fee_base_msat"]),
                        "fee_rate": int(node1_policy["fee_rate_milli_msat"]),
                    },
                    {
                        "id": pub_key_to_id[node2_pub],
                        "fee_base": int(node2_policy["fee_base_msat"]),
                        "fee_rate": int(node2_policy["fee_rate_milli_msat"]),
                    },
                ],
                "capacity": int(edge["capacity"]),
            }
        )

    result = {"nodes": nodes, "edges": edges}

    logger.info(
        f"Converted {len(nodes)} nodes and {len(edges)} edges (skipped {skipped} edges)"
    )

    with open(data_dir / output_path, "w") as f:
        json.dump(result, f, indent=4)

    logger.info(f"Graph saved to {output_path}")


def generate_payments(
    num_payments: int,
    avg_amount: float,
    recurrence_rate: float = 0.2,
):
    network_path = "ln.json"
    output_path = "payments.json"

    logger.info(f"Generating {num_payments} payments with avg amount {avg_amount}...")

    with open(data_dir / network_path) as f:
        network = json.load(f)

    ln = nx.Graph()
    ln.add_nodes_from(node["id"] for node in network["nodes"])
    ln.add_edges_from(
        (edge["nodes"][0]["id"], edge["nodes"][1]["id"]) for edge in network["edges"]
    )

    if not nx.is_connected(ln):
        largest_cc = max(nx.connected_components(ln), key=len)
        ln = ln.subgraph(largest_cc).copy()
        logger.info(
            f"Graph is not fully connected. Keeping largest component with {ln.number_of_nodes()} nodes and {ln.number_of_edges()} edges."
        )

    node_ids = list(ln.nodes())

    shape = 2.0
    scale = avg_amount / shape
    amounts = np.random.gamma(shape, scale, size=num_payments)

    paths: list[tuple[str, str]] = []
    for _ in range(int(num_payments * (1 - recurrence_rate))):
        source, target = random.sample(node_ids, 2)
        paths.append((source, target))

    for _ in range(num_payments - len(paths)):
        source, target = random.choice(paths)
        paths.append((source, target))

    payments = []
    for i, path in enumerate(paths):
        payments.append(
            {"source": path[0], "target": path[1], "amount": max(1, int(amounts[i]))}
        )

    with open(data_dir / output_path, "w") as f:
        json.dump(payments, f, indent=4)

    logger.info(f"Payments saved to {output_path}")


def build_state(
    unbalance: float,
    network_path: str = "ln.json",
    output_path: str = "state.json",
    min_component_size: int = 4,
):
    logger.info(f"Building network state (unbalance_factor={unbalance})...")

    with open(data_dir / network_path) as f:
        data = LightningNetworkData(**json.load(f))

    network = LightningNetwork()
    for node in data.nodes:
        network.add_node(node)
    for edge in data.edges:
        network.add_edge(edge, unbalance)
    removed = network.prune_small_components(min_size=min_component_size)
    logger.info(
        f"Network built: {len(data.nodes)} nodes, {len(data.edges)} channels "
        f"({removed} nodes pruned from components < {min_component_size})"
    )

    network.save_state(data_dir / output_path)
    logger.info(f"State saved to {output_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        logger.error(
            "Usage:\n"
            "  python generator.py convert\n"
            "  python generator.py state <unbalance_factor>\n"
            "  python generator.py payments <num_transactions> <avg_amount>"
        )
        sys.exit(1)

    command = sys.argv[1]

    if command == "convert":
        graph_converter()
    elif command == "state":
        if len(sys.argv) < 3:
            logger.error("Usage: python generator.py state <unbalance_factor>")
            sys.exit(1)
        build_state(float(sys.argv[2]))
    elif command == "payments":
        if len(sys.argv) < 4:
            logger.error(
                "Usage: python generator.py payments "
                "<num_transactions> <avg_amount> <recurrence_rate>"
            )
            sys.exit(1)
        num_transactions = int(sys.argv[2])
        avg_amount = float(sys.argv[3])
        recurrence_rate = float(sys.argv[4]) if len(sys.argv) >= 5 else 0.2
        generate_payments(num_transactions, avg_amount, recurrence_rate)
    else:
        logger.error(f"Unknown command: {command}")
        sys.exit(1)
