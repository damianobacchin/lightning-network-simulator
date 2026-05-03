from modules.core.strategies.base import RebalanceStrategy
from modules.core.strategies.jit import JITStrategy
from modules.core.strategies.splicing import SplicingStrategy

STRATEGIES: dict[str, type[RebalanceStrategy]] = {
    "splicing": SplicingStrategy,
    "jit": JITStrategy,
}

__all__ = ["RebalanceStrategy", "SplicingStrategy", "JITStrategy", "STRATEGIES"]
