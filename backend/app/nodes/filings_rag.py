import logging
from app.state import GraphState

logger = logging.getLogger(__name__)


async def run(state: GraphState) -> dict:
    """Node 6: Filings RAG — stub, implemented in Phase 2."""
    logger.info("filings_rag: stub node, skipping")
    # Return only the keys this node writes — avoids LangGraph InvalidUpdateError
    # when parallel nodes each try to update the same state keys.
    return {
        "filings_rag": None,
        "section_statuses": {
            "filings_rag": {
                "status": "failed", "source": None, "cached": False, "ttl_remaining_s": None,
            }
        },
    }
