import random
from datetime import datetime, timedelta

import numpy as np

from modules.network import LightningNetwork
from modules.schema import LightningPaymentData, SimulationResult


class Simulation:
    def __init__(self, network: LightningNetwork):
        self.network = network
        self.payments: list[LightningPaymentData] = []

    def generate_payments(
        self,
        num_payments: int,
        avg_amount: float,
        duration: int,
        recurrence_rate: float = 0,
        max_amount_ratio: float = 0.3,
    ):
        nodes = list(self.network.graph.nodes())
        out_capacity = {
            n: sum(d["balance"] for _, _, d in self.network.graph.out_edges(n, data=True))
            for n in nodes
        }
        shape = 2.0
        scale = avg_amount / shape

        amounts = np.random.gamma(shape, scale, size=num_payments)
        now = datetime.now()
        timestamps = [
            now + timedelta(seconds=int(s))
            for s in np.random.uniform(0, duration, size=num_payments)
        ]

        paths: list[tuple[str, str]] = []
        for _ in range(int(num_payments * (1 - recurrence_rate))):
            source, target = random.sample(nodes, 2)
            paths.append((source, target))

        for _ in range(num_payments - len(paths)):
            source, target = random.choice(paths)
            paths.append((source, target))

        payments: list[LightningPaymentData] = []
        for i, path in enumerate(paths):
            cap = int(max_amount_ratio * out_capacity[path[0]])
            payments.append(
                LightningPaymentData(
                    src=path[0],
                    dst=path[1],
                    amount=max(1, min(int(amounts[i]), cap)),
                    timestamp=timestamps[i],
                )
            )

        random.shuffle(payments)
        self.payments = payments

    def run_simulation(self, circular_rebalancing: bool = False) -> SimulationResult:
        simulation_result = SimulationResult(
            total_payments=len(self.payments),
            successful_payments=0,
            failed_payments=0,
            total_fees=0,
        )

        for payment in self.payments:
            route = self.network.find_route(payment.src, payment.dst, payment.amount)
            if route:
                path, total_fee = route
                self.network.execute_payment(path, payment.amount)
                simulation_result.successful_payments += 1
                simulation_result.total_fees += total_fee
            else:
                simulation_result.failed_payments += 1

        return simulation_result
