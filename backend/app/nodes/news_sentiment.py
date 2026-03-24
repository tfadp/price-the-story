import logging
from app.state import GraphState

logger = logging.getLogger(__name__)


async def run(state: GraphState) -> GraphState:
    """Node 5: News & Sentiment — stub, implemented in Phase 2."""
    logger.info("news_sentiment: stub node, skipping")
    state.setdefault("section_statuses", {})["news_sentiment"] = {
        "status": "failed", "source": None, "cached": False, "ttl_remaining_s": None
    }
    state["news_sentiment"] = None
    return state
