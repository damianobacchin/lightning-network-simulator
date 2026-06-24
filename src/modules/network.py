import math

import matplotlib.pyplot as plt
import networkx as nx

from modules.config import config
from modules.errors import InsufficientBalanceError, NoRouteError
from modules.fees import calculate_fee
from modules.schema import LightningNetworkData


class LightningNetwork:
    def __init__(
        self, data: LightningNetworkData, balance_ratio: float = config.balance_ratio
    ):
        self.graph = nx.DiGraph()
        self.graph.add_nodes_from((node.id, node.model_dump()) for node in data.nodes)
        self.graph.add_edges_from(
            direction
            for edge in data.edges
            for direction in [
                (
                    edge.nodes[0].id,
                    edge.nodes[1].id,
                    {
                        "balance": int(edge.capacity * balance_ratio),
                        "fee_base": edge.nodes[0].fee_base,
                        "fee_rate": edge.nodes[0].fee_rate,
                        "lambda": 0,
                    },
                ),
                (
                    edge.nodes[1].id,
                    edge.nodes[0].id,
                    {
                        "balance": int(edge.capacity * (1 - balance_ratio)),
                        "fee_base": edge.nodes[1].fee_base,
                        "fee_rate": edge.nodes[1].fee_rate,
                        "lambda": 0,
                    },
                ),
            ]
        )
        largest_connected_component = max(
            nx.strongly_connected_components(self.graph), key=len
        )
        self.graph = self.graph.subgraph(largest_connected_component).copy()

    def find_route(
        self, src: str, dst: str, amount: int, simulation: bool = False
    ) -> tuple[list[str], int] | None:
        def routing_weight(_u, _v, data) -> float:
            channel_capacity = data.get("balance", 0) + self.graph[_v][_u].get(
                "balance", 0
            )
            if simulation and channel_capacity < amount:
                return math.inf
            elif not simulation and data.get("balance", 0) < amount:
                return math.inf
            else:
                return calculate_fee(
                    data.get("fee_base", 0), data.get("fee_rate", 0), amount
                )

        try:
            path = nx.shortest_path(
                self.graph, source=src, target=dst, weight=routing_weight
            )
            if any(
                self.graph[path[i]][path[i + 1]]["balance"] < amount
                for i in range(len(path) - 1)
            ):
                raise InsufficientBalanceError()
            total_fee = sum(
                calculate_fee(
                    self.graph[path[i]][path[i + 1]]["fee_base"],
                    self.graph[path[i]][path[i + 1]]["fee_rate"],
                    amount,
                )
                for i in range(len(path) - 1)
            )
            return path, total_fee
        except (nx.NetworkXNoPath, NoRouteError, InsufficientBalanceError):
            return None

    def find_circular_route(
        self, src_channel: tuple[str, str], dst_channel: tuple[str, str], amount: int
    ) -> tuple[list[str], int] | None:
        if (
            self.graph[src_channel[0]][src_channel[1]]["balance"] < amount
            or self.graph[dst_channel[0]][dst_channel[1]]["balance"] < amount
        ):
            return None
        route = self.find_route(src_channel[1], dst_channel[0], amount)
        if route is not None:
            path, total_fee = route
            path = [src_channel[0]] + path + [dst_channel[1]]
            return path, total_fee
        else:
            return None

    def execute_payment(self, path: list[str], amount: int) -> None:
        hops = list(zip(path[:-1], path[1:]))
        fees: list[int] = []

        for u, v in hops:
            channel = self.graph[u][v]
            fees.append(
                calculate_fee(
                    channel["fee_base"],
                    channel["fee_rate"],
                    amount,
                )
            )

        for i, (u, v) in enumerate(hops):
            flow = amount + sum(fees[i + 1 :])
            self.graph[u][v]["balance"] -= flow
            self.graph[v][u]["balance"] += flow

    def network_connectivity(self) -> tuple[float, list[float]]:
        undirected_graph = self.graph.to_undirected()
        core_graph = nx.k_core(undirected_graph, k=5)
        lambda_2 = nx.algebraic_connectivity(core_graph)
        fiedler_vector = nx.fiedler_vector(core_graph)
        return lambda_2, fiedler_vector.tolist()

    def plot(self, _labels: bool = True):
        pos = nx.nx_agraph.graphviz_layout(self.graph, prog="sfdp")
        labels = nx.get_node_attributes(self.graph, "id")
        nx.draw(
            self.graph,
            pos,
            labels=labels if _labels else None,
            with_labels=_labels,
            node_color="skyblue",
        )
        plt.show()
