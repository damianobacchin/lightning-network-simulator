import json
from pathlib import Path

from modules.data.schema import LightningNetworkData
from modules.network.index import LightningNetwork
from modules.utils.logger import logger

if __name__ == "__main__":
    logger.info("Reading data from file")

    path = Path(__file__).parent.parent / "data" / "ln.json"

    with open(path) as f:
        data_dict = json.load(f)

    data = LightningNetworkData(**data_dict)

    logger.info(f"Loaded {len(data.nodes)} nodes and {len(data.edges)} edges")

    network = LightningNetwork()
    for node in data.nodes:
        network.add_node(node)
    for edge in data.edges:
        network.add_edge(edge)

    network.plot()
