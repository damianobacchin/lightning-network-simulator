from collections import defaultdict

from modules.logger import logger
from modules.network import LightningNetwork
from modules.simulation import Simulation


class RebalancingStrategy:
    def __init__(self, network: LightningNetwork, simulation: Simulation):
        self.network = network
        self.simulation = simulation

    def analyze_payments(self):
        channels_usage: dict[tuple[str, str], int] = defaultdict(lambda: 0)
        for payment in self.simulation.payments:
            route = self.network.find_route(
                payment.src, payment.dst, payment.amount, simulation=True
            )
            if route is None:
                continue
            path, _ = route
            for u, v in zip(path[:-1], path[1:]):
                channels_usage[(u, v)] += payment.amount

        for (u, v), amount in channels_usage.items():
            self.network.graph[u][v]["lambda"] = amount

    def submarine_swap(self, threshold: int = 100):
        graph = self.network.graph
        rebalanced_channels = 0
        for node in graph.nodes():
            if graph.out_degree(node) < 2:
                continue
            net_flow = {
                v: data["lambda"] - graph[v][node]["lambda"]
                for _, v, data in graph.out_edges(node, data=True)
            }
            capital = sum(graph[node][v]["balance"] for v in net_flow)
            total_imbalance = sum(abs(f) for f in net_flow.values()) or 1
            delta = {v: capital * f // total_imbalance for v, f in net_flow.items()}
            deficits = sorted(
                (v for v in delta if delta[v] > 0), key=lambda v: -delta[v]
            )
            surpluses = sorted(
                (v for v in delta if delta[v] < 0), key=lambda v: delta[v]
            )
            for deficit, surplus in zip(deficits, surpluses):
                amount = min(
                    delta[deficit],
                    -delta[surplus],
                    graph[node][surplus]["balance"],
                    graph[deficit][node]["balance"],
                )
                if amount < threshold:
                    continue
                graph[node][deficit]["balance"] += amount
                graph[deficit][node]["balance"] -= amount
                graph[node][surplus]["balance"] -= amount
                graph[surplus][node]["balance"] += amount

                rebalanced_channels += 1

        logger.info(f"Rebalanced {rebalanced_channels} channels using submarine swaps.")
