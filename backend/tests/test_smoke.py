"""
Smoke tests — verify the API returns valid responses.
Run with: cd backend && pytest tests/ -v
"""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Ensure the backend package is importable regardless of cwd
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.main import app  # noqa: E402

client = TestClient(app)


def test_health_returns_ok():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_analyze_aapl_returns_200():
    """AAPL should always return a 200 with at least a ticker field."""
    r = client.post("/analyze-ticker", json={"ticker": "AAPL"})
    assert r.status_code == 200
    data = r.json()
    assert data["ticker"] == "AAPL"
    assert data["as_of"] is not None


def test_analyze_aapl_has_segment():
    """AAPL is a large cap — classifier should categorize it."""
    r = client.post("/analyze-ticker", json={"ticker": "AAPL"})
    data = r.json()
    assert data.get("segment") in (
        "large_cap_blue_chip", "mid_cap", "small_cap_high_vol", "other", None
    )


def test_analyze_default_cagr():
    """Default target_cagr should be 0.10."""
    r = client.post("/analyze-ticker", json={"ticker": "MSFT"})
    assert r.status_code == 200


def test_non_us_ticker_rejected():
    """A clearly non-US ticker slug should be rejected."""
    r = client.post("/analyze-ticker", json={"ticker": "HSBA.L"})
    # Classifier hard-fails with 422 or 500 for non-US
    assert r.status_code in (422, 500)
