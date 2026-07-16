import json
from pathlib import Path

from modules.network import LightningNetwork
from modules.robustness_analysis import RobustnessAnalysis
from modules.schema import LightningNetworkData

data_path = Path(__file__).resolve().parents[1] / "data"

if __name__ == "__main__":
    with open(data_path / "network.json") as f:
        graph_data = LightningNetworkData(**json.load(f))

    lightning_network = LightningNetwork(graph_data)
    graph = lightning_network.graph.to_undirected()

    RobustnessAnalysis.over_alpha(graph.number_of_nodes(), graph.number_of_edges())
