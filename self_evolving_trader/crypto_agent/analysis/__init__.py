"""Diagnostics computed *about* the agent, from the two brains, rather than
things the agent needs to run.

Kept separate from ``strategy``/``evolution``/``execution`` because nothing
here feeds back into a trading decision - it only explains one, after the
fact.
"""

from .divergence import DivergenceReport, FillComparison, SymbolDivergence, measure_divergence

__all__ = [
    "DivergenceReport",
    "FillComparison",
    "SymbolDivergence",
    "measure_divergence",
]
