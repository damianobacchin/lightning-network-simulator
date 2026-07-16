from collections.abc import Mapping

import networkx as nx

from modules.network import LightningNetwork
from modules.robustness_analysis import RobustnessAnalysis


class RobustnessOptimization:
    def __init__(self, network: LightningNetwork, min_degree: int = 2):
        self.graph = network.graph.to_undirected()
        self.min_degree = min_degree

    def optimize(self, channels: int = 5) -> nx.Graph:
        improved = self.graph.copy()
        core = nx.k_core(self.graph, self.min_degree)
        if core.number_of_nodes() < 2:
            return improved
        core = core.subgraph(max(nx.connected_components(core), key=len))
        fiedler = dict(zip(core, nx.fiedler_vector(core)))
        order = sorted(core, key=lambda node: fiedler[node])
        for _ in range(channels):
            lo, hi = 0, len(order) - 1
            while lo < hi:
                if improved.has_edge(order[lo], order[hi]):
                    hi -= 1
                else:
                    improved.add_edge(order[lo], order[hi])
                    lo, hi = lo + 1, hi - 1
        return improved

    def analyze(self, channels: int = 1, **kwargs) -> Mapping[str, RobustnessAnalysis]:
        return RobustnessAnalysis.compare(
            {"Original": self.graph, "Optimized": self.optimize(channels)}, ("degree", "betweenness"), **kwargs
        )
