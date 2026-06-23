import json
from pathlib import Path

# from modules.logger import logger
from modules.network import LightningNetwork
from modules.schema import LightningNetworkData
from modules.simulation import run_simulation

data_path = Path(__file__).resolve().parents[1] / "data"

if __name__ == "__main__":
    with open(data_path / "network.json") as f:
        graph_data = LightningNetworkData(**json.load(f))

    lightning_network = LightningNetwork(graph_data, balance_ratio=0.5)
    lightning_network.plot(_labels=True)

    # payments = lightning_network.generate_payments(
    #     avg_amount=50000, num_payments=100, recurrence_rate=0
    # )

    # simulation_result = run_simulation(lightning_network, payments)
    # print(simulation_result)
