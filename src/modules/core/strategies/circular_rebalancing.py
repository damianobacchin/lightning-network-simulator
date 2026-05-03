from typing import Optional

from networkx import dijkstra_path

from modules.data.schema import LightningPaymentData
from modules.network.index import LightningNetwork
from modules.routing.errors import InsufficientBalanceError, NoRouteError
from modules.utils.logger import logger


class CircularRebalancing:
    def __init__(
        self,
        lightning_network: LightningNetwork,
        payments: Optional[list[LightningPaymentData]] = None,
    ):
        self.network = lightning_network
        self.graph = lightning_network.graph
        self.payments = payments
        self.channels_usage: dict[tuple[str, str], int] = dict()

    def analyze_payments(self):
        logger.info("Analyzing channels usage for circular rebalancing...")
        for payment in self.payments or []:
            path = dijkstra_path(self.graph, payment.src, payment.dst)
            for u, v in zip(path[:-1], path[1:]):
                self.channels_usage[(u, v)] = (
                    self.channels_usage.get((u, v), 0) + payment.amount
                )
        logger.info("Channel usage analysis complete.")

    def apply_rebalancing(self):
        logger.info("Applying circular rebalancing strategy...")
        if not self.channels_usage:
            self.analyze_payments()

        rebalance_count = 0
        graph_nodes = self.graph.number_of_nodes()

        for i, node in enumerate(list(self.graph.nodes())):
            print(f"Processing node {i + 1}/{graph_nodes} for circular rebalancing...")
            if self.graph.out_degree(node) < 2:
                continue

            out_channels = list(self.graph.out_edges(node, data=True))
            total_capacity = sum(data["capacity"] for _, _, data in out_channels)
            total_usage = sum(
                self.channels_usage.get((u, v), 0) for u, v, _ in out_channels
            )

            if total_usage == 0 or total_capacity == 0:
                continue

            excesses: list[tuple[tuple[str, str], int]] = []
            for u, v, data in out_channels:
                channel_usage = self.channels_usage.get((u, v), 0)
                optimal_capacity = int(total_capacity * channel_usage / total_usage)
                excess = data["capacity"] - optimal_capacity
                excesses.append(((u, v), excess))

            over_usage = sorted(
                [(c, e) for c, e in excesses if e > 0], key=lambda x: -x[1]
            )
            under_usage = [
                [c, e]
                for c, e in sorted(
                    [(c, e) for c, e in excesses if e < 0], key=lambda x: x[1]
                )
            ]

            for src_channel, src_excess in over_usage:
                remaining = src_excess
                for entry in under_usage:
                    dst_channel, dst_deficit = entry
                    if dst_deficit >= 0 or remaining <= 0:
                        continue
                    amount = min(remaining, -dst_deficit)
                    if amount <= 5000:
                        continue
                    try:
                        path, _ = self.network.find_circular_route(
                            src_channel, dst_channel, amount
                        )
                        self.network.execute_payment(path, amount)
                        rebalance_count += 1
                        remaining -= amount
                        entry[1] = dst_deficit + amount
                        logger.info(
                            f"Rebalanced {amount} sats on node {node}: "
                            f"{src_channel[0]}-{src_channel[1]} -> {dst_channel[0]}-{dst_channel[1]}"
                        )
                    except (NoRouteError, InsufficientBalanceError) as e:
                        logger.debug(
                            f"Skip rebalance {src_channel} -> {dst_channel}: {e}"
                        )
                        continue

        logger.info(f"Circular rebalancing complete: {rebalance_count} operations")
