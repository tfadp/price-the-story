"""
Async client for the Financial Datasets API.

This module exposes the same function signatures used throughout the codebase.
In tests, these functions are patched by conftest.py — they never hit the network
during test runs.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Will be set from config when the real implementation is wired up
_FD_BASE_URL = "https://api.financialdatasets.ai"
_API_KEY: Optional[str] = None


async def get_company_facts(ticker: str) -> dict:
    """Return company metadata (name, exchange, market_cap, description) from Financial Datasets.

    Raises httpx.ConnectError / httpx.TimeoutException on transport failure.
    Raises ValueError with '404' in the message when the ticker is not found.
    """
    raise NotImplementedError(
        "financial_datasets_client is not yet implemented. "
        "Callers must handle the fallback to yfinance."
    )


async def get_snapshot_price(ticker: str) -> float:
    """Return the latest snapshot price for the given ticker.

    Raises httpx.ConnectError / httpx.TimeoutException on transport failure.
    Raises ValueError with '404' in the message when the ticker is not found.
    """
    raise NotImplementedError(
        "financial_datasets_client is not yet implemented. "
        "Callers must handle the fallback to yfinance."
    )


async def get_income_statements(ticker: str, limit: int = 5) -> list[dict]:
    """Return annual income statements from Financial Datasets.

    Returns an empty list on failure — callers treat this as non-critical.
    """
    raise NotImplementedError("financial_datasets_client is not yet implemented.")


async def get_balance_sheets(ticker: str, limit: int = 5) -> list[dict]:
    """Return annual balance sheets from Financial Datasets.

    Returns an empty list on failure — callers treat this as non-critical.
    """
    raise NotImplementedError("financial_datasets_client is not yet implemented.")


async def get_cash_flow_statements(ticker: str, limit: int = 5) -> list[dict]:
    """Return annual cash flow statements from Financial Datasets.

    Returns an empty list on failure — callers treat this as non-critical.
    """
    raise NotImplementedError("financial_datasets_client is not yet implemented.")
