"""
Async REST client for Alpha Vantage (alphavantage.co).

Used for ONE thing: get_ticker_info, which calls the OVERVIEW + GLOBAL_QUOTE
endpoints to obtain company metadata (exchange, market cap, name) when
Financial Datasets is unavailable.

All other market data (current price, price history, financials) is handled
by yfinance_client.py.

All functions are async via httpx.AsyncClient. The API key is read from
settings at call time so tests can patch it freely.
"""
import asyncio
import logging
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


async def get_market_cap(ticker: str) -> float:
    """Fetch market cap from OVERVIEW — single call, respects 1 req/sec free tier.

    Used by the classifier supplement block when Financial Datasets returns
    no market cap. Returns 0.0 on any failure so the caller can fall through
    to history-derived volume for segment classification.
    """
    try:
        data = await _get({"function": "OVERVIEW", "symbol": ticker})
        market_cap = _safe_float(data.get("MarketCapitalization")) or 0
        if not market_cap:
            # Fallback: shares × price
            shares = _safe_float(data.get("SharesOutstanding")) or 0
            price = _safe_float(data.get("50DayMovingAverage")) or 0  # proxy if needed
            if shares and price:
                market_cap = shares * price
        return market_cap
    except Exception as e:
        logger.warning("get_market_cap (AV): failed for %s: %s", ticker, e)
        return 0.0


async def get_ticker_info(ticker: str) -> dict:
    """Fetch company overview + current quote in parallel.

    Returns a dict with exchange, market cap, price, and name fields so the
    classifier can validate the ticker without yfinance.

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
