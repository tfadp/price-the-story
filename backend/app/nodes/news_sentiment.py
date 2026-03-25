import logging
from app.state import GraphState

logger = logging.getLogger(__name__)


async def run(state: GraphState) -> dict:
    """Node 5: News & Sentiment — stub, implemented in Phase 2."""
    logger.info("news_sentiment: stub node, skipping")
    # Return only the keys this node writes — avoids LangGraph InvalidUpdateError
    # when parallel nodes each try to update the same state keys.
    return {
        "news_sentiment": None,
        "section_statuses": {
            "news_sentiment": {
                "status": "failed", "source": None, "cached": False, "ttl_remaining_s": None,
            }
        },
    }
