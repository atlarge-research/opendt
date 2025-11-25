"""Simulation Worker Service Package.

This package provides the core simulation engine for OpenDT, including:
- OpenDC binary wrapper for running simulations
- Time-based window management for task aggregation
- Kafka integration for consuming workload and topology streams
"""

from .runner import OpenDCRunner
from .window_manager import TimeWindow, WindowManager

__all__ = [
    "OpenDCRunner",
    "TimeWindow",
    "WindowManager",
]
