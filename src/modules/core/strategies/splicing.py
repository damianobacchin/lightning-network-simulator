import networkx as nx

from modules.core.strategies.base import RebalanceStrategy, node_channels
from modules.network.index import LightningNetwork


class SplicingStrategy(RebalanceStrategy):
    def __init__(
        self,
        sats_per_vbyte: int = 10,
        splice_vbytes: int = 250,
        rebalance_threshold: float = 0.30,
        max_ops_per_node: int = 3,
        centrality_sample_size: int = 1000,
    ):
        self.sats_per_vbyte = sats_per_vbyte
        self.splice_vbytes = splice_vbytes
        self.rebalance_threshold = rebalance_threshold
        self.max_ops_per_node = max_ops_per_node
        self.centrality_sample_size = centrality_sample_size

    def apply(self, network: LightningNetwork) -> dict:
        graph = network.graph
        splice_cost = self.sats_per_vbyte * self.splice_vbytes
        centrality = self._compute_centrality(graph)

        total_fees = 0
        op_count = 0
        fees_by_node: dict[str, int] = {}

        for node in list(graph.nodes()):
            channels = node_channels(graph, node)
            if len(channels) < 2:
                continue
            for c in channels:
                c["importance"] = self._importance(centrality, node, c["peer"])
            channels.sort(key=lambda c: c["importance"], reverse=True)

            node_fees = 0
            ops_done = 0

            for chan in channels:
                if ops_done >= self.max_ops_per_node:
                    break
                if chan["ratio"] >= self.rebalance_threshold:
                    continue

                needed = int(chan["total"] * 0.5 - chan["outbound"])
                if needed <= 0:
                    continue

                src, available = self._select_source(channels, chan)
                if src is None or available <= 0:
                    continue

                move = min(needed, available)
                if move <= 0:
                    continue

                graph[node][src["peer"]]["capacity"] -= move
                graph[node][chan["peer"]]["capacity"] += move
                self._adjust(src, -move)
                self._adjust(chan, move)

                fee = 2 * splice_cost
                node_fees += fee
                total_fees += fee
                op_count += 2
                ops_done += 1

            if node_fees > 0:
                fees_by_node[node] = node_fees

        return {
            "splice_count": op_count,
            "onchain_fees_sat": total_fees,
            "fees_by_node": fees_by_node,
        }

    def _compute_centrality(self, graph) -> dict:
        undirected = graph.to_undirected()
        k = min(self.centrality_sample_size, undirected.number_of_nodes())
        return nx.edge_betweenness_centrality(undirected, k=k, seed=42)

    @staticmethod
    def _importance(centrality: dict, u: str, v: str) -> float:
        return centrality.get((u, v), centrality.get((v, u), 0.0))

    def _select_source(self, channels: list[dict], target: dict):
        others = [c for c in channels if c["peer"] != target["peer"]]
        over = [c for c in others if c["ratio"] > 1 - self.rebalance_threshold]
        if over:
            over.sort(key=lambda c: c["importance"])
            src = over[0]
            return src, int(src["outbound"] - src["total"] * 0.5)

        less = sorted(others, key=lambda c: c["importance"])
        if not less:
            return None, 0
        src = less[0]
        if src["importance"] >= target["importance"]:
            return None, 0
        return src, int(src["outbound"] - src["total"] * self.rebalance_threshold)

    @staticmethod
    def _adjust(chan: dict, delta: int) -> None:
        chan["outbound"] += delta
        chan["total"] += delta
        chan["ratio"] = chan["outbound"] / chan["total"] if chan["total"] > 0 else 0.0
