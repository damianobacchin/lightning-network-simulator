from collections.abc import Mapping
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np

from modules.graph_generation import SyntheticGraph
from modules.logger import logger

plt.rcParams.update(
    {
        "font.family": "serif",
        "font.serif": ["cmr10", "Computer Modern Roman", "DejaVu Serif"],
        "mathtext.fontset": "cm",
        "axes.formatter.use_mathtext": True,
        "axes.unicode_minus": False,
        "font.size": 12,
        "axes.titlesize": 13,
        "axes.labelsize": 12,
        "xtick.labelsize": 11,
        "ytick.labelsize": 11,
        "legend.fontsize": 11,
        "axes.linewidth": 0.7,
        "xtick.major.width": 0.7,
        "ytick.major.width": 0.7,
        "grid.linewidth": 0.5,
        "grid.alpha": 0.4,
        "lines.linewidth": 1.0,
        "lines.markersize": 4.5,
        "lines.markeredgewidth": 0.9,
        "legend.framealpha": 0.9,
        "legend.edgecolor": "0.7",
        "savefig.dpi": 300,
    }
)

strategies = ("degree", "betweenness", "random")
styles = {
    "degree": {"color": "steelblue", "marker": "s"},
    "betweenness": {"color": "firebrick", "marker": "o"},
    "random": {"color": "seagreen", "marker": "o", "markerfacecolor": "none"},
}
alpha_markers = ("o", "s", "^", "D", "v")
output_dir = Path(__file__).resolve().parents[2] / "output" / "robustness_analysis"


class RobustnessAnalysis:
    def __init__(
        self,
        graph: nx.Graph,
        strategies: tuple[str, ...] = strategies,
        max_fraction: float = 0.5,
        step_fraction: float = 0.02,
        betweenness_sample: int = 500,
        seed: int = 42,
    ):
        self.graph = graph
        self.total = graph.number_of_nodes()
        self.max_remove = int(max_fraction * self.total)
        self.batch = max(1, round(step_fraction * self.total))
        self.betweenness_sample = betweenness_sample
        self.seed = seed
        self.fractions: list[float] = []
        self.results: dict[str, tuple[list[float], list[int]]] = {}

        for strategy in strategies:
            logger.info(f"Ranking {self.total} nodes for the {strategy} attack...")
            self.fractions, sizes, diameters = self._simulate(self._order(strategy))
            self.results[strategy] = (sizes, diameters)
            logger.info(f"{strategy}: giant {sizes[-1]:.3f}N, diameter {diameters[-1]}")

    def _order(self, strategy: str) -> list:
        if strategy == "random":
            nodes = list(self.graph.nodes())
            perm = np.random.default_rng(self.seed).permutation(len(nodes))
            return [nodes[i] for i in perm]
        if strategy == "degree":
            ranking = nx.degree_centrality(self.graph)
        elif strategy == "betweenness":
            k = min(self.betweenness_sample, self.total)
            ranking = nx.betweenness_centrality(self.graph, k=k, seed=self.seed)
        else:
            raise ValueError(f"unknown strategy: {strategy!r}")
        return sorted(ranking, key=lambda n: ranking[n], reverse=True)

    @staticmethod
    def _metrics(graph: nx.Graph) -> tuple[int, int]:
        if graph.number_of_nodes() == 0:
            return 0, 0
        giant = max(nx.connected_components(graph), key=len)
        if len(giant) <= 1:
            return len(giant), 0
        return len(giant), nx.diameter(graph.subgraph(giant).copy(), usebounds=True)

    def _simulate(self, order: list) -> tuple[list[float], list[float], list[int]]:
        graph = self.graph.copy()
        fractions, sizes, diameters, removed = [], [], [], 0
        while True:
            size, diameter = self._metrics(graph)
            fractions.append(removed / self.total)
            sizes.append(size / self.total)
            diameters.append(diameter)
            if removed >= self.max_remove:
                return fractions, sizes, diameters
            k = min(self.batch, self.max_remove - removed)
            graph.remove_nodes_from(order[removed : removed + k])
            removed += k

    def plot(self, filename: str = "robustness.pdf"):
        fig, (ax_size, ax_diam) = plt.subplots(
            2, 1, sharex=True, figsize=(6.5, 5.4), layout="constrained"
        )
        for strategy, (sizes, diameters) in self.results.items():
            style = styles[strategy]
            ax_size.plot(self.fractions, sizes, label=strategy.capitalize(), **style)
            ax_diam.plot(self.fractions, diameters, **style)
        ax_size.set_ylabel("Giant component size (fraction of $N$)")
        ax_diam.set_ylabel("Giant component diameter")
        ax_diam.set_xlabel("Fraction of nodes removed")
        for ax in (ax_size, ax_diam):
            ax.grid(True, ls="--")
            ax.set_ylim(bottom=0)
        ax_diam.set_xlim(left=0)
        ax_size.legend()
        _save(fig, filename)

    @classmethod
    def over_alpha(
        cls,
        nodes: int,
        edges: int,
        alphas: tuple[float, ...] = (0.5, 0.75, 1.0, 1.25, 1.5),
        leaf_ratio: float = 0.2,
        n0: int = 6,
        strategies: tuple[str, ...] = strategies,
        filename: str = "robustness_alpha.pdf",
        **kwargs,
    ) -> Mapping[float, "RobustnessAnalysis"]:
        kwargs.setdefault("step_fraction", 0.02)
        analyses = {
            alpha: cls(
                SyntheticGraph(nodes, edges, alpha, leaf_ratio, n0).graph,
                strategies=strategies,
                **kwargs,
            )
            for alpha in alphas
        }
        cls._plot_alpha(analyses, strategies, filename)
        return analyses

    @staticmethod
    def _plot_alpha(
        analyses: Mapping[float, "RobustnessAnalysis"],
        strategies: tuple[str, ...],
        filename: str,
    ):
        n_strat = len(strategies)
        fig, axes = plt.subplots(
            2,
            n_strat,
            figsize=(3.6 * n_strat, 5.6),
            sharex=True,
            sharey="row",
            layout="constrained",
        )
        axes = np.array(axes).reshape(2, n_strat)
        cycle = plt.rcParams["axes.prop_cycle"].by_key()["color"]
        for col, strategy in enumerate(strategies):
            ax_size, ax_diam = axes[0, col], axes[1, col]
            for j, (alpha, analysis) in enumerate(analyses.items()):
                style = {
                    "color": cycle[j % len(cycle)],
                    "marker": alpha_markers[j % len(alpha_markers)],
                    "markerfacecolor": "none" if j % 2 else cycle[j % len(cycle)],
                }
                sizes, diameters = analysis.results[strategy]
                ax_size.plot(analysis.fractions, sizes, label=rf"$\alpha = {alpha}$", **style)
                ax_diam.plot(analysis.fractions, diameters, **style)
            ax_size.set_title(f"{strategy.capitalize()} attack")
            for ax in (ax_size, ax_diam):
                ax.grid(True, ls="--")
                ax.set_ylim(bottom=0)
            ax_diam.set_xlabel("Fraction of nodes removed")
            ax_diam.set_xlim(left=0)
        axes[0, 0].set_ylabel("Giant component (fraction of $N$)")
        axes[1, 0].set_ylabel("Giant component diameter")
        axes[0, -1].legend()
        _save(fig, filename)


def _save(fig, filename: str):
    output_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_dir / filename, format="pdf", bbox_inches="tight")
    plt.close(fig)
