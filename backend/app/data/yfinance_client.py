"""
Thin async wrapper around yfinance — analyst data ONLY.

All market data (ticker info, price history, financials, current price) has
been moved to alpha_vantage_client.py. This file exists solely to provide
get_analyst_data, which returns analyst recommendations, price targets, and
earnings forecasts. yfinance is the only available source for this data in v1
since Alpha Vantage has no analyst estimates endpoint.

All calls use asyncio.to_thread so they don't block the event loop.
Every call is wrapped in asyncio.wait_for with a 10-second timeout.
"""
import asyncio
import logging
from typing import Optional

import pandas as pd
import yfinance as yf
import requests

logger = logging.getLogger(__name__)

# How long we'll wait for any yfinance network call before giving up
_TIMEOUT_S = 15

# Browser-like headers used to reduce rate limiting
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://finance.yahoo.com/",
}

# Use a persistent session with browser-like headers to reduce rate limiting
_SESSION = requests.Session()
_SESSION.headers.update(_BROWSER_HEADERS)
yf.set_tz_cache_location("/tmp/yfinance_tz_cache")


def _df_to_records(df: pd.DataFrame) -> list[dict]:
    """Convert a DataFrame to a list of row dicts with JSON-serializable values.

    yfinance returns DataFrames whose column headers are Timestamps; we convert
    them to ISO strings so the data can round-trip through JSON.
    """
    if df is None or df.empty:
        return []
    # Transpose so each column (period) becomes a row
    transposed = df.T
    records = []
    for idx, row in transposed.iterrows():
        row_dict = {"date": str(idx)}
        for col, val in row.items():
            col_str = str(col)
            # Convert numpy/pandas NA to None
            row_dict[col_str] = None if pd.isna(val) else float(val)
        records.append(row_dict)
    return records


async def get_analyst_data(ticker: str) -> dict:
    """Return analyst recommendations, price targets, and earnings forecasts.

    Handles both yfinance 0.2.x summary format (strongBuy/buy/hold/sell/strongSell)
    and the legacy firm-level recommendations format.

    Returns an empty dict on failure (non-critical).
    """
    def _fetch() -> dict:
        t = yf.Ticker(ticker, session=_SESSION)

        # yfinance 0.2.x: recommendations is a period-summary DataFrame
        # yfinance legacy: recommendations is a firm-level DataFrame
        recommendations = t.recommendations

        # upgrades_downgrades gives firm-level history in 0.2.x
        try:
            upgrades_downgrades = t.upgrades_downgrades
        except Exception:
            upgrades_downgrades = None

        earnings_estimate = t.earnings_estimate
        revenue_estimate = t.revenue_estimate
        eps_trend = t.eps_trend
        price_targets = getattr(t, "analyst_price_targets", None)
        earnings_history = t.earnings_history

        return {
            "recommendations": recommendations,
            "upgrades_downgrades": upgrades_downgrades,
            "earnings_estimate": earnings_estimate,
            "revenue_estimate": revenue_estimate,
            "eps_trend": eps_trend,
            "price_targets": price_targets,
            "earnings_history": earnings_history,
        }

    try:
        raw = await asyncio.wait_for(
            asyncio.to_thread(_fetch),
            timeout=_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        logger.warning("get_analyst_data: timeout for %s", ticker)
        return {}
    except Exception as e:
        logger.warning("get_analyst_data: failed for %s: %s", ticker, e)
        return {}

    def _safe_df(df: Optional[pd.DataFrame]) -> list[dict]:
        """Convert a DataFrame to records, safely handling None/empty."""
        if df is None or (hasattr(df, "empty") and df.empty):
            return []
        try:
            df_reset = df.reset_index()
            records = []
            for _, row in df_reset.iterrows():
                row_dict = {}
                for col, val in row.items():
                    col_str = str(col)
                    row_dict[col_str] = None if (isinstance(val, float) and pd.isna(val)) else val
                records.append(row_dict)
            return records
        except Exception:
            return []

    # Price targets may be a dict or DataFrame
    price_targets_raw = raw.get("price_targets")
    if isinstance(price_targets_raw, pd.DataFrame):
        price_targets_out = _safe_df(price_targets_raw)
    elif isinstance(price_targets_raw, dict):
        price_targets_out = price_targets_raw
    else:
        price_targets_out = {}

    return {
        "recommendations": _safe_df(raw.get("recommendations")),
        "upgrades_downgrades": _safe_df(raw.get("upgrades_downgrades")),
        "earnings_estimate": _safe_df(raw.get("earnings_estimate")),
        "revenue_estimate": _safe_df(raw.get("revenue_estimate")),
        "eps_trend": _safe_df(raw.get("eps_trend")),
        "price_targets": price_targets_out,
        "earnings_history": _safe_df(raw.get("earnings_history")),
    }
