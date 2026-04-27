from abc import ABC, abstractmethod

from modules.network.index import LightningNetwork


class RebalanceStrategy(ABC):
    @abstractmethod
    def apply(self, network: LightningNetwork) -> dict:
        ...


def node_channels(graph, node) -> list[dict]:
    peers = {v for _, v in graph.out_edges(node)} | {
        u for u, _ in graph.in_edges(node)
    }
    channels = []
    for peer in peers:
        if not (graph.has_edge(node, peer) and graph.has_edge(peer, node)):
            continue
        outbound = graph[node][peer]["capacity"]
        inbound = graph[peer][node]["capacity"]
        total = outbound + inbound
        if total <= 0:
            continue
        channels.append(
            {
                "peer": peer,
                "outbound": outbound,
                "total": total,
                "ratio": outbound / total,
            }
        )
    return channels
