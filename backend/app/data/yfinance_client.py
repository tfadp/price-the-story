"""
Thin async wrapper around yfinance (which is synchronous).
All calls use asyncio.to_thread so they don't block the event loop.
Every call is wrapped in asyncio.wait_for with a 10-second timeout.
"""
import asyncio
import logging
from typing import Optional

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

# How long we'll wait for any yfinance network call before giving up
_TIMEOUT_S = 10


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
        t = yf.Ticker(ticker)
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
        t = yf.Ticker(ticker)
        return t.info

    # Try fast_info first, fall back to full .info
    for attempt in range(2):
        try:
            if attempt == 0:
                info = await asyncio.wait_for(
                    asyncio.to_thread(_fetch_fast),
                    timeout=_TIMEOUT_S,
                )
                # fast_info succeeded — augment with a few .info fields if possible
                if info.get("quoteType"):
                    return info
                # fast_info gave us nothing useful, fall through to full .info

            info = await asyncio.wait_for(
                asyncio.to_thread(_fetch_full),
                timeout=_TIMEOUT_S,
            )
            if not info or info.get("quoteType") is None:
                raise ValueError(f"Ticker not found or unsupported: {ticker}")
            return info

        except asyncio.TimeoutError:
            if attempt == 0:
                logger.warning("get_ticker_info: timeout on attempt 1 for %s, retrying", ticker)
                await asyncio.sleep(2)
                continue
            raise ValueError(f"Timeout fetching info for {ticker}")
        except ValueError:
            raise
        except Exception as e:
            if attempt == 0:
                logger.warning("get_ticker_info: error on attempt 1 for %s (%s), retrying in 3s", ticker, e)
                await asyncio.sleep(3)
                continue
            raise ValueError(f"Failed to fetch ticker info for {ticker}: {e}") from e

    raise ValueError(f"Failed to fetch ticker info for {ticker} after retries")


async def get_financials(ticker: str) -> dict:
    """Return annual income statement, balance sheet, and cash flow as lists of dicts.

    Keys: income_stmt, balance_sheet, cashflow — each is a list[dict] (JSON-safe).
    Returns empty lists for each on failure (non-critical).
    """
    def _fetch() -> dict:
        t = yf.Ticker(ticker)
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

    Returns an empty dict on failure (non-critical).
    """
    def _fetch() -> dict:
        t = yf.Ticker(ticker)
        recommendations = t.recommendations
        earnings_estimate = t.earnings_estimate
        revenue_estimate = t.revenue_estimate
        eps_trend = t.eps_trend
        price_targets = getattr(t, "analyst_price_targets", None)
        earnings_history = t.earnings_history

        return {
            "recommendations": recommendations,
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
            # Reset index to include it as a column
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
        t = yf.Ticker(ticker)
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
        t = yf.Ticker(ticker)
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
