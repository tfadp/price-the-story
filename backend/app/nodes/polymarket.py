import logging
from app.state import GraphState

logger = logging.getLogger(__name__)


async def run(state: GraphState) -> GraphState:
    """Node 9: Polymarket — stub, implemented in Phase 2."""
    logger.info("polymarket: stub node, skipping")
    state.setdefault("section_statuses", {})["polymarket"] = {
        "status": "failed", "source": None, "cached": False, "ttl_remaining_s": None
    }
    state["polymarket"] = None
    return state
