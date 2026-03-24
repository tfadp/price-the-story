"""
LangGraph DAG — all 11 nodes wired.
Execution: classifier → [parallel fan-out: 8 nodes] → probability_engine → pm_synthesis

Node names are prefixed with "node_" to avoid clashing with GraphState field names,
which LangGraph 0.2.x prohibits using as node identifiers.
"""
from __future__ import annotations

import logging

from langgraph.graph import StateGraph, START, END

from app.state import GraphState
from app.nodes import (
    classifier,
    fundamentals,
    valuation,
    analyst_estimates,
    news_sentiment,
    filings_rag,
    themes,
    macro,
    polymarket,
    probability_engine,
    pm_synthesis,
)

logger = logging.getLogger(__name__)

# Internal node names (prefixed to avoid GraphState key conflicts)
PARALLEL_NODES = [
    "node_fundamentals",
    "node_valuation",
    "node_analyst_estimates",
    "node_news_sentiment",
    "node_filings_rag",
    "node_themes",
    "node_macro",
    "node_polymarket",
]


def build_graph() -> StateGraph:
    builder = StateGraph(GraphState)

    builder.add_node("node_classifier", classifier.run)
    builder.add_node("node_fundamentals", fundamentals.run)
    builder.add_node("node_valuation", valuation.run)
    builder.add_node("node_analyst_estimates", analyst_estimates.run)
    builder.add_node("node_news_sentiment", news_sentiment.run)
    builder.add_node("node_filings_rag", filings_rag.run)
    builder.add_node("node_themes", themes.run)
    builder.add_node("node_macro", macro.run)
    builder.add_node("node_polymarket", polymarket.run)
    builder.add_node("node_probability_engine", probability_engine.run)
    builder.add_node("node_pm_synthesis", pm_synthesis.run)

    builder.add_edge(START, "node_classifier")
    for node_name in PARALLEL_NODES:
        builder.add_edge("node_classifier", node_name)
        builder.add_edge(node_name, "node_probability_engine")
    builder.add_edge("node_probability_engine", "node_pm_synthesis")
    builder.add_edge("node_pm_synthesis", END)

    return builder.compile()


graph = build_graph()
