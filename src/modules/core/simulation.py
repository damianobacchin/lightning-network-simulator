import json
from pathlib import Path

from modules.data.schema import LightningNetworkData, LightningPaymentData
from modules.network.index import (
    InsufficientBalanceError,
    LightningNetwork,
    NoRouteError,
)
from modules.utils.logger import logger

data_dir = Path(__file__).resolve().parents[3] / "data"


def run_simulation(
    network_path: str = "ln.json",
    payments_path: str = "payments.json",
    output_path: str = "results.json",
):
    logger.info("Loading Network...")

    with open(data_dir / network_path) as f:
        data = LightningNetworkData(**json.load(f))

    network = LightningNetwork()
    for node in data.nodes:
        network.add_node(node)
    for edge in data.edges:
        network.add_edge(edge)

    logger.info(
        f"Network loaded: {len(data.nodes)} nodes and {len(data.edges)} channels"
    )

    logger.info("Loading Payments...")
    with open(data_dir / payments_path) as f:
        payments = [LightningPaymentData(**tx) for tx in json.load(f)]

    logger.info(f"Payments loaded: {len(payments)} payments")

    logger.info("Executing payments...")
    results = []
    successful = 0
    failed = 0

    for payment in payments:
        try:
            path, fee = network.find_route(
                payment.source, payment.target, payment.amount
            )
            network.execute_payment(path, payment.amount)
            results.append(
                {
                    "source": payment.source,
                    "target": payment.target,
                    "amount": payment.amount,
                    "status": "success",
                    "fee": fee,
                    "path": path,
                }
            )
            successful += 1
        except NoRouteError:
            results.append(
                {
                    "source": payment.source,
                    "target": payment.target,
                    "amount": payment.amount,
                    "status": "no_route",
                }
            )
            failed += 1
        except InsufficientBalanceError:
            results.append(
                {
                    "source": payment.source,
                    "target": payment.target,
                    "amount": payment.amount,
                    "status": "insufficient_balance",
                }
            )
            failed += 1

    with open(data_dir / output_path, "w") as f:
        json.dump(results, f, indent=4)

    logger.info(
        f"Simulation complete: {successful} successful, {failed} failed out of {len(payments)} payments. "
        f"Results saved to {output_path}"
    )
