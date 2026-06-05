import json
import sys
from pathlib import Path

from modules.core.strategies.circular_rebalancing import CircularRebalancing
from modules.core.strategies.submarine_swap import SubmarineSwap
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
    circular_rebalancing_optimization = "circular-rebalancing" in flags
    submarine_swap_optimization = "submarine-swap" in flags

    logger.info(f"Loading network state from {state_path}...")
    network = LightningNetwork()
    network.load_state(data_dir / state_path)

    logger.info("Loading Payments...")
    with open(data_dir / payments_path) as f:
        payments = [LightningPaymentData(**tx) for tx in json.load(f)]

    if circular_rebalancing_optimization:
        circular_rebalancing = CircularRebalancing(network, payments)
        circular_rebalancing.analyze_payments()
        circular_rebalancing.apply_rebalancing()

    if submarine_swap_optimization:
        submarine_swap = SubmarineSwap(network, payments)
        submarine_swap.analyze_payments()
        submarine_swap.apply_swaps()

    logger.info(
        f"State loaded: {network.graph.number_of_nodes()} nodes, "
        f"{network.graph.number_of_edges()} directed edges"
    )

    logger.info(f"Payments loaded: {len(payments)} payments")

    logger.info("Executing payments...")
    results = []
    successful = 0
    failed = 0

    for payment in payments:
        try:
            if multipath:
                routes = network.find_multipath_route(
                    payment.src, payment.dst, payment.amount
                )
            else:
                path, fee = network.find_route(payment.src, payment.dst, payment.amount)
                routes = [(path, payment.amount, fee)]

            for path, part_amount, _ in routes:
                network.execute_payment(path, part_amount)

            total_fee = sum(f for _, _, f in routes)
            if len(routes) == 1:
                result_entry = {
                    "source": payment.src,
                    "target": payment.dst,
                    "amount": payment.amount,
                    "status": "success",
                    "fee": total_fee,
                    "path": routes[0][0],
                }
            else:
                result_entry = {
                    "source": payment.src,
                    "target": payment.dst,
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
                    "source": payment.src,
                    "target": payment.dst,
                    "amount": payment.amount,
                    "status": "no_route",
                }
            )
            failed += 1
        except InsufficientBalanceError:
            results.append(
                {
                    "source": payment.src,
                    "target": payment.dst,
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
