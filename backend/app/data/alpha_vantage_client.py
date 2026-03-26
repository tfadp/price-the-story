"""
Async REST client for Alpha Vantage (alphavantage.co).

Primary replacement for yfinance for all market data:
  - get_ticker_info    → OVERVIEW + GLOBAL_QUOTE (parallel)
  - get_current_price  → GLOBAL_QUOTE
  - get_price_history  → TIME_SERIES_DAILY (≤1y) or TIME_SERIES_WEEKLY (>1y)
  - get_financials     → INCOME_STATEMENT + BALANCE_SHEET + CASH_FLOW (parallel)

yfinance is kept ONLY for get_analyst_data (AV has no analyst estimates endpoint).

All functions are async via httpx.AsyncClient. The API key is read from
settings at call time so tests can patch it freely.
"""
import asyncio
import logging
from datetime import date, timedelta
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.alphavantage.co/query"
_TIMEOUT_S = 20


def _key() -> str:
    return settings.alpha_vantage_api_key


def _safe_float(val) -> Optional[float]:
    try:
        if val is None or val == "None" or val == "N/A" or val == "-":
            return None
        return float(str(val).replace(",", ""))
    except (ValueError, TypeError):
        return None


async def _get(params: dict) -> dict:
    """Single GET request to Alpha Vantage. Raises httpx.HTTPStatusError on 4xx/5xx."""
    params["apikey"] = _key()
    async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
        resp = await client.get(_BASE_URL, params=params)
    resp.raise_for_status()
    data = resp.json()
    # AV returns a plain dict with an "Information" key when rate-limited or on error
    if "Information" in data:
        raise ValueError(f"Alpha Vantage API limit or error: {data['Information']}")
    if "Error Message" in data:
        raise ValueError(f"Alpha Vantage error: {data['Error Message']}")
    return data


async def get_ticker_info(ticker: str) -> dict:
    """Fetch company overview + current quote in parallel.

    Returns a dict with the same keys that yfinance_client.get_ticker_info()
    returned so callers need no changes.

    Raises ValueError if the ticker is not found or AV returns an error.
    """
    overview_data, quote_data = await asyncio.gather(
        _get({"function": "OVERVIEW", "symbol": ticker}),
        _get({"function": "GLOBAL_QUOTE", "symbol": ticker}),
        return_exceptions=True,
    )

    # If both failed, raise
    if isinstance(overview_data, Exception) and isinstance(quote_data, Exception):
        raise ValueError(f"Alpha Vantage unavailable for {ticker}: {overview_data}") from overview_data

    overview: dict = overview_data if not isinstance(overview_data, Exception) else {}
    quote_raw: dict = quote_data if not isinstance(quote_data, Exception) else {}
    quote: dict = quote_raw.get("Global Quote", {})

    # A valid OVERVIEW has at least a Symbol key
    if not overview.get("Symbol") and not quote.get("01. symbol"):
        raise ValueError(f"Ticker not found: {ticker} (Alpha Vantage returned empty overview and quote)")

    market_cap = _safe_float(overview.get("MarketCapitalization")) or 0
    # Fallback: compute from shares × price if AV didn't populate market cap
    if not market_cap:
        shares = _safe_float(overview.get("SharesOutstanding")) or 0
        price = _safe_float(quote.get("05. price")) or 0
        if shares and price:
            market_cap = shares * price

    return {
        "quoteType": "EQUITY",
        "exchange": overview.get("Exchange", ""),
        "marketCap": market_cap,
        "regularMarketPrice": _safe_float(quote.get("05. price")) or 0,
        "regularMarketVolume": _safe_float(quote.get("06. volume")) or 0,
        "averageDailyVolume10Day": _safe_float(quote.get("06. volume")) or 0,
        "previousClose": _safe_float(quote.get("08. previous close")) or 0,
        "shortName": overview.get("Name", ticker),
        "longName": overview.get("Name", ticker),
        "trailingPE": _safe_float(overview.get("PERatio")),
        "sharesOutstanding": _safe_float(overview.get("SharesOutstanding")),
        "currency": overview.get("Currency", "USD"),
        "_from_alpha_vantage": True,
    }


async def get_current_price(ticker: str) -> float:
    """Return the most recent price from GLOBAL_QUOTE.

    Raises ValueError if unavailable.
    """
    data = await _get({"function": "GLOBAL_QUOTE", "symbol": ticker})
    quote = data.get("Global Quote", {})
    price = _safe_float(quote.get("05. price"))
    if price is None:
        raise ValueError(f"Current price unavailable for {ticker} (Alpha Vantage)")
    return price


async def get_price_history(ticker: str, period: str = "10y") -> dict:
    """Return OHLCV price history as a list of dicts sorted oldest-first.

    Each dict: {date, open, high, low, close, volume}.
    Uses TIME_SERIES_WEEKLY for periods > 1 year (cheaper, sufficient for vol calc).
    Uses TIME_SERIES_DAILY for periods ≤ 1 year (more granular).

    Returns {"history": []} on failure (non-critical).
    """
    # Determine years requested
    period_years = {"5d": 0, "1mo": 0, "3mo": 0, "6mo": 0, "1y": 1, "2y": 2, "5y": 5, "10y": 10}
    years = period_years.get(period, 10)

    try:
        if years > 1:
            # Weekly data — full history (20+ years)
            data = await _get({
                "function": "TIME_SERIES_WEEKLY",
                "symbol": ticker,
                "outputsize": "full",
            })
            series = data.get("Weekly Time Series", {})
            open_k, high_k, low_k, close_k, vol_k = "1. open", "2. high", "3. low", "4. close", "5. volume"
        else:
            # Daily data — full for ≤1y means we get the last 20 years but slice to needed range
            data = await _get({
                "function": "TIME_SERIES_DAILY",
                "symbol": ticker,
                "outputsize": "full",
            })
            series = data.get("Time Series (Daily)", {})
            open_k, high_k, low_k, close_k, vol_k = "1. open", "2. high", "3. low", "4. close", "5. volume"

        if not series:
            return {"history": []}

        # Cutoff date for filtering
        cutoff = date.today() - timedelta(days=max(years * 365, 7))

        records = []
        for date_str, bar in series.items():
            try:
                bar_date = date.fromisoformat(date_str)
            except ValueError:
                continue
            if bar_date < cutoff:
                continue
            records.append({
                "date": date_str,
                "open": _safe_float(bar.get(open_k)) or 0,
                "high": _safe_float(bar.get(high_k)) or 0,
                "low": _safe_float(bar.get(low_k)) or 0,
                "close": _safe_float(bar.get(close_k)) or 0,
                "volume": int(_safe_float(bar.get(vol_k)) or 0),
            })

        # Sort oldest-first (AV returns newest-first)
        records.sort(key=lambda r: r["date"])
        return {"history": records}

    except Exception as e:
        logger.warning("get_price_history (AV): failed for %s period=%s: %s", ticker, period, e)
        return {"history": []}


async def get_financials(ticker: str) -> dict:
    """Return annual income statement, balance sheet, and cash flow.

    Keys: income_stmt, balance_sheet, cashflow — each is a list[dict].
    Field names use Alpha Vantage's camelCase convention, which is handled
    by fundamentals.py's _find_field() case-insensitive lookup.
    Returns empty lists for each on failure (non-critical).
    """
    try:
        income_data, balance_data, cashflow_data = await asyncio.gather(
            _get({"function": "INCOME_STATEMENT", "symbol": ticker}),
            _get({"function": "BALANCE_SHEET", "symbol": ticker}),
            _get({"function": "CASH_FLOW", "symbol": ticker}),
            return_exceptions=True,
        )

        def _parse_annual(data, key: str = "annualReports") -> list[dict]:
            if isinstance(data, Exception):
                return []
            reports = data.get(key, [])
            # Convert all string numbers to floats; keep strings that are non-numeric
            result = []
            for report in reports:
                row = {}
                for k, v in report.items():
                    f = _safe_float(v)
                    row[k] = f if f is not None else v
                result.append(row)
            return result

        return {
            "income_stmt": _parse_annual(income_data),
            "balance_sheet": _parse_annual(balance_data),
            "cashflow": _parse_annual(cashflow_data),
        }

    except Exception as e:
        logger.warning("get_financials (AV): failed for %s: %s", ticker, e)
        return {"income_stmt": [], "balance_sheet": [], "cashflow": []}
