import logging
from app.state import GraphState

logger = logging.getLogger(__name__)


async def run(state: GraphState) -> dict:
    """Node 7: Themes — stub, implemented in Phase 2.

    Returns only this node's delta so LangGraph parallel fan-out does not
    raise InvalidUpdateError when multiple nodes write to shared state keys.
    """
    logger.info("themes: stub node, skipping")
    return {"themes": None}
