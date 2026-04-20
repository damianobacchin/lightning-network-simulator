import json
import sys
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
    unbalance_factor = float(sys.argv[1]) if len(sys.argv) > 1 else 1

    with open(data_dir / network_path) as f:
        data = LightningNetworkData(**json.load(f))

    network = LightningNetwork()
    for node in data.nodes:
        network.add_node(node)
    for edge in data.edges:
        network.add_edge(edge, unbalance_factor)

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

    total = len(payments)
    success_rate = (successful / total * 100) if total else 0.0

    failure_counts: dict[str, int] = {}
    for r in results:
        if r["status"] != "success":
            failure_counts[r["status"]] = failure_counts.get(r["status"], 0) + 1
    failure_reasons = {
        reason: {
            "count": count,
            "percentage": (count / failed * 100) if failed else 0.0,
        }
        for reason, count in failure_counts.items()
    }

    statistics = {
        "total": total,
        "successful": successful,
        "failed": failed,
        "success_rate": success_rate,
        "failure_reasons": failure_reasons,
    }

    with open(data_dir / output_path, "w") as f:
        json.dump({"statistics": statistics, "results": results}, f, indent=4)

    logger.info(
        f"Simulation complete: {successful}/{total} successful, {failed}/{total} failed "
        f"(success rate: {success_rate:.2f}%)"
    )
    if failure_reasons:
        logger.info("Failure breakdown:")
        for reason, info in failure_reasons.items():
            logger.info(
                f"  - {reason}: {info['count']} ({info['percentage']:.2f}% of failures)"
            )
    logger.info(f"Results saved to {output_path}")
