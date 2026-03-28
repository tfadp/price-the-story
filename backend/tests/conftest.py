"""
pytest fixtures — patch all external data clients so tests never hit the network.

Patches are applied at the point of use, because the nodes import functions
directly into module scope.
"""
from contextlib import ExitStack
from unittest.mock import AsyncMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fake data returned by mocked clients
# ---------------------------------------------------------------------------

_FAKE_SNAPSHOT_PRICE = 175.0
_FAKE_AAPL_FACTS = {
    "quoteType": "EQUITY",
    "exchange": "NMS",
    "marketCap": 3_000_000_000_000,
    "regularMarketPrice": _FAKE_SNAPSHOT_PRICE,
    "averageDailyVolume10Day": 60_000_000,
    "regularMarketVolume": 60_000_000,
    "previousClose": 174.0,
    "shortName": "Apple Inc.",
    "longName": "Apple Inc.",
}

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
        for i in range(252)
    ]
}

_FAKE_INCOME_STATEMENTS = [
    {"revenue": 383_285_000_000, "gross_profit": 152_836_000_000, "operating_income": 111_852_000_000, "net_income": 99_803_000_000, "eps_diluted": 6.11},
    {"revenue": 394_328_000_000, "gross_profit": 169_106_000_000, "operating_income": 120_216_000_000, "net_income": 104_956_000_000, "eps_diluted": 6.13},
    {"revenue": 416_161_000_000, "gross_profit": 170_782_000_000, "operating_income": 123_216_000_000, "net_income": 112_010_000_000, "eps_diluted": 6.42},
]

_FAKE_BALANCE_SHEETS = [
    {"total_equity": 62_146_000_000, "total_debt": 109_106_000_000, "cash_and_equivalents": 48_304_000_000},
    {"total_equity": 67_155_000_000, "total_debt": 120_660_000_000, "cash_and_equivalents": 51_355_000_000},
    {"total_equity": 74_011_000_000, "total_debt": 120_000_000_000, "cash_and_equivalents": 67_155_000_000},
]

_FAKE_CASH_FLOW = [
    {"free_cash_flow": 93_500_000_000},
    {"free_cash_flow": 104_000_000_000},
    {"free_cash_flow": 110_000_000_000},
]


@pytest.fixture(autouse=True)
def mock_external_clients():
    """Patch all outbound network calls so tests are deterministic and offline."""
    from app.main import limiter as app_limiter, analysis_cache, inflight_analyses
    from app.config import settings

    app_limiter.reset()
    analysis_cache.clear()
    inflight_analyses.clear()
    settings.internal_api_key = ""
    patchers = [
        # classifier.py
        patch("app.nodes.classifier.get_company_facts", new_callable=AsyncMock, return_value={"exchange": "NMS", "market_cap": 3_000_000_000_000, "name": "Apple Inc."}),
        patch("app.nodes.classifier.get_snapshot_price", new_callable=AsyncMock, return_value=_FAKE_SNAPSHOT_PRICE),
        patch("app.nodes.classifier.get_market_cap", new_callable=AsyncMock, return_value=3_000_000_000_000),
        patch("app.nodes.classifier.get_ticker_info", new_callable=AsyncMock, return_value=_FAKE_AAPL_FACTS),
        patch("app.nodes.classifier.get_price_history", new_callable=AsyncMock, return_value=_FAKE_PRICE_HISTORY),
        patch("app.nodes.classifier.get_current_price", new_callable=AsyncMock, return_value=_FAKE_SNAPSHOT_PRICE),
        # fundamentals.py
        patch("app.nodes.fundamentals.get_income_statements", new_callable=AsyncMock, return_value=_FAKE_INCOME_STATEMENTS),
        patch("app.nodes.fundamentals.get_balance_sheets", new_callable=AsyncMock, return_value=_FAKE_BALANCE_SHEETS),
        patch("app.nodes.fundamentals.get_cash_flow_statements", new_callable=AsyncMock, return_value=_FAKE_CASH_FLOW),
        patch("app.nodes.fundamentals.get_snapshot_price", new_callable=AsyncMock, return_value=_FAKE_SNAPSHOT_PRICE),
        patch("app.nodes.fundamentals.get_financials", new_callable=AsyncMock, return_value={"income_stmt": [], "balance_sheet": [], "cashflow": []}),
        patch("app.nodes.fundamentals.get_current_price", new_callable=AsyncMock, return_value=_FAKE_SNAPSHOT_PRICE),
        # valuation.py
        patch("app.nodes.valuation.get_snapshot_price", new_callable=AsyncMock, return_value=_FAKE_SNAPSHOT_PRICE),
        patch("app.nodes.valuation.get_current_price", new_callable=AsyncMock, return_value=_FAKE_SNAPSHOT_PRICE),
        # analyst_estimates.py
        patch("app.nodes.analyst_estimates.get_analyst_data", new_callable=AsyncMock, return_value={}),
        # news_sentiment.py
        patch(
            "app.nodes.news_sentiment.get_options_sentiment",
            new_callable=AsyncMock,
            return_value={
                "expiry": "2027-01-15",
                "days_to_expiry": 420,
                "atm_strike": 175.0,
                "implied_volatility": 0.22,
                "implied_move_pct": 0.236,
                "call_put_oi_ratio": 1.8,
                "lean": "bullish",
                "source": "yfinance",
            },
        ),
        # macro.py
        patch("app.nodes.macro.get_price_history", new_callable=AsyncMock, return_value=_FAKE_PRICE_HISTORY),
        # Source modules are patched too, so direct imports elsewhere stay offline.
        patch("app.data.alpha_vantage_client.get_ticker_info", new_callable=AsyncMock, return_value=_FAKE_AAPL_FACTS),
        patch("app.data.yfinance_client.get_price_history", new_callable=AsyncMock, return_value=_FAKE_PRICE_HISTORY),
        patch("app.data.yfinance_client.get_current_price", new_callable=AsyncMock, return_value=_FAKE_SNAPSHOT_PRICE),
        patch("app.data.yfinance_client.get_financials", new_callable=AsyncMock, return_value={"income_stmt": [], "balance_sheet": [], "cashflow": []}),
        patch("app.data.yfinance_client.get_analyst_data", new_callable=AsyncMock, return_value={}),
        patch("app.data.financial_datasets_client.get_company_facts", new_callable=AsyncMock, return_value={"exchange": "NMS", "market_cap": 3_000_000_000_000, "name": "Apple Inc."}),
        patch("app.data.financial_datasets_client.get_snapshot_price", new_callable=AsyncMock, return_value=_FAKE_SNAPSHOT_PRICE),
        patch("app.data.financial_datasets_client.get_income_statements", new_callable=AsyncMock, return_value=[]),
        patch("app.data.financial_datasets_client.get_balance_sheets", new_callable=AsyncMock, return_value=[]),
        patch("app.data.financial_datasets_client.get_cash_flow_statements", new_callable=AsyncMock, return_value=[]),
    ]
    with ExitStack() as stack:
        for p in patchers:
            stack.enter_context(p)
        yield
