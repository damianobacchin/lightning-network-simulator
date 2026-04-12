import json
import random
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

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
    num_transactions: int,
    avg_amount: float,
    network_path: str = "ln.json",
    output_path: str = "payments.json",
    shape: float = 2.0,
):
    logger.info(
        f"Generating {num_transactions} payments with avg amount {avg_amount}..."
    )

    with open(data_dir / network_path) as f:
        network = json.load(f)

    node_ids = [node["id"] for node in network["nodes"]]
    logger.info(f"Loaded {len(node_ids)} nodes from {network_path}")

    scale = avg_amount / shape
    amounts = np.random.gamma(shape, scale, size=num_transactions)

    payments = []
    for amount in amounts:
        source, target = random.sample(node_ids, 2)
        payments.append(
            {"source": source, "target": target, "amount": max(1, int(amount))}
        )

    with open(data_dir / output_path, "w") as f:
        json.dump(payments, f, indent=4)

    logger.info(f"Payments saved to {output_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        logger.error(
            "Usage:\n  python generator.py convert\n  python generator.py payments <num_transactions> <avg_amount>"
        )
        sys.exit(1)

    command = sys.argv[1]

    if command == "convert":
        graph_converter()
    elif command == "payments":
        if len(sys.argv) < 4:
            logger.error(
                "Usage: python generator.py payments <num_transactions> <avg_amount>"
            )
            sys.exit(1)
        num_transactions = int(sys.argv[2])
        avg_amount = float(sys.argv[3])
        generate_payments(num_transactions, avg_amount)
    else:
        logger.error(f"Unknown command: {command}")
        sys.exit(1)
