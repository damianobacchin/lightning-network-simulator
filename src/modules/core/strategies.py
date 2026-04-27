import networkx as nx

from modules.network.index import LightningNetwork

sats_per_vbyte = 10
splice_vbytes = 250
rebalance_threshold = 0.30
max_ops_per_node = 3
centrality_sample_size = 1000


def _channel_importance(centrality: dict, u: str, v: str) -> float:
    return centrality.get((u, v), centrality.get((v, u), 0.0))


def splicing_rebalance(network: LightningNetwork) -> dict:
    graph = network.graph
    undirected = graph.to_undirected()
    k = min(centrality_sample_size, undirected.number_of_nodes())
    centrality = nx.edge_betweenness_centrality(undirected, k=k, seed=42)

    total_fees = 0
    splice_count = 0
    fees_by_node: dict[str, int] = {}
    splice_cost = sats_per_vbyte * splice_vbytes

    for node in list(graph.nodes()):
        peers = {v for _, v in graph.out_edges(node)} | {
            u for u, _ in graph.in_edges(node)
        }
        if len(peers) < 2:
            continue

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
                    "importance": _channel_importance(centrality, node, peer),
                }
            )

        if len(channels) < 2:
            continue

        channels.sort(key=lambda c: c["importance"], reverse=True)

        ops_done = 0
        node_fees = 0

        for chan in channels:
            if ops_done >= max_ops_per_node:
                break
            if chan["ratio"] >= rebalance_threshold:
                continue

            target_outbound = chan["total"] * 0.5
            needed = int(target_outbound - chan["outbound"])
            if needed <= 0:
                continue

            others = [c for c in channels if c["peer"] != chan["peer"]]
            over = [c for c in others if c["ratio"] > 1 - rebalance_threshold]

            if over:
                over.sort(key=lambda c: c["importance"])
                src = over[0]
                available = int(src["outbound"] - src["total"] * 0.5)
            else:
                less = sorted(others, key=lambda c: c["importance"])
                src = less[0]
                if src["importance"] >= chan["importance"]:
                    continue
                available = int(src["outbound"] - src["total"] * rebalance_threshold)

            if available <= 0:
                continue

            move = min(needed, available)
            if move <= 0:
                continue

            graph[node][src["peer"]]["capacity"] -= move
            graph[node][chan["peer"]]["capacity"] += move

            src["outbound"] -= move
            src["total"] -= move
            src["ratio"] = src["outbound"] / src["total"] if src["total"] > 0 else 0.0
            chan["outbound"] += move
            chan["total"] += move
            chan["ratio"] = chan["outbound"] / chan["total"]

            op_fee = 2 * splice_cost
            node_fees += op_fee
            total_fees += op_fee
            splice_count += 2
            ops_done += 1

        if node_fees > 0:
            fees_by_node[node] = node_fees

    return {
        "splice_count": splice_count,
        "onchain_fees_sat": total_fees,
        "fees_by_node": fees_by_node,
    }
