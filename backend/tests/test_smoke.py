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
from app.config import settings  # noqa: E402

client = TestClient(app)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

def test_health_returns_ok():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_auth_required_when_internal_api_key_is_configured():
    settings.internal_api_key = "secret-key"
    try:
        r = client.post("/analyze-ticker", json={"ticker": "AAPL"})
        assert r.status_code == 401

        r = client.post(
            "/analyze-ticker",
            json={"ticker": "AAPL"},
            headers={"x-api-key": "secret-key"},
        )
        assert r.status_code == 200
    finally:
        settings.internal_api_key = ""


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


def test_large_cap_includes_options_sentiment_signal():
    r = client.post("/analyze-ticker", json={"ticker": "AAPL"})
    assert r.status_code == 200
    data = r.json()
    assert data["sentiment"]["options_sentiment"]["lean"] == "bullish"
    assert data["sentiment"]["options_sentiment"]["thesis_alignment"] == "supports_thesis"
    assert data["sentiment"]["options_sentiment"]["summary"]


def test_identical_requests_reuse_cached_analysis_result():
    async def fake_ainvoke(state):
        return state

    with patch("app.main.graph.ainvoke", new_callable=AsyncMock, side_effect=fake_ainvoke) as ainvoke:
        r1 = client.post("/analyze-ticker", json={"ticker": "AAPL"})
        r2 = client.post("/analyze-ticker", json={"ticker": "AAPL"})

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert ainvoke.await_count == 1


def test_large_cap_classification_survives_missing_liquidity_data():
    """Apple-like names should stay large-cap even if volume data is sparse."""
    with (
        patch(
            "app.nodes.classifier.get_company_facts",
            new_callable=AsyncMock,
            return_value={"exchange": "NMS", "market_cap": None, "name": "Apple Inc."},
        ),
        patch(
            "app.nodes.classifier.get_snapshot_price",
            new_callable=AsyncMock,
            return_value=175.0,
        ),
        patch(
            "app.nodes.classifier.get_market_cap",
            new_callable=AsyncMock,
            return_value=3_000_000_000_000,
        ),
        patch(
            "app.nodes.classifier.get_price_history",
            new_callable=AsyncMock,
            return_value={"history": []},
        ),
    ):
        r = client.post("/analyze-ticker", json={"ticker": "AAPL"})

    assert r.status_code == 200
    data = r.json()
    assert data["segment"] == "large_cap_blue_chip"
    assert data["data_quality"] == "high"
    assert data["probability_engine"]["enabled"] is True
    assert data["confidence_verdict"] != "insufficient_data"


def test_probability_engine_is_sensitive_to_entry_price_and_exposes_richer_outputs():
    """Supported large caps should expose a graded entry-dependence surface."""
    with (
        patch(
            "app.nodes.classifier.get_snapshot_price",
            new_callable=AsyncMock,
            return_value=100.0,
        ),
        patch(
            "app.nodes.valuation.get_snapshot_price",
            new_callable=AsyncMock,
            return_value=100.0,
        ),
    ):
        r = client.post(
            "/analyze-ticker",
            json={
                "ticker": "AAPL",
                "entry_price": 95.0,
                "target_cagr": 0.015,
                "horizons": [1, 3, 5, 10],
            },
        )

    assert r.status_code == 200
    data = r.json()
    prob = data["probability_engine"]

    assert prob["enabled"] is True
    assert prob["confidence_tier"] in {"medium", "low"}
    assert prob["methodology_notes"]
    assert prob["calibration_notes"]
    assert prob["scenario_weights"]
    assert abs(sum(prob["scenario_weights"].values()) - 1.0) < 1e-6

    assert len(prob["horizons"]) == 4
    assert len(prob["entry_dependence"]) >= 4
    assert len(prob["downside_risk"]) == 4

    entry_probabilities = [
        (row["entry_price"], (row["prob_ge_target_low"] + row["prob_ge_target_high"]) / 2)
        for row in prob["entry_dependence"]
    ]
    assert entry_probabilities == sorted(entry_probabilities, key=lambda item: item[0])

    midpoints = [probability for _, probability in entry_probabilities]
    assert len(set(midpoints)) > 1
    assert midpoints == sorted(midpoints, reverse=True)
    assert midpoints[0] > midpoints[-1]

    for row in prob["downside_risk"]:
        assert 0.0 <= row["prob_le_zero_cagr_low"] <= row["prob_le_zero_cagr_high"] <= 1.0


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
# Probability/data sufficiency — low-quality inputs should degrade explicitly
# ---------------------------------------------------------------------------

def test_small_cap_low_data_disables_probability_and_marks_insufficient_data():
    """A genuinely low-quality ticker should disable probability and confidence."""
    with (
        patch(
            "app.nodes.classifier.get_company_facts",
            new_callable=AsyncMock,
            return_value={"exchange": "NMS", "market_cap": 750_000_000, "name": "TinyCo"},
        ),
        patch(
            "app.nodes.classifier.get_snapshot_price",
            new_callable=AsyncMock,
            return_value=4.25,
        ),
        patch(
            "app.nodes.classifier.get_market_cap",
            new_callable=AsyncMock,
            return_value=750_000_000,
        ),
        patch(
            "app.nodes.classifier.get_price_history",
            new_callable=AsyncMock,
            return_value={"history": []},
        ),
    ):
        r = client.post("/analyze-ticker", json={"ticker": "TINY"})

    assert r.status_code == 200
    data = r.json()
    assert data["segment"] == "small_cap_high_vol"
    assert data["data_quality"] == "low"
    assert data["probability_engine"]["enabled"] is False
    assert data["probability_engine"]["reason_disabled"]
    assert data["confidence_verdict"] == "insufficient_data"
    assert data["stress_test"] is None


def test_small_cap_omits_options_sentiment():
    with (
        patch(
            "app.nodes.classifier.get_company_facts",
            new_callable=AsyncMock,
            return_value={"exchange": "NMS", "market_cap": 750_000_000, "name": "TinyCo"},
        ),
        patch(
            "app.nodes.classifier.get_snapshot_price",
            new_callable=AsyncMock,
            return_value=4.25,
        ),
        patch(
            "app.nodes.classifier.get_market_cap",
            new_callable=AsyncMock,
            return_value=750_000_000,
        ),
        patch(
            "app.nodes.classifier.get_price_history",
            new_callable=AsyncMock,
            return_value={"history": []},
        ),
    ):
        r = client.post("/analyze-ticker", json={"ticker": "TINY"})

    assert r.status_code == 200
    data = r.json()
    assert data.get("sentiment") is None
    assert data["section_statuses"]["news_sentiment"]["status"] == "partial"


def test_large_cap_with_weak_fundamentals_is_marked_insufficient_data():
    """Even a mega-cap should stop short of publishing odds if fundamentals are too weak."""
    with (
        patch(
            "app.nodes.fundamentals.get_income_statements",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "app.nodes.fundamentals.get_balance_sheets",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "app.nodes.fundamentals.get_cash_flow_statements",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "app.nodes.fundamentals.get_financials",
            new_callable=AsyncMock,
            return_value={"income_stmt": [], "balance_sheet": [], "cashflow": []},
        ),
    ):
        r = client.post("/analyze-ticker", json={"ticker": "AAPL"})

    assert r.status_code == 200
    data = r.json()
    assert data["segment"] == "large_cap_blue_chip"
    assert data["data_quality"] == "high"
    assert data["probability_engine"]["enabled"] is False
    assert data["probability_engine"]["reason_disabled"]
    assert data["section_statuses"]["probability_engine"]["status"] == "partial"
    assert data["confidence_verdict"] == "insufficient_data"
    assert data["stress_test"] is None


# ---------------------------------------------------------------------------
# Fallback — FD transport failure falls back to yfinance
# ---------------------------------------------------------------------------

def test_fd_transport_failure_falls_back_to_alpha_vantage():
    """When Financial Datasets fails, classifier falls back to Alpha Vantage."""

    with (
        patch(
            "app.nodes.classifier.get_company_facts",
            new_callable=AsyncMock,
            side_effect=ValueError("FD unreachable"),
        ),
        patch(
            "app.nodes.classifier.get_snapshot_price",
            new_callable=AsyncMock,
            side_effect=ValueError("FD unreachable"),
        ),
    ):
        r = client.post("/analyze-ticker", json={"ticker": "AAPL"})

    # Should succeed via Alpha Vantage / yfinance fallback, not crash with 500
    assert r.status_code == 200
    data = r.json()
    assert data["ticker"] == "AAPL"
    assert data["segment"] == "large_cap_blue_chip"
    assert data["section_statuses"]["classifier"]["source"] == "alpha_vantage"


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
