"""
Async REST client for Financial Datasets (financialdatasets.ai).

This is the primary data source for Price the Story. yfinance is kept as a
fallback in each node but should not be reached under normal conditions.

All functions are async via httpx.AsyncClient. The API key is read from
settings at call time (not at import time) so tests can patch it freely.
"""
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.financialdatasets.ai"

# Seconds before we give up on a single HTTP request
_TIMEOUT_S = 15


def _headers() -> dict:
    """Build auth headers from live config — called inside request functions.

    We defer reading the key until call time so test fixtures can override
    settings.financial_datasets_api_key without import-time side effects.
    """
    return {"X-API-KEY": settings.financial_datasets_api_key}


async def get_company_facts(ticker: str) -> dict:
    """Fetch company metadata: name, exchange, market_cap, description.

    Raises ValueError on 404 (ticker not found) or 429 (rate limited).
    """
    url = f"{_BASE_URL}/company/facts"
    params = {"ticker": ticker}

    async with httpx.AsyncClient(timeout=_TIMEOUT_S, follow_redirects=True) as client:
        resp = await client.get(url, headers=_headers(), params=params)

    if resp.status_code == 404:
        raise ValueError(f"Ticker not found: {ticker} (Financial Datasets returned 404)")
    if resp.status_code == 429:
        raise ValueError(
            f"Financial Datasets rate limit exceeded for {ticker}. "
            "Back off and retry after a short delay."
        )
    resp.raise_for_status()

    data = resp.json()
    company_facts = data.get("company_facts")
    if not company_facts:
        raise ValueError(f"Ticker not found: {ticker} (empty company_facts in response)")

    return company_facts


async def get_snapshot_price(ticker: str) -> float:
    """Fetch the current/latest price for a ticker.

    Returns the snapshot.price as a float.
    Raises ValueError if no price is available or the ticker is not found.
    """
    url = f"{_BASE_URL}/prices/snapshot"
    params = {"ticker": ticker}

    async with httpx.AsyncClient(timeout=_TIMEOUT_S, follow_redirects=True) as client:
        resp = await client.get(url, headers=_headers(), params=params)

    if resp.status_code == 404:
        raise ValueError(f"Ticker not found: {ticker} (Financial Datasets snapshot returned 404)")
    if resp.status_code == 429:
        raise ValueError(
            f"Financial Datasets rate limit exceeded for {ticker}. "
            "Back off and retry after a short delay."
        )
    resp.raise_for_status()

    data = resp.json()
    snapshot = data.get("snapshot") or {}
    price = snapshot.get("price")
    if price is None:
        raise ValueError(f"No price available for {ticker} in Financial Datasets snapshot")

    return float(price)


async def get_income_statements(ticker: str, limit: int = 5) -> list[dict]:
    """Fetch annual income statements, newest first.

    Returns an empty list on any failure — this data is supplementary and
    the pipeline must continue without it.
    """
    url = f"{_BASE_URL}/financials/income-statements"
    params = {"ticker": ticker, "period": "annual", "limit": limit}

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_S, follow_redirects=True) as client:
            resp = await client.get(url, headers=_headers(), params=params)
        resp.raise_for_status()
        data = resp.json()
        return data.get("income_statements") or []
    except Exception as e:
        logger.warning("get_income_statements: failed for %s: %s", ticker, e)
        return []


async def get_balance_sheets(ticker: str, limit: int = 5) -> list[dict]:
    """Fetch annual balance sheets, newest first.

    Returns an empty list on any failure — this data is supplementary and
    the pipeline must continue without it.
    """
    url = f"{_BASE_URL}/financials/balance-sheets"
    params = {"ticker": ticker, "period": "annual", "limit": limit}

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_S, follow_redirects=True) as client:
            resp = await client.get(url, headers=_headers(), params=params)
        resp.raise_for_status()
        data = resp.json()
        return data.get("balance_sheets") or []
    except Exception as e:
        logger.warning("get_balance_sheets: failed for %s: %s", ticker, e)
        return []


async def get_cash_flow_statements(ticker: str, limit: int = 5) -> list[dict]:
    """Fetch annual cash flow statements, newest first.

    Returns an empty list on any failure — this data is supplementary and
    the pipeline must continue without it.
    """
    url = f"{_BASE_URL}/financials/cash-flow-statements"
    params = {"ticker": ticker, "period": "annual", "limit": limit}

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_S, follow_redirects=True) as client:
            resp = await client.get(url, headers=_headers(), params=params)
        resp.raise_for_status()
        data = resp.json()
        return data.get("cash_flow_statements") or []
    except Exception as e:
        logger.warning("get_cash_flow_statements: failed for %s: %s", ticker, e)
        return []
