import networkx as nx

from modules.network.index import LightningNetwork


def calculate_fee(fee_base: int, fee_rate: int, amount: int) -> int:
    return fee_base + round(fee_rate * amount / 1_000_000)


def find_route(
    network: LightningNetwork, source: str, target: str, amount: int
) -> tuple[list[str], int] | None:
    def weight(u, v, data):
        if data["capacity"] < amount:
            return None
        return calculate_fee(data["fee_base"], data["fee_rate"], amount)

    try:
        path = nx.dijkstra_path(network.graph, source, target, weight=weight)
    except nx.NetworkXNoPath:
        return None

    total_fee = 0
    for u, v in zip(path[:-1], path[1:]):
        data = network.graph[u][v]
        total_fee += calculate_fee(data["fee_base"], data["fee_rate"], amount)

    return path, total_fee
