import json
from pathlib import Path

# from modules.logger import logger
from modules.network import LightningNetwork
from modules.schema import LightningNetworkData
from modules.simulation import Simulation

data_path = Path(__file__).resolve().parents[1] / "data"

if __name__ == "__main__":
    with open(data_path / "network.json") as f:
        graph_data = LightningNetworkData(**json.load(f))

    lightning_network = LightningNetwork(graph_data, balance_ratio=0.5)
    # lightning_network.plot(_labels=True)

    simulation = Simulation(lightning_network)

    simulation.generate_payments(
        avg_amount=100000, num_payments=300, duration=180, recurrence_rate=0
    )
    print(simulation.run_simulation())

    # simulation_result = run_simulation(lightning_network, payments)
    # print(simulation_result)
