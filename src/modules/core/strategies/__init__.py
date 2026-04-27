from modules.core.strategies.base import RebalanceStrategy
from modules.core.strategies.splicing import SplicingStrategy

STRATEGIES: dict[str, type[RebalanceStrategy]] = {
    "splicing": SplicingStrategy,
}

__all__ = ["RebalanceStrategy", "SplicingStrategy", "STRATEGIES"]
