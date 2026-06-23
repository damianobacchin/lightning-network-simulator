import math
import random

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np

from modules.config import config
from modules.errors import InsufficientBalanceError, NoRouteError
from modules.fees import calculate_fee
from modules.schema import LightningNetworkData, LightningPaymentData


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
                    },
                ),
                (
                    edge.nodes[1].id,
                    edge.nodes[0].id,
                    {
                        "balance": int(edge.capacity * (1 - balance_ratio)),
                        "fee_base": edge.nodes[1].fee_base,
                        "fee_rate": edge.nodes[1].fee_rate,
                    },
                ),
            ]
        )
        largest_connected_component = max(
            nx.strongly_connected_components(self.graph), key=len
        )
        self.graph = self.graph.subgraph(largest_connected_component).copy()

    def find_route(
        self, src: str, dst: str, amount: int
    ) -> tuple[list[str], int] | None:
        def routing_weight(_u, _v, data) -> float:
            if data.get("balance", 0) < amount:
                return math.inf
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

    def generate_payments(
        self, num_payments: int, avg_amount: float, recurrence_rate: float = 0
    ) -> list[LightningPaymentData]:
        nodes = list(self.graph.nodes())
        shape = 2.0
        scale = avg_amount / shape
        amounts = np.random.gamma(shape, scale, size=num_payments)

        paths: list[tuple[str, str]] = []
        for _ in range(int(num_payments * (1 - recurrence_rate))):
            source, target = random.sample(nodes, 2)
            paths.append((source, target))

        for _ in range(num_payments - len(paths)):
            source, target = random.choice(paths)
            paths.append((source, target))

        payments: list[LightningPaymentData] = []
        for i, path in enumerate(paths):
            payments.append(
                LightningPaymentData(
                    src=path[0], dst=path[1], amount=max(1, int(amounts[i]))
                )
            )

        random.shuffle(payments)
        return payments

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
