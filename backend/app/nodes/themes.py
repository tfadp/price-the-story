import logging
from app.state import GraphState

logger = logging.getLogger(__name__)


async def run(state: GraphState) -> GraphState:
    """Node 7: Themes — stub, implemented in Phase 2."""
    logger.info("themes: stub node, skipping")
    state.setdefault("section_statuses", {})["themes"] = {
        "status": "failed", "source": None, "cached": False, "ttl_remaining_s": None
    }
    state["themes"] = None
    return state
