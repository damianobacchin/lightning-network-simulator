import json
from pathlib import Path

from modules.data.schema import LightningNetworkData, LightningPaymentData
from modules.network.index import LightningNetwork
from modules.utils.logger import logger

if __name__ == "__main__":
    logger.info("Loading Network...")

    network_path = Path(__file__).parent.parent / "data" / "ln.json"
    payments_path = Path(__file__).parent.parent / "data" / "payments.json"

    with open(network_path) as f:
        data_dict = json.load(f)

    data = LightningNetworkData(**data_dict)

    network = LightningNetwork()
    for node in data.nodes:
        network.add_node(node)
    for edge in data.edges:
        network.add_edge(edge)

    logger.info(
        f"Network loaded: {len(data.nodes)} nodes and {len(data.edges)} channels"
    )

    logger.info("Loading Transactions...")
    with open(payments_path) as f:
        payments_dict = json.load(f)

    payments = [LightningPaymentData(**tx) for tx in payments_dict]
    logger.info(f"Payments loaded: {len(payments)} payments")
