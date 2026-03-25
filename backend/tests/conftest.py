"""
pytest fixtures — patch all external data clients so tests never hit the network.

Patches are applied at the point of USE (the node modules that import functions
directly), not at the point of definition. This matches Python's patching rules:
patch where the name is looked up, not where it is defined.
"""
from unittest.mock import AsyncMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fake data returned by mocked clients
# ---------------------------------------------------------------------------

_FAKE_TICKER_INFO = {
    "quoteType": "EQUITY",
    "exchange": "NMS",
    "marketCap": 3_000_000_000_000,
    "regularMarketPrice": 175.0,
    "averageDailyVolume10Day": 60_000_000,
    "regularMarketVolume": 60_000_000,
    "previousClose": 174.0,
    "shortName": "Apple Inc.",
    "longName": "Apple Inc.",
}

_FAKE_SNAPSHOT_PRICE = 175.0

_FAKE_PRICE_HISTORY = {
    "history": [
        {
            "date": f"2024-01-{i + 1:02d}",
            "open": 170.0,
            "high": 180.0,
            "low": 165.0,
            "close": 175.0 + i * 0.1,
            "volume": 50_000_000,
        }
        for i in range(252)  # ~1 year of daily data — enough for vol calculation
    ]
}

_FAKE_FINANCIALS = {"income_stmt": [], "balance_sheet": [], "cashflow": []}


# ---------------------------------------------------------------------------
# Autouse fixture — active for every test in this session
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mock_external_clients():
    """Patch all outbound network calls so tests are deterministic and offline.

    Each patch targets the name as it appears in the module that imports it
    (the 'point of use'), not the source module. This is required because all
    nodes use `from app.data.yfinance_client import func` — creating local
    references that bypass patches on the source module.
    """
    with (
        # classifier.py imports
        patch(
            "app.nodes.classifier.get_ticker_info",
            new_callable=AsyncMock,
            return_value=_FAKE_TICKER_INFO,
        ),
        patch(
            "app.nodes.classifier.get_price_history",
            new_callable=AsyncMock,
            return_value=_FAKE_PRICE_HISTORY,
        ),
        patch(
            "app.nodes.classifier.get_current_price",
            new_callable=AsyncMock,
            return_value=_FAKE_SNAPSHOT_PRICE,
        ),
        # fundamentals.py imports
        patch(
            "app.nodes.fundamentals.get_financials",
            new_callable=AsyncMock,
            return_value=_FAKE_FINANCIALS,
        ),
        patch(
            "app.nodes.fundamentals.get_current_price",
            new_callable=AsyncMock,
            return_value=_FAKE_SNAPSHOT_PRICE,
        ),
        # valuation.py imports
        patch(
            "app.nodes.valuation.get_current_price",
            new_callable=AsyncMock,
            return_value=_FAKE_SNAPSHOT_PRICE,
        ),
        # analyst_estimates.py imports
        patch(
            "app.nodes.analyst_estimates.get_analyst_data",
            new_callable=AsyncMock,
            return_value={},
        ),
        # macro.py imports
        patch(
            "app.nodes.macro.get_price_history",
            new_callable=AsyncMock,
            return_value=_FAKE_PRICE_HISTORY,
        ),
        # Also patch the source module so any indirect callers are covered
        patch(
            "app.data.yfinance_client.get_ticker_info",
            new_callable=AsyncMock,
            return_value=_FAKE_TICKER_INFO,
        ),
        patch(
            "app.data.yfinance_client.get_price_history",
            new_callable=AsyncMock,
            return_value=_FAKE_PRICE_HISTORY,
        ),
        patch(
            "app.data.yfinance_client.get_current_price",
            new_callable=AsyncMock,
            return_value=_FAKE_SNAPSHOT_PRICE,
        ),
        patch(
            "app.data.yfinance_client.get_financials",
            new_callable=AsyncMock,
            return_value=_FAKE_FINANCIALS,
        ),
        patch(
            "app.data.yfinance_client.get_analyst_data",
            new_callable=AsyncMock,
            return_value={},
        ),
        # financial_datasets_client (no nodes use it yet — patched for future use)
        patch(
            "app.data.financial_datasets_client.get_company_facts",
            new_callable=AsyncMock,
            return_value={},
        ),
        patch(
            "app.data.financial_datasets_client.get_snapshot_price",
            new_callable=AsyncMock,
            return_value=_FAKE_SNAPSHOT_PRICE,
        ),
        patch(
            "app.data.financial_datasets_client.get_income_statements",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "app.data.financial_datasets_client.get_balance_sheets",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "app.data.financial_datasets_client.get_cash_flow_statements",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        yield
