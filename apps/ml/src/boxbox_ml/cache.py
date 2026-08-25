"""FastF1 cache bootstrap.

FastF1 re-downloads every session from the F1 live-timing API unless a cache is
enabled, so ``enable()`` must run **before any other FastF1 call**. A loaded race
weekend is on the order of tens of MB without telemetry and hundreds of MB with
it, so the cache is the difference between a script that takes seconds and one
that takes minutes.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import fastf1

_DEFAULT_CACHE = Path(__file__).resolve().parents[2] / "data" / "ff1cache"


def cache_dir() -> Path:
    """Resolve the cache directory, honouring the ``BOXBOX_FF1_CACHE`` override."""
    override = os.environ.get("BOXBOX_FF1_CACHE")
    return Path(override).expanduser() if override else _DEFAULT_CACHE


def enable(quiet: bool = True) -> Path:
    """Enable the FastF1 cache and return the directory in use.

    Args:
        quiet: Raise FastF1's log level to WARNING so ingest output stays readable.

    Returns:
        The directory the cache was enabled on.
    """
    path = cache_dir()
    path.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(path))
    if quiet:
        logging.getLogger("fastf1").setLevel(logging.WARNING)
    return path
