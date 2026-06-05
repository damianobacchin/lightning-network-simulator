from typing import Optional

from networkx import NetworkXNoPath, NodeNotFound, dijkstra_path

from modules.core import fees
from modules.data.schema import LightningPaymentData
from modules.network.index import LightningNetwork
from modules.routing.fees import calculate_fee
from modules.utils.logger import logger


class SubmarineSwap:
    def __init__(
        self,
        lightning_network: LightningNetwork,
        payments: Optional[list[LightningPaymentData]] = None,
        swap_fee_rate: int = fees.swap_fee_rate,
        swap_fee_base: int = fees.swap_fee_base,
        sats_per_vbyte: int = fees.sats_per_vbyte,
        swap_vbytes: int = fees.swap_vbytes,
        min_swap_amount: int = fees.min_swap_amount,
    ):
        self.network = lightning_network
        self.graph = lightning_network.graph
        self.payments = payments

        self.swap_fee_rate = swap_fee_rate
        self.swap_fee_base = swap_fee_base

        self.sats_per_vbyte = sats_per_vbyte
        self.swap_vbytes = swap_vbytes
        self.min_swap_amount = min_swap_amount
        self.channels_usage: dict[tuple[str, str], int] = dict()
        self.swap_count = 0
        self.total_lightning_fee = 0
        self.total_onchain_fee = 0

    @property
    def total_cost(self) -> int:
        return self.total_lightning_fee + self.total_onchain_fee

    def analyze_payments(self):
        logger.info("Analyzing channels usage for submarine swap...")
        for payment in self.payments or []:
            try:
                path = dijkstra_path(self.graph, payment.src, payment.dst)
            except (NetworkXNoPath, NodeNotFound):
                continue
            for u, v in zip(path[:-1], path[1:]):
                self.channels_usage[(u, v)] = (
                    self.channels_usage.get((u, v), 0) + payment.amount
                )
        logger.info("Channel usage analysis complete.")

    def apply_swaps(self):
        logger.info("Applying submarine swap strategy...")
        if not self.channels_usage:
            self.analyze_payments()

        candidate_nodes = {u for u, _ in self.channels_usage}
        logger.info(
            f"Evaluating {len(candidate_nodes)} candidate nodes "
            f"(of {self.graph.number_of_nodes()}) for submarine swaps..."
        )

        for node in self.graph.nodes():
            if node not in candidate_nodes:
                continue
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
                    if amount <= self.min_swap_amount:
                        continue

                    self._swap(node, src_channel, dst_channel, amount)
                    remaining -= amount
                    entry[1] = dst_deficit + amount

        logger.info(
            f"Submarine swap complete: {self.swap_count} swaps, "
            f"lightning fees {self.total_lightning_fee} sats, "
            f"on-chain fees {self.total_onchain_fee} sats, "
            f"total cost {self.total_cost} sats"
        )

    def _swap(
        self,
        node: str,
        src_channel: tuple[str, str],
        dst_channel: tuple[str, str],
        amount: int,
    ):
        u_src, v_src = src_channel
        u_dst, v_dst = dst_channel
        self.graph[u_src][v_src]["capacity"] -= amount
        self.graph[u_dst][v_dst]["capacity"] += amount

        lightning_fee = calculate_fee(self.swap_fee_base, self.swap_fee_rate, amount)
        onchain_fee = self.sats_per_vbyte * self.swap_vbytes

        self.swap_count += 1
        self.total_lightning_fee += lightning_fee
        self.total_onchain_fee += onchain_fee

        logger.info(
            f"Swapped {amount} sats on node {node}: "
            f"{src_channel[0]}-{src_channel[1]} -> {dst_channel[0]}-{dst_channel[1]} "
            f"(lightning fee {lightning_fee}, on-chain fee {onchain_fee})"
        )
