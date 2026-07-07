from collections import defaultdict
from statistics import mean

from modules.logger import logger
from modules.network import LightningNetwork
from modules.simulation import Simulation


class RebalancingStrategy:
    def __init__(self, network: LightningNetwork, simulation: Simulation):
        self.network = network
        self.simulation = simulation

    def analyze_channels_balance(
        self, channels: list[tuple[str, str]] | None = None
    ) -> float:
        balances: list[int] = []
        for edge in channels or self.network.graph.edges():
            u, v = edge
            channel_out = self.network.graph[u][v]["balance"]
            channel_in = self.network.graph[v][u]["balance"]
            channel_capacity = channel_out + channel_in

            balance_ratio = (
                channel_out / channel_capacity
                if channel_out < channel_in
                else channel_in / channel_capacity
            )
            balances.append(balance_ratio)
        return mean(balances)

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

        for u, v, out in self.network.graph.edges(data=True):
            inb = self.network.graph[v][u]
            lambda_tot = out.get("lambda", 0) + inb.get("lambda", 0)
            capacity = out["balance"] + inb["balance"]
            out["rebalance_score"] = (
                out["balance"]
                if lambda_tot == 0
                else out["balance"] - out["lambda"] * capacity / lambda_tot
            )

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

    def circular_rebalance(self, rebalance_threshold: float = 0.2):
        rebalanced = 0
        for node in self.network.graph.nodes():
            imbalances = []
            for u, v, out in self.network.graph.out_edges(node, data=True):
                inb = self.network.graph[v][u]
                lambda_tot = out.get("lambda", 0) + inb.get("lambda", 0)
                if not lambda_tot:
                    continue
                capacity = out["balance"] + inb["balance"]
                imbalance = (
                    out["balance"] - out.get("lambda", 0) * capacity / lambda_tot
                )
                if abs(imbalance) >= rebalance_threshold * capacity:
                    imbalances.append((imbalance, v))

            surplus = sorted((c for c in imbalances if c[0] > 0), reverse=True)
            deficit = sorted(c for c in imbalances if c[0] < 0)
            for (surplus_amount, sv), (deficit_amount, dv) in zip(surplus, deficit):
                amount = int(min(surplus_amount, -deficit_amount))
                route = self.network.find_circular_route((node, sv), (dv, node), amount)
                if route is None:
                    continue
                self.network.execute_payment(route[0], amount)
                rebalanced += 1

        logger.info(f"Rebalanced {rebalanced} channel pairs using circular payments.")

    def circular_rebalance_opt(self, rebalance_threshold: float = 0.2):
        rebalanced = 0
        for node in self.network.graph.nodes():
            channels = []
            for u, v, out in self.network.graph.out_edges(node, data=True):
                capacity = out["balance"] + self.network.graph[v][u]["balance"]
                if abs(out["rebalance_score"]) >= rebalance_threshold * capacity:
                    channels.append((out["rebalance_score"], v))

            surplus = sorted((c for c in channels if c[0] > 0), reverse=True)
            deficit = sorted(c for c in channels if c[0] < 0)
            for (surplus_amount, sv), (deficit_amount, dv) in zip(surplus, deficit):
                seed = int(min(surplus_amount, -deficit_amount))
                route = self.network.find_circular_route(
                    (node, sv), (dv, node), seed, rebalance=True
                )
                if route is None:
                    continue
                hops = list(zip(route[0][:-1], route[0][1:]))
                amount = int(
                    min(
                        -deficit_amount,
                        *(self.network.graph[a][b]["rebalance_score"] for a, b in hops),
                    )
                )
                if amount <= 0:
                    continue
                self.network.execute_payment(route[0], amount)
                for a, b in hops:
                    self.network.graph[a][b]["rebalance_score"] -= amount
                    self.network.graph[b][a]["rebalance_score"] += amount
                rebalanced += 1

        logger.info(
            f"Rebalanced {rebalanced} channel pairs using optimized circular payments."
        )

    def passive_rebalance(
        self, max_fee_base: int = 2000, max_fee_rate: int = 20_000
    ) -> list[tuple[str, str]]:
        channels = set()
        for u, v, channel in self.network.graph.edges(data=True):
            channel_out = channel["balance"]
            channel_in = self.network.graph[v][u]["balance"]
            skew = (channel_out - channel_in) / (channel_out + channel_in)
            factor = (1 - skew) / 2
            channel["fee_base"] = int(max_fee_base * factor)
            channel["fee_rate"] = int(max_fee_rate * factor)

        for payment in self.simulation.payments:
            route = self.network.find_route(
                payment.src, payment.dst, payment.amount, simulation=True
            )
            if route is not None:
                self.network.execute_payment(route[0], payment.amount)
                channels = channels.union(set(zip(route[0][:-1], route[0][1:])))

        return list(channels)
