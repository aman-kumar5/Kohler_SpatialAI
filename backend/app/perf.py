"""Opt-in, low-noise performance instrumentation for optimizer diagnostics."""
from __future__ import annotations

import logging
import os
from time import perf_counter

logger = logging.getLogger(__name__)


def perf_enabled() -> bool:
    return os.getenv("KOHLER_PERF_LOG", "").lower() in {"1", "true", "yes"}


def log_perf(label: str, started_at: float) -> None:
    """Emit a single timing line only when explicitly requested."""
    if perf_enabled():
        logger.info("[PERF] %s: %.1f ms", label, (perf_counter() - started_at) * 1000)
