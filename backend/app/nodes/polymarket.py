import logging
from app.state import GraphState

logger = logging.getLogger(__name__)


async def run(state: GraphState) -> dict:
    """Node 9: Polymarket — stub, implemented in Phase 2."""
    logger.info("polymarket: stub node, skipping")
    # Return only the keys this node writes — avoids LangGraph InvalidUpdateError
    # when parallel nodes each try to update the same state keys.
    return {
        "polymarket": None,
        "section_statuses": {
            "polymarket": {
                "status": "failed", "source": None, "cached": False, "ttl_remaining_s": None,
            }
        },
    }
