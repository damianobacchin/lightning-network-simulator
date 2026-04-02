import json
from pathlib import Path

from modules.data.schema import LightningNetworkData, LightningPaymentData
from modules.network.index import (
    InsufficientBalanceError,
    LightningNetwork,
    NoRouteError,
)
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

    logger.info("Loading Payments...")
    with open(payments_path) as f:
        payments_dict = json.load(f)

    payments = [LightningPaymentData(**tx) for tx in payments_dict]
    logger.info(f"Payments loaded: {len(payments)} payments")

    logger.info("Executing payments...")
    for payment in payments:
        try:
            path, fee = network.find_route(
                payment.source, payment.target, payment.amount
            )
            logger.info(
                f"Payment from {payment.source} to {payment.target} for {payment.amount} sats: "
                f"Route found with fee {fee} satoshis: {' > '.join(path)}"
            )
            network.execute_payment(path, payment.amount)
            for u, v in zip(path[:-1], path[1:]):
                logger.info(
                    f"  Channel {u} -> {v}: capacity {network.graph[u][v]['capacity']} | "
                    f"reverse {v} -> {u}: capacity {network.graph[v][u]['capacity']}"
                )
        except NoRouteError:
            logger.warning(
                f"Payment from {payment.source} to {payment.target} for {payment.amount} sats: No route found"
            )
        except InsufficientBalanceError:
            logger.warning(
                f"Payment from {payment.source} to {payment.target} for {payment.amount} sats: "
                f"Insufficient channel balance"
            )
