import logging
from app.state import GraphState

logger = logging.getLogger(__name__)


async def run(state: GraphState) -> dict:
    """Node 6: Filings RAG — stub, implemented in Phase 2.

    Returns only this node's delta so LangGraph parallel fan-out does not
    raise InvalidUpdateError when multiple nodes write to shared state keys.
    """
    logger.info("filings_rag: stub node, skipping")
    return {"filings_rag": None}
