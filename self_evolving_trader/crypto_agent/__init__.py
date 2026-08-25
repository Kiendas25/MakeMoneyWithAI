"""A self-evolving, autonomous crypto trading agent with two brains.

Public surface:

    from crypto_agent import Config, TradingAgent, DualBrain

See ``README.md`` for the architecture and the CLI.
"""

from .config import Config
from .brain.memory import DualBrain
from .agent import TradingAgent, StepResult

__all__ = ["Config", "DualBrain", "TradingAgent", "StepResult", "__version__"]
__version__ = "1.0.0"
