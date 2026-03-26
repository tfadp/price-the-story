"""Shared utility functions used across multiple nodes and data clients."""
import math
from typing import Optional


def safe_float(val) -> Optional[float]:
    """Convert a value to float, returning None on any error or non-finite result."""
    try:
        if val is None:
            return None
        f = float(val)
        return None if math.isnan(f) or math.isinf(f) else f
    except (TypeError, ValueError):
        return None
