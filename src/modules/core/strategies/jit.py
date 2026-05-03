import networkx as nx

from modules.core.strategies.base import RebalanceStrategy, node_channels
from modules.network.index import LightningNetwork
from modules.routing.fees import calculate_fee


class JITStrategy(RebalanceStrategy):
    def __init__(
        self,
        max_path_attempts: int = 5,
        max_loop_attempts: int = 3,
        min_channels: int = 2,
    ):
        self.max_path_attempts = max_path_attempts
        self.max_loop_attempts = max_loop_attempts
        self.min_channels = min_channels

    def apply(self, network: LightningNetwork) -> dict:
        return {"jit_count": 0, "rebalance_fees_sat": 0, "fees_by_node": {}}

    def try_route(
        self,
        network: LightningNetwork,
        source: str,
        target: str,
        amount: int,
    ) -> tuple[list[str], int, int, dict[str, int]] | None:
        graph = network.graph
        try:
            nx.dijkstra_path(graph, source, target)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

        try:
            paths_iter = nx.shortest_simple_paths(
                graph, source, target, weight=_capacity_weight
            )
            for i, path in enumerate(paths_iter):
                if i >= self.max_path_attempts:
                    break
                resolved = self._resolve_path(network, path, amount)
                if resolved is None:
                    continue
                jit_fee, fees_by_node = resolved
                payment_fee = sum(
                    calculate_fee(
                        graph[u][v]["fee_base"], graph[u][v]["fee_rate"], amount
                    )
                    for u, v in zip(path[:-1], path[1:])
                )
                return path, payment_fee, jit_fee, fees_by_node
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None
        return None

    def _resolve_path(
        self,
        network: LightningNetwork,
        path: list[str],
        amount: int,
    ) -> tuple[int, dict[str, int]] | None:
        graph = network.graph
        backup = {(u, v): graph[u][v]["capacity"] for u, v in graph.edges()}

        jit_fee = 0
        fees_by_node: dict[str, int] = {}
        for u, v in zip(path[:-1], path[1:]):
            if graph[u][v]["capacity"] >= amount:
                continue
            if len(node_channels(graph, u)) < self.min_channels:
                self._restore(graph, backup)
                return None
            deficit = amount - graph[u][v]["capacity"]
            fee = self._rebalance_node(network, u, v, deficit)
            if fee is None:
                self._restore(graph, backup)
                return None
            jit_fee += fee
            fees_by_node[u] = fees_by_node.get(u, 0) + fee
        return jit_fee, fees_by_node

    @staticmethod
    def _restore(graph, backup: dict[tuple[str, str], int]) -> None:
        for (u, v), cap in backup.items():
            graph[u][v]["capacity"] = cap

    def _rebalance_node(
        self,
        network: LightningNetwork,
        node: str,
        target_peer: str,
        deficit: int,
    ) -> int | None:
        graph = network.graph
        candidates = [
            c
            for c in node_channels(graph, node)
            if c["peer"] != target_peer and c["outbound"] >= deficit
        ]
        candidates.sort(key=lambda c: -c["outbound"])
        if not candidates:
            return None

        subgraph = nx.restricted_view(graph, [node], [])
        if not subgraph.has_node(target_peer):
            return None

        for c in candidates:
            w = c["peer"]
            if not subgraph.has_node(w):
                continue
            try:
                paths_iter = nx.shortest_simple_paths(
                    subgraph, w, target_peer, weight=_capacity_weight
                )
                for j, sub in enumerate(paths_iter):
                    if j >= self.max_loop_attempts:
                        break
                    loop = [node] + sub + [node]
                    hops = list(zip(loop[:-1], loop[1:]))
                    fees = [
                        calculate_fee(
                            graph[u][v]["fee_base"], graph[u][v]["fee_rate"], deficit
                        )
                        for u, v in hops
                    ]
                    feasible = True
                    for idx, (u, v) in enumerate(hops):
                        flow = deficit + sum(fees[idx + 1 :])
                        if graph[u][v]["capacity"] < flow:
                            feasible = False
                            break
                    if not feasible:
                        continue
                    network.execute_payment(loop, deficit)
                    return sum(fees[1:])
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                continue
        return None


def _capacity_weight(u, v, d):
    cap = d.get("capacity", 0)
    return 1.0 / cap if cap > 0 else float("inf")
