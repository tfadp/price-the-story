import logging
from app.state import GraphState

logger = logging.getLogger(__name__)

_PENDING_STATUS = {
    "status": "partial",
    "source": "pending_phase2",
    "cached": False,
    "ttl_remaining_s": None,
}


async def run(state: GraphState) -> dict:
    """Node 5: News & Sentiment — stubbed pending Phase 2 (Finnhub).

    Options sentiment via Yahoo Finance was removed because the endpoint
    is unreliable. Will be reimplemented with Finnhub in Phase 2.
    """
    logger.debug("news_sentiment: stubbed — Phase 2 pending")
    return {
        "news_sentiment": None,
        "section_statuses": {"news_sentiment": _PENDING_STATUS},
    }
