import networkx as nx
import numpy as np


class SyntheticGraph:
    def __init__(self, nodes: int, edges: int, alpha: float, leaf_ratio: float, n0: int):
        if not 0.0 <= leaf_ratio < 1.0 or nodes <= n0:
            raise ValueError("invalid nodes/leaf_ratio/n0 combination")

        span = nodes - n0
        n_leaf = round(leaf_ratio * nodes)
        n_core = span - n_leaf
        base, rem = divmod(edges - n_leaf, max(n_core, 1))
        if n_core < 1 or base < 1 or base + 1 > n0:
            raise ValueError("infeasible edge budget for given parameters")

        rng = np.random.default_rng(42)
        attach = np.concatenate(
            [np.ones(n_leaf, int), np.full(rem, base + 1), np.full(n_core - rem, base)]
        )
        leaf = np.arange(span) < n_leaf
        perm = rng.permutation(span)
        attach, leaf = attach[perm], leaf[perm]

        self.graph = nx.Graph()
        self.graph.add_nodes_from(str(i) for i in range(1, n0 + 1))
        degrees = np.zeros(nodes)
        is_leaf = np.zeros(nodes, bool)

        for step, pos in enumerate(range(n0, nodes)):
            m = int(attach[step])
            cand = np.nonzero(~is_leaf[:pos])[0]
            w = degrees[cand] ** alpha
            p = w / w.sum() if w.sum() > 0 else np.full(len(cand), 1 / len(cand))
            if np.count_nonzero(p) >= m:
                targets = cand[rng.choice(len(cand), m, replace=False, p=p)]
            else:
                forced = np.nonzero(p)[0]
                extra = rng.choice(np.nonzero(p == 0)[0], m - len(forced), replace=False)
                targets = cand[np.concatenate([forced, extra])]

            self.graph.add_node(str(pos + 1))
            self.graph.add_edges_from((str(pos + 1), str(int(v) + 1)) for v in targets)
            degrees[pos], degrees[targets], is_leaf[pos] = m, degrees[targets] + 1, leaf[step]
