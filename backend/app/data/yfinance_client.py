"""
Thin async wrapper around yfinance (which is synchronous).
All calls use asyncio.to_thread so they don't block the event loop.
Every call is wrapped in asyncio.wait_for with a 10-second timeout.

yfinance is a scraper — it has no official API. Yahoo Finance rate-limits
aggressively during development (many calls in a short window). In normal
use (one analysis at a time), this is not an issue.

When yfinance is rate-limited, get_ticker_info falls back to the Yahoo
Finance v8/chart API directly via httpx, which uses a different endpoint
and is significantly more resilient.
"""
import asyncio
import logging
import requests
from typing import Optional

import httpx
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

# How long we'll wait for any yfinance network call before giving up
_TIMEOUT_S = 15

# Browser-like headers used for the direct HTTP fallback
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


async def _get_ticker_info_direct(ticker: str) -> dict:
    """Fallback: fetch ticker info directly from Yahoo Finance v8 chart API.

    This endpoint is less rate-limited than the quoteSummary endpoint that
    yfinance uses for .info. Returns a minimal dict with the fields the
    classifier needs: quoteType, exchange, regularMarketPrice, marketCap.
    """
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    params = {"interval": "1d", "range": "5d"}

    async with httpx.AsyncClient(headers=_BROWSER_HEADERS, timeout=_TIMEOUT_S) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    result = data.get("chart", {}).get("result")
    if not result:
        error = data.get("chart", {}).get("error", {})
        raise ValueError(f"Ticker not found: {ticker} — {error.get('description', 'unknown')}")

    meta = result[0].get("meta", {})
    return {
        "quoteType":             meta.get("instrumentType", "EQUITY"),
        "exchange":              meta.get("exchangeName", ""),
        "regularMarketPrice":    meta.get("regularMarketPrice"),
        "previousClose":         meta.get("chartPreviousClose"),
        "currency":              meta.get("currency", "USD"),
        "symbol":                meta.get("symbol", ticker),
        "shortName":             meta.get("shortName", ticker),
        "longName":              meta.get("longName", ticker),
        # marketCap not in v8/chart — will be None, classifier defaults to mid_cap
        "marketCap":             None,
        "regularMarketVolume":   None,
        "_from_direct_api":      True,
    }


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


async def get_ticker_info(ticker: str) -> dict:
    """Fetch yfinance metadata for the given ticker symbol.

    Tries fast_info first (lighter, avoids rate limits), then falls back to .info.
    Retries once with a 3-second delay on transient failures (e.g. 429 rate limit).
    Raises ValueError if the ticker is invalid or not found.
    """
    def _fetch_fast() -> dict:
        """Use fast_info — fewer HTTP calls, less rate-limit risk."""
        t = yf.Ticker(ticker, session=_SESSION)
        fi = t.fast_info
        # Map fast_info attributes to the .info key names the rest of the app expects
        return {
            "quoteType": getattr(fi, "quote_type", None),
            "exchange": getattr(fi, "exchange", None),
            "marketCap": getattr(fi, "market_cap", None),
            "regularMarketPrice": getattr(fi, "last_price", None),
            "regularMarketVolume": getattr(fi, "three_month_average_volume", None),
            "averageDailyVolume10Day": getattr(fi, "three_month_average_volume", None),
            "previousClose": getattr(fi, "previous_close", None),
            "currency": getattr(fi, "currency", "USD"),
            "shortName": ticker,
            "longName": ticker,
            # Supplement with .info for fields fast_info doesn't have
            "_from_fast_info": True,
        }

    def _fetch_full() -> dict:
        t = yf.Ticker(ticker, session=_SESSION)
        return t.info

    # Attempt 1: yfinance fast_info (lightweight)
    try:
        info = await asyncio.wait_for(asyncio.to_thread(_fetch_fast), timeout=_TIMEOUT_S)
        if info.get("quoteType"):
            logger.info("get_ticker_info: fast_info succeeded for %s", ticker)
            return info
    except Exception as e:
        logger.warning("get_ticker_info: fast_info failed for %s (%s), trying full .info", ticker, e)

    # Attempt 2: yfinance full .info
    try:
        info = await asyncio.wait_for(asyncio.to_thread(_fetch_full), timeout=_TIMEOUT_S)
        if info and info.get("quoteType"):
            logger.info("get_ticker_info: full .info succeeded for %s", ticker)
            return info
    except Exception as e:
        logger.warning("get_ticker_info: full .info failed for %s (%s), trying direct API", ticker, e)

    # Attempt 3: direct Yahoo Finance v8/chart API (bypasses yfinance crumb)
    try:
        logger.info("get_ticker_info: falling back to direct v8/chart API for %s", ticker)
        info = await _get_ticker_info_direct(ticker)
        logger.info("get_ticker_info: direct API succeeded for %s", ticker)
        return info
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            raise ValueError(
                "Yahoo Finance is rate-limiting this IP address. "
                "Stop all requests and wait 30 minutes before trying again."
            ) from e
        raise ValueError(f"Direct API failed for {ticker}: {e}") from e
    except Exception as e:
        raise ValueError(f"All data sources failed for {ticker}: {e}") from e


async def get_financials(ticker: str) -> dict:
    """Return annual income statement, balance sheet, and cash flow as lists of dicts.

    Keys: income_stmt, balance_sheet, cashflow — each is a list[dict] (JSON-safe).
    Returns empty lists for each on failure (non-critical).
    """
    def _fetch() -> dict:
        t = yf.Ticker(ticker, session=_SESSION)
        return {
            "income_stmt": t.financials,
            "balance_sheet": t.balance_sheet,
            "cashflow": t.cashflow,
        }

    try:
        raw = await asyncio.wait_for(
            asyncio.to_thread(_fetch),
            timeout=_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        logger.warning("get_financials: timeout for %s", ticker)
        return {"income_stmt": [], "balance_sheet": [], "cashflow": []}
    except Exception as e:
        logger.warning("get_financials: failed for %s: %s", ticker, e)
        return {"income_stmt": [], "balance_sheet": [], "cashflow": []}

    return {
        "income_stmt": _df_to_records(raw.get("income_stmt")),
        "balance_sheet": _df_to_records(raw.get("balance_sheet")),
        "cashflow": _df_to_records(raw.get("cashflow")),
    }


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


async def get_price_history(ticker: str, period: str = "10y") -> dict:
    """Return OHLCV price history as a list of dicts.

    Each dict has: date, open, high, low, close, volume.
    Returns {"history": []} on failure (non-critical).
    """
    def _fetch() -> pd.DataFrame:
        t = yf.Ticker(ticker, session=_SESSION)
        return t.history(period=period)

    try:
        df = await asyncio.wait_for(
            asyncio.to_thread(_fetch),
            timeout=_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        logger.warning("get_price_history: timeout for %s", ticker)
        return {"history": []}
    except Exception as e:
        logger.warning("get_price_history: failed for %s: %s", ticker, e)
        return {"history": []}

    if df is None or df.empty:
        return {"history": []}

    records = []
    for ts, row in df.iterrows():
        records.append({
            "date": str(ts.date()),
            "open": float(row.get("Open", 0)),
            "high": float(row.get("High", 0)),
            "low": float(row.get("Low", 0)),
            "close": float(row.get("Close", 0)),
            "volume": int(row.get("Volume", 0)),
        })

    return {"history": records}


async def get_current_price(ticker: str) -> float:
    """Return the most recent closing price. Never cached.

    Raises ValueError if price is unavailable.
    """
    def _fetch() -> float:
        t = yf.Ticker(ticker, session=_SESSION)
        info = t.info
        # Prefer regularMarketPrice, fall back to previousClose
        price = info.get("regularMarketPrice") or info.get("currentPrice") or info.get("previousClose")
        return price

    try:
        price = await asyncio.wait_for(
            asyncio.to_thread(_fetch),
            timeout=_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        raise ValueError(f"Timeout fetching current price for {ticker}")
    except Exception as e:
        raise ValueError(f"Failed to fetch current price for {ticker}: {e}") from e

    if price is None:
        raise ValueError(f"Current price unavailable for {ticker}")

    return float(price)
