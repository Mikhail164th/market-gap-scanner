"""Market Gap Scanner — market niche analysis using Wordstat, Reddit, and LLM."""

__version__ = "0.1.0"

from .analyzer import MarketGap, analyze_gaps
from .wordstat import WordstatClient, WordstatResult

__all__ = [
    "MarketGap",
    "WordstatClient",
    "WordstatResult",
    "analyze_gaps",
]
