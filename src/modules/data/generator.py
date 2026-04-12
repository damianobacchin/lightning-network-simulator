import json
from pathlib import Path

data_dir = Path(__file__).resolve().parents[3] / "data"


def graph_converter(input_path: str = "raw.json", output_path: str = "ln.json"):
    with open(data_dir / input_path) as f:
        raw = json.load(f)

    pub_key_to_id: dict[str, str] = {}
    nodes = []
    for i, node in enumerate(raw["nodes"], start=1):
        node_id = str(i)
        pub_key_to_id[node["pub_key"]] = node_id
        nodes.append({"id": node_id, "alias": node["alias"]})

    edges = []
    for edge in raw["edges"]:
        node1_pub = edge["node1_pub"]
        node2_pub = edge["node2_pub"]

        if node1_pub not in pub_key_to_id or node2_pub not in pub_key_to_id:
            continue

        node1_policy = edge.get("node1_policy")
        node2_policy = edge.get("node2_policy")

        if node1_policy is None or node2_policy is None:
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

    with open(data_dir / output_path, "w") as f:
        json.dump(result, f, indent=4)


if __name__ == "__main__":
    graph_converter()
