"""
Finnhub data client.

Used in Phase B for earnings call transcripts.
Free tier: 60 req/min. No daily cap.

All calls are synchronous (finnhub-python is sync) — callers use asyncio.to_thread.
"""
import logging
from datetime import date, timedelta
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

# Module-level client — instantiated once, reused across requests
_client: Optional[object] = None


def _get_finnhub_module():
    try:
        import finnhub
    except ImportError as e:
        raise RuntimeError("finnhub-python not installed") from e
    return finnhub


def _get_client() -> Optional[object]:
    global _client
    if _client is None and settings.finnhub_api_key:
        finnhub = _get_finnhub_module()
        _client = finnhub.Client(api_key=settings.finnhub_api_key)
    return _client


def get_earnings_transcripts(ticker: str, limit: int = 4) -> list[dict]:
    """Return the last `limit` earnings call transcripts for a ticker.

    Each transcript is a dict with keys: symbol, year, quarter, transcript (list of speaker turns).
    Returns an empty list when Finnhub is unavailable or the ticker has no transcripts.
    """
    try:
        client = _get_client()
    except RuntimeError as e:
        logger.info("finnhub: %s, skipping transcripts for %s", e, ticker)
        return []
    if not client:
        logger.info("finnhub: no API key configured, skipping transcripts for %s", ticker)
        return []

    try:
        # List available transcript IDs
        result = client.earnings_call_transcripts_list(ticker)
        transcripts_meta = (result or {}).get("transcripts") or []
        if not transcripts_meta:
            logger.info("finnhub: no transcripts found for %s", ticker)
            return []

        # Fetch most recent `limit` transcripts
        out = []
        for meta in transcripts_meta[:limit]:
            t_id = meta.get("id")
            if not t_id:
                continue
            try:
                transcript = client.earnings_call_transcripts(t_id)
                if transcript:
                    out.append({
                        "symbol": transcript.get("symbol", ticker),
                        "year": transcript.get("year"),
                        "quarter": transcript.get("quarter"),
                        # Each item: {name, speech}
                        "transcript": transcript.get("transcript") or [],
                    })
            except Exception as e:
                logger.warning("finnhub: failed to fetch transcript %s: %s", t_id, e)

        logger.info("finnhub: fetched %d transcripts for %s", len(out), ticker)
        return out

    except Exception as e:
        logger.warning("finnhub: get_earnings_transcripts failed for %s: %s", ticker, e)
        return []


def get_company_news(ticker: str, lookback_days: int = 30) -> list[dict]:
    """Return recent company news articles from Finnhub.

    Each item is a dict with keys: headline, summary, datetime (unix int), source, url.
    Returns [] when Finnhub is unavailable, the API key is absent, or the ticker has no news.
    Sorted newest-first, capped at 50 articles.
    """
    try:
        client = _get_client()
    except RuntimeError as e:
        logger.info("finnhub: %s, skipping news for %s", e, ticker)
        return []
    if not client:
        logger.info("finnhub: no API key configured, skipping news for %s", ticker)
        return []

    try:
        from_date = (date.today() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
        to_date = date.today().strftime("%Y-%m-%d")
        raw = client.company_news(ticker, _from=from_date, to=to_date) or []

        articles = []
        for item in raw:
            articles.append({
                "headline": item.get("headline", ""),
                "summary": item.get("summary", ""),
                "datetime": item.get("datetime", 0),
                "source": item.get("source", ""),
                "url": item.get("url", ""),
            })

        # Newest first, cap at 50
        articles.sort(key=lambda a: a["datetime"], reverse=True)
        logger.info("finnhub: fetched %d news articles for %s", len(articles[:50]), ticker)
        return articles[:50]

    except Exception as e:
        logger.warning("finnhub: get_company_news failed for %s: %s", ticker, e)
        return []
