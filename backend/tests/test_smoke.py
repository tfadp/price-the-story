"""
Unit tests for Price the Story API.

All external data clients are patched in conftest.py — these tests never
hit the network. They verify routing, validation, and response shape.
"""
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.main import app  # noqa: E402

client = TestClient(app)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

def test_health_returns_ok():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# Happy path — valid US tickers
# ---------------------------------------------------------------------------

def test_analyze_aapl_returns_200():
    """Valid US ticker returns 200 with required top-level fields."""
    r = client.post("/analyze-ticker", json={"ticker": "AAPL"})
    assert r.status_code == 200
    data = r.json()
    assert data["ticker"] == "AAPL"
    assert data["as_of"] is not None


def test_analyze_aapl_has_valid_segment():
    """Classifier must populate segment from the allowed enum values."""
    r = client.post("/analyze-ticker", json={"ticker": "AAPL"})
    assert r.status_code == 200
    data = r.json()
    assert data.get("segment") in (
        "large_cap_blue_chip", "mid_cap", "small_cap_high_vol", "other", None
    )


def test_analyze_default_cagr():
    """Default target_cagr (0.10) is accepted without error."""
    r = client.post("/analyze-ticker", json={"ticker": "MSFT"})
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# Input validation — sad paths
# ---------------------------------------------------------------------------

def test_invalid_ticker_rejected():
    """Ticker with invalid characters is rejected with 422."""
    r = client.post("/analyze-ticker", json={"ticker": "HSBA.L"})
    assert r.status_code == 422


def test_ticker_too_long_rejected():
    """Ticker longer than 5 chars is rejected with 422."""
    r = client.post("/analyze-ticker", json={"ticker": "TOOLONG"})
    assert r.status_code == 422


def test_empty_ticker_rejected():
    """Empty ticker is rejected with 422."""
    r = client.post("/analyze-ticker", json={"ticker": ""})
    assert r.status_code == 422


def test_target_cagr_too_low_rejected():
    """target_cagr below 0.01 is rejected with 422."""
    r = client.post("/analyze-ticker", json={"ticker": "AAPL", "target_cagr": 0.0})
    assert r.status_code == 422


def test_target_cagr_too_high_rejected():
    """target_cagr above 10.0 is rejected with 422."""
    r = client.post("/analyze-ticker", json={"ticker": "AAPL", "target_cagr": 11.0})
    assert r.status_code == 422


def test_horizon_out_of_range_rejected():
    """Horizon value above 30 years is rejected with 422."""
    r = client.post("/analyze-ticker", json={"ticker": "AAPL", "horizons": [50]})
    assert r.status_code == 422


def test_too_many_horizons_rejected():
    """More than 4 horizon values is rejected with 422."""
    r = client.post("/analyze-ticker", json={"ticker": "AAPL", "horizons": [1, 2, 3, 4, 5]})
    assert r.status_code == 422


def test_negative_entry_price_rejected():
    """Negative entry_price is rejected with 422."""
    r = client.post("/analyze-ticker", json={"ticker": "AAPL", "entry_price": -1.0})
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Fallback — FD transport failure falls back to yfinance
# ---------------------------------------------------------------------------

def test_fd_transport_failure_falls_back_to_yfinance():
    """When Financial Datasets raises ConnectError, classifier falls back to yfinance."""
    import httpx

    with (
        patch(
            "app.data.financial_datasets_client.get_company_facts",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectError("FD unreachable"),
        ),
        patch(
            "app.data.financial_datasets_client.get_snapshot_price",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectError("FD unreachable"),
        ),
    ):
        r = client.post("/analyze-ticker", json={"ticker": "AAPL"})
        # Should succeed via yfinance fallback, not crash with 500
        assert r.status_code == 200
        data = r.json()
        assert data["ticker"] == "AAPL"


# ---------------------------------------------------------------------------
# Error response — 500s must not leak internals
# ---------------------------------------------------------------------------

def test_pipeline_500_does_not_leak_internals():
    """A pipeline crash returns a generic message, not a raw exception string."""
    with patch(
        "app.graph.graph.ainvoke",
        new_callable=AsyncMock,
        side_effect=RuntimeError("secret internal detail"),
    ):
        r = client.post("/analyze-ticker", json={"ticker": "AAPL"})
        assert r.status_code == 500
        body = r.json()
        assert "secret internal detail" not in body.get("detail", "")
        assert "Analysis failed" in body.get("detail", "")
