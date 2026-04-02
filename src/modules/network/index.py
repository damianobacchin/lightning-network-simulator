import matplotlib
import matplotlib.pyplot as plt
import networkx as nx

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
        except nx.NetworkXNoPath:
            raise NoRouteError(f"No route from {source} to {target}")

        for i, path in enumerate(nx.shortest_simple_paths(self.graph, source, target)):
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
