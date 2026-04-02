"""
Phase D unit tests: news_sentiment node + get_company_news client.

TDD — these tests are written BEFORE the implementation so they start RED.
"""
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# get_company_news — finnhub_client
# ---------------------------------------------------------------------------

class TestGetCompanyNews:
    """Unit tests for the new get_company_news function."""

    def test_returns_empty_list_when_no_api_key(self):
        """No Finnhub key → _get_client() returns None → returns []."""
        from app.data.finnhub_client import get_company_news
        with patch("app.data.finnhub_client._get_client", return_value=None):
            result = get_company_news("AAPL")
        assert result == []

    def test_returns_list_of_dicts_with_required_keys(self):
        """Happy path: Finnhub returns articles → we reshape into required keys."""
        raw_articles = [
            {
                "headline": "Apple hits record",
                "summary": "AAPL soars",
                "datetime": 1700000200,
                "source": "Reuters",
                "url": "https://reuters.com/aapl",
            },
            {
                "headline": "Apple misses estimates",
                "summary": "EPS below consensus",
                "datetime": 1700000100,
                "source": "Bloomberg",
                "url": "https://bloomberg.com/aapl",
            },
        ]
        mock_client = MagicMock()
        mock_client.company_news.return_value = raw_articles

        from app.data.finnhub_client import get_company_news
        with patch("app.data.finnhub_client._get_client", return_value=mock_client):
            result = get_company_news("AAPL")

        assert len(result) == 2
        assert result[0]["headline"] == "Apple hits record"
        assert result[0]["datetime"] == 1700000200
        assert "source" in result[0]
        assert "url" in result[0]

    def test_results_are_sorted_newest_first(self):
        """Articles are returned sorted by datetime descending."""
        raw_articles = [
            {"headline": "Old news", "summary": "", "datetime": 100, "source": "X", "url": ""},
            {"headline": "New news", "summary": "", "datetime": 999, "source": "X", "url": ""},
        ]
        mock_client = MagicMock()
        mock_client.company_news.return_value = raw_articles

        from app.data.finnhub_client import get_company_news
        with patch("app.data.finnhub_client._get_client", return_value=mock_client):
            result = get_company_news("AAPL")

        assert result[0]["datetime"] == 999
        assert result[1]["datetime"] == 100

    def test_limited_to_50_articles(self):
        """Never returns more than 50 articles regardless of Finnhub response."""
        raw_articles = [
            {"headline": f"Article {i}", "summary": "", "datetime": i, "source": "X", "url": ""}
            for i in range(100)
        ]
        mock_client = MagicMock()
        mock_client.company_news.return_value = raw_articles

        from app.data.finnhub_client import get_company_news
        with patch("app.data.finnhub_client._get_client", return_value=mock_client):
            result = get_company_news("AAPL")

        assert len(result) <= 50

    def test_returns_empty_list_on_exception(self):
        """If Finnhub raises any exception, return [] gracefully."""
        mock_client = MagicMock()
        mock_client.company_news.side_effect = Exception("rate limit")

        from app.data.finnhub_client import get_company_news
        with patch("app.data.finnhub_client._get_client", return_value=mock_client):
            result = get_company_news("AAPL")

        assert result == []


# ---------------------------------------------------------------------------
# news_sentiment node
# ---------------------------------------------------------------------------

class TestNewsSentimentNode:
    """Unit tests for the news_sentiment.run() node."""

    @pytest.mark.asyncio
    async def test_returns_partial_when_no_finnhub_key(self):
        """When Finnhub key is absent, node returns partial status.

        Must patch both the settings key (the early guard) and _get_client (the
        fallback) — otherwise a real key in .env bypasses the guard and we land
        on no_news_found instead.
        """
        from app.nodes import news_sentiment
        from app.config import settings as real_settings
        original_key = real_settings.finnhub_api_key
        real_settings.finnhub_api_key = ""
        try:
            state = {"ticker": "AAPL"}
            result = await news_sentiment.run(state)
        finally:
            real_settings.finnhub_api_key = original_key

        assert result["news_sentiment"] is None
        assert result["section_statuses"]["news_sentiment"]["status"] == "partial"
        assert result["section_statuses"]["news_sentiment"]["source"] == "no_finnhub_key"

    @pytest.mark.asyncio
    async def test_returns_partial_when_news_list_empty(self):
        """When Finnhub returns no articles, node returns partial/no_news_found."""
        mock_client = MagicMock()
        mock_client.company_news.return_value = []

        with patch("app.data.finnhub_client._get_client", return_value=mock_client):
            from app.nodes import news_sentiment
            state = {"ticker": "AAPL"}
            result = await news_sentiment.run(state)

        assert result["news_sentiment"] is None
        assert result["section_statuses"]["news_sentiment"]["status"] == "partial"
        assert result["section_statuses"]["news_sentiment"]["source"] == "no_news_found"

    @pytest.mark.asyncio
    async def test_returns_score_when_vader_scores_articles(self):
        """Happy path: articles + VADER → news_sentiment_score is a float in [-1, 1]."""
        raw_articles = [
            {"headline": "Apple crushes earnings, stock soars", "summary": "Great quarter",
             "datetime": 1700000200, "source": "Reuters", "url": ""},
            {"headline": "Apple misses guidance", "summary": "Disappointing results",
             "datetime": 1700000100, "source": "Bloomberg", "url": ""},
        ]
        mock_client = MagicMock()
        mock_client.company_news.return_value = raw_articles

        with patch("app.data.finnhub_client._get_client", return_value=mock_client):
            from app.nodes import news_sentiment
            state = {"ticker": "AAPL"}
            result = await news_sentiment.run(state)

        payload = result["news_sentiment"]
        assert payload is not None
        score = payload["news_sentiment_score"]
        assert isinstance(score, float)
        assert -1.0 <= score <= 1.0
        assert payload["news_lookback_days"] == 30
        assert "top_narratives" in payload
        assert "recent_catalysts" in payload
        assert payload["recent_catalysts"] == []

    @pytest.mark.asyncio
    async def test_status_ok_when_vader_succeeds(self):
        """With articles, status is ok and source indicates which components ran."""
        raw_articles = [
            {"headline": "Apple news", "summary": "", "datetime": 1700000100, "source": "X", "url": ""},
        ]
        mock_client = MagicMock()
        mock_client.company_news.return_value = raw_articles

        with patch("app.data.finnhub_client._get_client", return_value=mock_client):
            from app.nodes import news_sentiment
            state = {"ticker": "AAPL"}
            result = await news_sentiment.run(state)

        assert result["section_statuses"]["news_sentiment"]["status"] == "ok"
        # Source is finnhub+vader when Haiku skipped (no key), finnhub+vader+haiku when Haiku ran
        source = result["section_statuses"]["news_sentiment"]["source"]
        assert source.startswith("finnhub+vader")

    @pytest.mark.asyncio
    async def test_returns_only_delta_keys(self):
        """Parallel node must return ONLY news_sentiment and section_statuses keys."""
        mock_client = MagicMock()
        mock_client.company_news.return_value = []

        with patch("app.data.finnhub_client._get_client", return_value=mock_client):
            from app.nodes import news_sentiment
            state = {"ticker": "AAPL", "segment": "large_cap_blue_chip", "fundamentals": {}}
            result = await news_sentiment.run(state)

        # Only delta keys — never the full state
        assert set(result.keys()) == {"news_sentiment", "section_statuses"}

    @pytest.mark.asyncio
    async def test_progress_callback_is_called(self):
        """Node emits a progress callback when one is present in state."""
        mock_client = MagicMock()
        mock_client.company_news.return_value = []
        callback = AsyncMock()

        with patch("app.data.finnhub_client._get_client", return_value=mock_client):
            from app.nodes import news_sentiment
            state = {"ticker": "AAPL", "progress_callback": callback}
            await news_sentiment.run(state)

        callback.assert_awaited_once()


# ---------------------------------------------------------------------------
# Integration: smoke test — news_sentiment shows up in full pipeline response
# ---------------------------------------------------------------------------

class TestNewsSentimentInPipeline:
    """Verify the full pipeline no longer returns pending_phase2 for news_sentiment."""

    def test_news_sentiment_section_status_is_not_pending_phase2(self):
        """After Phase D, source must NOT be 'pending_phase2'."""
        from fastapi.testclient import TestClient
        from app.main import app as fastapi_app
        tc = TestClient(fastapi_app)
        r = tc.post("/analyze-ticker", json={"ticker": "AAPL"})
        assert r.status_code == 200
        data = r.json()
        source = data["section_statuses"]["news_sentiment"]["source"]
        assert source != "pending_phase2", (
            f"news_sentiment still returning pending_phase2 — Phase D not wired in. Got: {source}"
        )

    def test_news_sentiment_status_is_partial_or_ok_never_pending(self):
        """Status must be 'partial' (no key) or 'ok' (with key) — never the old stub value."""
        from fastapi.testclient import TestClient
        from app.main import app as fastapi_app
        tc = TestClient(fastapi_app)
        r = tc.post("/analyze-ticker", json={"ticker": "AAPL"})
        assert r.status_code == 200
        data = r.json()
        status = data["section_statuses"]["news_sentiment"]["status"]
        assert status in ("ok", "partial")
