import json
from pathlib import Path

from modules.network import LightningNetwork
from modules.schema import LightningNetworkData
from modules.simulation import Simulation
from modules.strategies import RebalancingStrategy

data_path = Path(__file__).resolve().parents[1] / "data"

if __name__ == "__main__":
    with open(data_path / "network.json") as f:
        graph_data = LightningNetworkData(**json.load(f))

    lightning_network = LightningNetwork(graph_data, balance_ratio=0.3)

    simulation = Simulation(lightning_network)

    simulation.generate_payments(
        avg_amount=5000, num_payments=10000, duration=180, recurrence_rate=0.1
    )

    strategy = RebalancingStrategy(lightning_network, simulation)
    strategy.analyze_payments()
    strategy.circular_rebalance_opt()

    print(simulation.run_simulation())
