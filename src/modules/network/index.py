import matplotlib
import matplotlib.pyplot as plt
import networkx as nx

from modules.data.schema import Edge, Node
from modules.routing.fees import calculate_fee

matplotlib.use("Qt5Agg")


class LightningNetwork:
    def __init__(self):
        self.graph = nx.DiGraph()

    def find_route(
        self, source: str, target: str, amount: int
    ) -> tuple[list[str], int] | None:
        def weight(u, v, data):
            if data["capacity"] < amount:
                return None
            return calculate_fee(data["fee_base"], data["fee_rate"], amount)

        try:
            path = nx.dijkstra_path(self.graph, source, target, weight=weight)
        except nx.NetworkXNoPath:
            return None

        total_fee = 0
        for u, v in zip(path[:-1], path[1:]):
            data = self.graph[u][v]
            total_fee += calculate_fee(data["fee_base"], data["fee_rate"], amount)

        return path, total_fee

    def execute_payment(self, path: list[str], amount: int) -> None:
        hops = list(zip(path[:-1], path[1:]))

        fees = []
        for u, v in hops:
            data = self.graph[u][v]
            fees.append(calculate_fee(data["fee_base"], data["fee_rate"], amount))

        for i, (u, v) in enumerate(hops):
            flow = amount + sum(fees[i + 1:])
            self.graph[u][v]["capacity"] -= flow
            self.graph[v][u]["capacity"] += flow

    def add_node(self, node: Node):
        self.graph.add_node(node.id, alias=node.alias)

    def add_edge(self, edge: Edge):
        src, dst = edge.nodes[0], edge.nodes[1]
        balance = edge.capacity // 2

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
            capacity=balance,
            fee_base=dst.fee_base,
            fee_rate=dst.fee_rate,
        )

    def plot(self):
        pos = nx.nx_agraph.graphviz_layout(self.graph, prog="sfdp")
        labels = nx.get_node_attributes(self.graph, "alias")
        nx.draw(self.graph, pos, labels=labels, with_labels=True, node_color="skyblue")
        plt.show()
