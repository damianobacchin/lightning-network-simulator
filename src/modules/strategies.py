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

    def submarine_swap(self, rebalance_threshold: float = 0.2):
        rebalanced_channels = 0
        for node in self.network.graph.nodes():
            for channel in self.network.graph.out_edges(node, data=True):
                u, v, channel_out = channel
                channel_in = self.network.graph[v][u]

                lambda_in = channel_in.get("lambda", 0)
                lambda_out = channel_out.get("lambda", 0)
                lambda_tot = lambda_in + lambda_out
                if lambda_tot == 0:
                    continue

                capacity_in = channel_in.get("balance", 0)
                capacity_out = channel_out.get("balance", 0)
                channel_capacity = capacity_in + capacity_out

                rebalance_amount = capacity_out - (
                    lambda_out * channel_capacity / lambda_tot
                )

                if rebalance_amount < rebalance_threshold * channel_capacity:
                    continue
                else:
                    self.network.execute_payment(
                        path=[u, v], amount=int(rebalance_amount)
                    )
                    rebalanced_channels += 1

        logger.info(f"Rebalanced {rebalanced_channels} channels using submarine swaps.")
