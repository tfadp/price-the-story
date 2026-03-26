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

# Module-level shared client — reuses TCP connections across parallel calls.
# Lazy-initialized on first use; reset to None when a new event loop is
# detected (e.g. between test runs) so the pool does not bind to a dead loop.
_FD_CLIENT: httpx.AsyncClient | None = None
_FD_CLIENT_LOOP_ID: int | None = None


def _get_fd_client() -> httpx.AsyncClient:
    """Return the shared AsyncClient.

    Creates a new client when first called, or when the running event loop has
    changed (detected by loop object identity). This keeps connection pooling in
    production (single long-lived loop) while staying safe in test environments
    that create a fresh loop per test.
    """
    global _FD_CLIENT, _FD_CLIENT_LOOP_ID
    import asyncio
    try:
        current_loop_id = id(asyncio.get_event_loop())
    except RuntimeError:
        current_loop_id = None
    if _FD_CLIENT is None or current_loop_id != _FD_CLIENT_LOOP_ID:
        _FD_CLIENT = httpx.AsyncClient(
            base_url=_BASE_URL,
            timeout=_TIMEOUT_S,
            follow_redirects=True,
        )
        _FD_CLIENT_LOOP_ID = current_loop_id
    return _FD_CLIENT


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
    params = {"ticker": ticker}

    resp = await _get_fd_client().get("/company/facts", headers=_headers(), params=params)

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
    params = {"ticker": ticker}

    resp = await _get_fd_client().get("/prices/snapshot", headers=_headers(), params=params)

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
    params = {"ticker": ticker, "period": "annual", "limit": limit}

    try:
        resp = await _get_fd_client().get("/financials/income-statements", headers=_headers(), params=params)
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
    params = {"ticker": ticker, "period": "annual", "limit": limit}

    try:
        resp = await _get_fd_client().get("/financials/balance-sheets", headers=_headers(), params=params)
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
    params = {"ticker": ticker, "period": "annual", "limit": limit}

    try:
        resp = await _get_fd_client().get("/financials/cash-flow-statements", headers=_headers(), params=params)
        resp.raise_for_status()
        data = resp.json()
        return data.get("cash_flow_statements") or []
    except Exception as e:
        logger.warning("get_cash_flow_statements: failed for %s: %s", ticker, e)
        return []
