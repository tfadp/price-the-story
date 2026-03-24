import logging
from app.state import GraphState

logger = logging.getLogger(__name__)


async def run(state: GraphState) -> GraphState:
    """Node 6: Filings RAG — stub, implemented in Phase 2."""
    logger.info("filings_rag: stub node, skipping")
    state.setdefault("section_statuses", {})["filings_rag"] = {
        "status": "failed", "source": None, "cached": False, "ttl_remaining_s": None
    }
    state["filings_rag"] = None
    return state
