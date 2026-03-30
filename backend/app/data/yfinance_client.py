"""
Async wrapper around yfinance.

Provides:
  - get_current_price  — regularMarketPrice / currentPrice / previousClose
  - get_price_history  — OHLCV history as a list of dicts
  - get_financials     — income statement, balance sheet, cash flow
  - get_analyst_data   — analyst recommendations, price targets, earnings

Alpha Vantage is used ONLY for get_ticker_info (OVERVIEW endpoint) to obtain
market cap when Financial Datasets returns None. All other market data comes
from yfinance.

All calls use asyncio.to_thread so they don't block the event loop.
Every call is wrapped in asyncio.wait_for with a 15-second timeout.
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


async def get_current_price(ticker: str) -> float:
    """Return the most recent market price for a ticker.

    Tries regularMarketPrice, then currentPrice, then previousClose.
    Raises ValueError if all three are None (e.g. bad ticker or yfinance outage).
    """
    def _fetch() -> float:
        t = yf.Ticker(ticker, session=_SESSION)
        info = t.info or {}
        price = (
            info.get("regularMarketPrice")
            or info.get("currentPrice")
            or info.get("previousClose")
        )
        if price is None:
            raise ValueError(f"Current price unavailable for {ticker} (yfinance)")
        return float(price)

    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_fetch),
            timeout=_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        logger.warning("get_current_price: timeout for %s", ticker)
        raise ValueError(f"get_current_price timed out for {ticker}")
    except ValueError:
        raise
    except Exception as e:
        logger.warning("get_current_price: failed for %s: %s", ticker, e)
        raise ValueError(f"get_current_price failed for {ticker}: {e}") from e


async def get_price_history(ticker: str, period: str = "10y") -> dict:
    """Return OHLCV price history for the requested period.

    Each record: {date, open, high, low, close, volume}.
    Records are sorted oldest-first.
    Returns {"history": []} on any failure (non-critical caller).
    """
    def _fetch() -> dict:
        t = yf.Ticker(ticker, session=_SESSION)
        df = t.history(period=period)
        if df is None or df.empty:
            return {"history": []}
        records = []
        for idx, row in df.iterrows():
            records.append({
                "date": str(idx.date()),
                "open": float(row.get("Open") or 0),
                "high": float(row.get("High") or 0),
                "low": float(row.get("Low") or 0),
                "close": float(row.get("Close") or 0),
                "volume": int(row.get("Volume") or 0),
            })
        return {"history": records}

    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_fetch),
            timeout=_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        logger.warning("get_price_history: timeout for %s period=%s", ticker, period)
        return {"history": []}
    except Exception as e:
        logger.warning("get_price_history: failed for %s period=%s: %s", ticker, period, e)
        return {"history": []}


async def get_financials(ticker: str) -> dict:
    """Return annual income statement, balance sheet, and cash flow statements.

    Each is a list[dict] converted from the yfinance DataFrame via _df_to_records.
    Returns empty lists for each key on any failure (non-critical caller).
    """
    def _fetch() -> dict:
        t = yf.Ticker(ticker, session=_SESSION)
        return {
            "income_stmt": _df_to_records(t.financials),
            "balance_sheet": _df_to_records(t.balance_sheet),
            "cashflow": _df_to_records(t.cashflow),
        }

    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_fetch),
            timeout=_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        logger.warning("get_financials: timeout for %s", ticker)
        return {"income_stmt": [], "balance_sheet": [], "cashflow": []}
    except Exception as e:
        logger.warning("get_financials: failed for %s: %s", ticker, e)
        return {"income_stmt": [], "balance_sheet": [], "cashflow": []}


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


