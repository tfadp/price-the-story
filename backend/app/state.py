"""
LangGraph graph state.
This TypedDict flows through all 11 nodes. Each node reads what it needs
and writes its outputs back. All fields are Optional — nodes return partial
results on failure rather than crashing the pipeline.
"""
from __future__ import annotations

from typing import Annotated, Callable, Optional
from typing_extensions import TypedDict


def _merge_section_statuses(a: dict, b: dict) -> dict:
    """Reducer for section_statuses — merges dicts from parallel nodes.

    Without this reducer, LangGraph would raise InvalidUpdateError when
    multiple parallel nodes each write their own key into section_statuses.
    The reducer tells LangGraph to merge the dicts rather than conflict.
    """
    return {**a, **b}


class GraphState(TypedDict, total=False):
    # ---- Input (set before graph starts) --------------------------------
    ticker: str
    target_cagr: float
    entry_price: Optional[float]
    horizons: list[int]
    force_refresh: bool
    debug: bool

    # ---- Node 1: Classifier ---------------------------------------------
    segment: Optional[str]             # large_cap_blue_chip | mid_cap | small_cap_high_vol | other
    segment_confidence: Optional[str]  # high | medium | low
    data_quality: Optional[str]        # high | medium | low
    is_us_equity: bool
    ticker_meta: Optional[dict]        # raw yfinance .info snapshot

    # ---- Node 2: Fundamentals -------------------------------------------
    fundamentals: Optional[dict]

    # ---- Node 3: Valuation ----------------------------------------------
    valuation: Optional[dict]

    # ---- Node 4: Analyst Estimates --------------------------------------
    analyst_estimates: Optional[dict]

    # ---- Node 5: News & Sentiment (stub Phase 1) ------------------------
    news_sentiment: Optional[dict]

    # ---- Node 6: Filings RAG (stub Phase 1) -----------------------------
    filings_rag: Optional[dict]

    # ---- Node 7: Themes (stub Phase 1) ----------------------------------
    themes: Optional[dict]

    # ---- Node 8: Macro --------------------------------------------------
    macro: Optional[dict]

    # ---- Node 9: Polymarket (stub Phase 1) ------------------------------
    polymarket: Optional[dict]

    # ---- Node 10: Probability Engine ------------------------------------
    probability_engine: Optional[dict]
    stress_test: Optional[dict]

    # ---- Node 11: PM Synthesis ------------------------------------------
    pm_synthesis: Optional[dict]
    verdict_paragraph: Optional[str]
    confidence_verdict: Optional[str]
    red_flags: list[dict]

    # ---- Metadata -------------------------------------------------------
    # Annotated with _merge_section_statuses so parallel nodes can each write
    # their own key without LangGraph raising InvalidUpdateError.
    section_statuses: Annotated[dict[str, dict], _merge_section_statuses]
    errors: list[str]
    # Async callable: (stage: str, node: str, pct: int) -> None
    # Used by nodes to emit SSE progress events.
    progress_callback: Optional[Callable]
