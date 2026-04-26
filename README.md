# Lightning Network Simulator

This reporitory provides an implementation of a Lightning Network Simulator in Python.

## Key Features
- **Network Graph Construction**: Build Lightning Network topology from LND node descriptions.
- **Payment Generation**: Create randomized payment sequences with configurable average amounts.
- **Channel Simulation**: Run network simulations with adjustable channel balance distribution.

## Usage
- Generate random payments: `python src/modules/data/generator.py payments <num_payments> <avg_amount>`
- Run simulation: `python src/index.py <unbalance_factor>`
