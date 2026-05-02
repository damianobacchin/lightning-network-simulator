import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

data_dir = Path(__file__).resolve().parents[3] / "data"


def _format_sats(value: int) -> str:
    if value >= 1_000_000:
        return f"{value // 1_000_000}M sat"
    if value >= 1_000:
        return f"{value // 1_000}k sat"
    return f"{value} sat"


def plot_simulations(
    input_path: str = "simulations.json",
    output_path: str = "simulations.pdf",
):
    with open(data_dir / input_path) as f:
        data = json.load(f)

    amounts = sorted((int(k) for k in data.keys()))
    factors = sorted({float(k) for series in data.values() for k in series.keys()})

    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.size": 11,
            "axes.titlesize": 13,
            "axes.labelsize": 11,
            "axes.edgecolor": "#444444",
            "axes.linewidth": 0.8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "xtick.color": "#444444",
            "ytick.color": "#444444",
            "legend.frameon": False,
            "pdf.fonttype": 42,
        }
    )

    fig, ax = plt.subplots(figsize=(8, 5))

    cmap = plt.get_cmap("viridis")
    colors = [cmap(i / max(len(amounts) - 1, 1) * 0.85) for i in range(len(amounts))]

    for amount, color in zip(amounts, colors):
        series = data[str(amount)]
        ys = [series[_factor_key(series, f)] for f in factors]
        ax.plot(
            factors,
            ys,
            marker="o",
            markersize=6,
            linewidth=2,
            color=color,
            label=_format_sats(amount),
            markeredgecolor="white",
            markeredgewidth=1.2,
        )

    ax.set_xlabel("Unbalance factor")
    ax.set_ylabel("Failed transactions")
    ax.set_title(
        "Failed transactions vs. channel unbalance",
        loc="left",
        pad=14,
        fontweight="semibold",
    )

    ax.set_xticks(factors)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True, nbins=8))
    ax.grid(True, axis="y", linestyle="--", linewidth=0.6, alpha=0.6)
    ax.set_axisbelow(True)
    ax.margins(x=0.04)

    legend = ax.legend(
        title="Average payment",
        loc="center left",
        bbox_to_anchor=(1.02, 0.5),
        borderaxespad=0,
    )
    legend.get_title().set_fontweight("semibold")

    fig.tight_layout()

    out = data_dir / output_path
    fig.savefig(out, format="pdf", bbox_inches="tight")
    plt.show()


def _factor_key(series: dict, factor: float) -> str:
    for k in series.keys():
        if float(k) == factor:
            return k
    raise KeyError(factor)


if __name__ == "__main__":
    plot_simulations()
