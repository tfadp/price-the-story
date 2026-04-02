"""
Node 5: News & Sentiment — Phase D.

Pipeline:
1. Fetch last 30 days of company news from Finnhub
2. Score each headline+summary with VADER (deterministic, no API key needed)
3. Claude Haiku clusters top headlines into 3–5 narrative themes

This is a PARALLEL node — returns only delta: {"news_sentiment": {...}, "section_statuses": {...}}

Degraded gracefully:
- No Finnhub key: partial, source="no_finnhub_key"
- Empty news: partial, source="no_news_found"
- VADER unavailable: partial, source="vader_unavailable"
- Haiku fails: still returns score, top_narratives=[]
"""
import asyncio
import logging

from app.config import settings
from app.data.finnhub_client import get_company_news
from app.state import GraphState

logger = logging.getLogger(__name__)

_LOOKBACK_DAYS = 30
_MAX_HAIKU_HEADLINES = 20
_HAIKU_TIMEOUT_S = 20.0


def _score_articles(articles: list[dict]) -> float:
    """Run VADER over each article's headline+summary, return mean compound score."""
    try:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    except ImportError as e:
        raise RuntimeError("vaderSentiment not installed: pip install vaderSentiment") from e

    sia = SentimentIntensityAnalyzer()
    scores = []
    for article in articles:
        text = f"{article.get('headline', '')} {article.get('summary', '')}".strip()
        if text:
            scores.append(sia.polarity_scores(text)["compound"])

    if not scores:
        return 0.0
    return round(sum(scores) / len(scores), 3)


async def _cluster_narratives(ticker: str, articles: list[dict]) -> list[dict]:
    """Ask Haiku to group top headlines into 3–5 narrative themes.

    Returns list of {label, sentiment, supporting_examples} or [] on any failure.
    """
    if not settings.anthropic_api_key:
        return []

    headlines = [a["headline"] for a in articles[:_MAX_HAIKU_HEADLINES] if a.get("headline")]
    if not headlines:
        return []

    headlines_text = "\n".join(f"- {h}" for h in headlines)

    try:
        from langchain_anthropic import ChatAnthropic
        from langchain_core.messages import HumanMessage

        llm = ChatAnthropic(
            model="claude-haiku-4-5-20251001",
            api_key=settings.anthropic_api_key,
            max_tokens=600,
        )

        prompt = f"""You are summarizing recent news coverage for an equity investor.

Company ticker: {ticker}
News headlines (newest first):
{headlines_text}

Identify 3–5 recurring narrative clusters in this news. For each cluster:
- label: 2–4 word name for the theme (e.g. "AI investment pace", "margin compression")
- sentiment: "positive" | "neutral" | "negative"
- supporting_examples: the 1–2 most representative headlines

Return only valid JSON — no markdown fences, no preamble:
[
  {{"label": "...", "sentiment": "positive|neutral|negative", "supporting_examples": ["...", "..."]}},
  ...
]"""

        import json
        response = await asyncio.wait_for(
            llm.ainvoke([HumanMessage(content=prompt)]),
            timeout=_HAIKU_TIMEOUT_S,
        )
        content = response.content.strip()
        # Strip markdown fences if present
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        narratives = json.loads(content)
        if isinstance(narratives, list):
            return narratives
        return []

    except asyncio.TimeoutError:
        logger.warning("news_sentiment: Haiku narrative clustering timed out for %s", ticker)
        return []
    except Exception as e:
        logger.warning("news_sentiment: Haiku narrative clustering failed for %s: %s", ticker, e)
        return []


async def run(state: GraphState) -> dict:
    """Node 5: News & Sentiment. Returns delta dict — parallel node."""
    ticker: str = state["ticker"]

    callback = state.get("progress_callback")
    if callback is not None:
        await callback("Reading news", "news_sentiment", 25)

    # Guard: no Finnhub key
    if not settings.finnhub_api_key:
        return {
            "news_sentiment": None,
            "section_statuses": {
                "news_sentiment": {
                    "status": "partial",
                    "source": "no_finnhub_key",
                    "cached": False,
                    "ttl_remaining_s": None,
                }
            },
        }

    # Fetch news (blocking IO — run in thread)
    try:
        articles = await asyncio.to_thread(get_company_news, ticker, _LOOKBACK_DAYS)
    except Exception as e:
        logger.warning("news_sentiment: news fetch failed for %s: %s", ticker, e)
        articles = []

    if not articles:
        return {
            "news_sentiment": None,
            "section_statuses": {
                "news_sentiment": {
                    "status": "partial",
                    "source": "no_news_found",
                    "cached": False,
                    "ttl_remaining_s": None,
                }
            },
        }

    # VADER scoring
    try:
        sentiment_score = _score_articles(articles)
    except RuntimeError as e:
        logger.warning("news_sentiment: VADER unavailable for %s: %s", ticker, e)
        return {
            "news_sentiment": None,
            "section_statuses": {
                "news_sentiment": {
                    "status": "partial",
                    "source": "vader_unavailable",
                    "cached": False,
                    "ttl_remaining_s": None,
                }
            },
        }

    # Haiku narrative clustering (best-effort)
    top_narratives = await _cluster_narratives(ticker, articles)

    source = "finnhub+vader+haiku" if top_narratives else "finnhub+vader"

    return {
        "news_sentiment": {
            "news_sentiment_score": sentiment_score,
            "news_lookback_days": _LOOKBACK_DAYS,
            "top_narratives": top_narratives,
            "recent_catalysts": [],
        },
        "section_statuses": {
            "news_sentiment": {
                "status": "ok",
                "source": source,
                "cached": False,
                "ttl_remaining_s": None,
            }
        },
    }
