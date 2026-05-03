from typing import Optional

from networkx import dijkstra_path

from modules.data.schema import LightningPaymentData
from modules.network.index import LightningNetwork
from modules.utils.logger import logger


class CircularRebalancing:
    def __init__(
        self,
        lightning_network: LightningNetwork,
        payments: Optional[list[LightningPaymentData]] = None,
    ):
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
        for node in self.graph.nodes():
            if self.graph.out_degree(node) < 2:
                continue
            out_channels = list(self.graph.out_edges(node, data=True))

            node_liquidity = sum(data.get("capacity", 0) for _, _, data in out_channels)
            print(f"Node {node} liquidity: {node_liquidity} sats")

            
