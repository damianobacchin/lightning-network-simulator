from modules.network import LightningNetwork
from modules.schema import LightningPaymentData, SimulationResult


def run_simulation(
    network: LightningNetwork, payments: list[LightningPaymentData]
) -> SimulationResult:
    simulation_result = SimulationResult(
        total_payments=len(payments),
        successful_payments=0,
        failed_payments=0,
        total_fees=0,
    )

    for payment in payments:
        route = network.find_route(payment.src, payment.dst, payment.amount)
        if route:
            path, total_fee = route
            network.execute_payment(path, payment.amount)
            simulation_result.successful_payments += 1
            simulation_result.total_fees += total_fee
        else:
            simulation_result.failed_payments += 1

    return simulation_result
