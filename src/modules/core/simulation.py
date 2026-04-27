import json
import sys
from pathlib import Path

from modules.data.schema import LightningPaymentData
from modules.network.index import (
    InsufficientBalanceError,
    LightningNetwork,
    NoRouteError,
)
from modules.utils.logger import logger

data_dir = Path(__file__).resolve().parents[3] / "data"


def run_simulation(
    state_path: str = "state.json",
    payments_path: str = "payments.json",
    output_path: str = "results.json",
):
    flags = {arg.lower() for arg in sys.argv[1:]}
    multipath = "multipath" in flags
    splicing = "splicing" in flags
    if multipath:
        logger.info("Multipath payments enabled (max splits: 8)")
    if splicing:
        logger.info("Splicing rebalance enabled (threshold: 30%)")

    logger.info(f"Loading network state from {state_path}...")
    network = LightningNetwork()
    network.load_state(data_dir / state_path)
    logger.info(
        f"State loaded: {network.graph.number_of_nodes()} nodes, "
        f"{network.graph.number_of_edges()} directed edges"
    )

    rebalance_fees = 0
    splice_count = 0
    fees_by_node: dict[str, int] = {}
    if splicing:
        logger.info("Applying splicing rebalance...")

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
            if multipath:
                routes = network.find_multipath_route(
                    payment.source, payment.target, payment.amount
                )
            else:
                path, fee = network.find_route(
                    payment.source, payment.target, payment.amount
                )
                routes = [(path, payment.amount, fee)]

            for path, part_amount, _ in routes:
                network.execute_payment(path, part_amount)

            total_fee = sum(f for _, _, f in routes)
            if len(routes) == 1:
                result_entry = {
                    "source": payment.source,
                    "target": payment.target,
                    "amount": payment.amount,
                    "status": "success",
                    "fee": total_fee,
                    "path": routes[0][0],
                }
            else:
                result_entry = {
                    "source": payment.source,
                    "target": payment.target,
                    "amount": payment.amount,
                    "status": "success",
                    "fee": total_fee,
                    "splits": len(routes),
                    "paths": [{"path": p, "amount": a, "fee": f} for p, a, f in routes],
                }
            results.append(result_entry)
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
        "rebalance": {
            "enabled": splicing,
            "splice_count": splice_count,
            "onchain_fees_sat": rebalance_fees,
            "fees_by_node": fees_by_node,
        },
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
