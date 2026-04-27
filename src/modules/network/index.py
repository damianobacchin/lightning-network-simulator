import json
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np

from modules.data.schema import Edge, Node
from modules.routing.errors import InsufficientBalanceError, NoRouteError
from modules.routing.fees import calculate_fee

matplotlib.use("Qt5Agg")


class LightningNetwork:
    def __init__(self):
        self.graph = nx.DiGraph()

    def find_route(
        self, source: str, target: str, amount: int, max_attempts: int = 10
    ) -> tuple[list[str], int]:
        try:
            nx.dijkstra_path(self.graph, source, target)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            raise NoRouteError(f"No route from {source} to {target}")

        def capacity_weight(u, v, d):
            cap = d.get("capacity", 0)
            return 1.0 / cap if cap > 0 else float("inf")

        for i, path in enumerate(
            nx.shortest_simple_paths(
                self.graph, source, target, weight=capacity_weight
            )
        ):
            if i >= max_attempts:
                break
            hops = list(zip(path[:-1], path[1:]))
            if all(self.graph[u][v]["capacity"] >= amount for u, v in hops):
                total_fee = sum(
                    calculate_fee(
                        self.graph[u][v]["fee_base"],
                        self.graph[u][v]["fee_rate"],
                        amount,
                    )
                    for u, v in hops
                )
                return path, total_fee

        raise InsufficientBalanceError(
            f"Route from {source} to {target} exists but channels lack sufficient balance for {amount} sats"
        )

    def find_multipath_route(
        self,
        source: str,
        target: str,
        amount: int,
        max_splits: int = 3,
    ) -> list[tuple[list[str], int, int]]:
        try:
            path, fee = self.find_route(source, target, amount)
            return [(path, amount, fee)]
        except InsufficientBalanceError:
            pass

        original_graph = self.graph
        try:
            for n in range(1, max_splits + 1):
                parts = 2**n
                if amount < parts:
                    break
                base = amount // parts
                remainder = amount - base * parts

                self.graph = original_graph.copy()
                try:
                    routes: list[tuple[list[str], int, int]] = []
                    for i in range(parts):
                        part_amount = base + (1 if i < remainder else 0)
                        path, fee = self.find_route(source, target, part_amount)
                        routes.append((path, part_amount, fee))
                        for u, v in zip(path[:-1], path[1:]):
                            self.graph[u][v]["capacity"] -= part_amount
                    return routes
                except InsufficientBalanceError:
                    continue
        finally:
            self.graph = original_graph

        raise InsufficientBalanceError(
            f"Cannot route {amount} sats from {source} to {target} even splitting into {2**max_splits} parts"
        )

    def execute_payment(self, path: list[str], amount: int) -> None:
        hops = list(zip(path[:-1], path[1:]))

        fees = []
        for u, v in hops:
            data = self.graph[u][v]
            fees.append(calculate_fee(data["fee_base"], data["fee_rate"], amount))

        for i, (u, v) in enumerate(hops):
            flow = amount + sum(fees[i + 1 :])
            self.graph[u][v]["capacity"] -= flow
            self.graph[v][u]["capacity"] += flow

    def prune_small_components(self, min_size: int = 4) -> int:
        components = list(nx.weakly_connected_components(self.graph))
        to_remove = [
            node for comp in components if len(comp) < min_size for node in comp
        ]
        self.graph.remove_nodes_from(to_remove)
        return len(to_remove)

    def add_node(self, node: Node):
        self.graph.add_node(node.id, alias=node.alias)

    def add_edge(self, edge: Edge, unbalance: float = 1.0):
        src, dst = edge.nodes[0], edge.nodes[1]

        alpha = beta = unbalance
        percentage = np.random.beta(alpha, beta)

        balance = round(edge.capacity * percentage)

        self.graph.add_edge(
            src.id,
            dst.id,
            capacity=balance,
            fee_base=src.fee_base,
            fee_rate=src.fee_rate,
        )
        self.graph.add_edge(
            dst.id,
            src.id,
            capacity=edge.capacity - balance,
            fee_base=dst.fee_base,
            fee_rate=dst.fee_rate,
        )

    def save_state(self, path: str | Path) -> None:
        nodes = [
            {"id": n, "alias": d.get("alias", "")}
            for n, d in self.graph.nodes(data=True)
        ]
        edges = [
            {
                "u": u,
                "v": v,
                "capacity": d["capacity"],
                "fee_base": d["fee_base"],
                "fee_rate": d["fee_rate"],
            }
            for u, v, d in self.graph.edges(data=True)
        ]
        with open(path, "w") as f:
            json.dump({"nodes": nodes, "edges": edges}, f)

    def load_state(self, path: str | Path) -> None:
        with open(path) as f:
            state = json.load(f)
        self.graph = nx.DiGraph()
        for n in state["nodes"]:
            self.graph.add_node(n["id"], alias=n.get("alias", ""))
        for e in state["edges"]:
            self.graph.add_edge(
                e["u"],
                e["v"],
                capacity=e["capacity"],
                fee_base=e["fee_base"],
                fee_rate=e["fee_rate"],
            )

    def plot(self):
        pos = nx.nx_agraph.graphviz_layout(self.graph, prog="sfdp")
        labels = nx.get_node_attributes(self.graph, "alias")
        nx.draw(self.graph, pos, labels=labels, with_labels=True, node_color="skyblue")
        plt.show()
