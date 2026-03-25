"""
Node 8: Macro Regime.

Uses yfinance ETF proxies (TLT, UUP, GLD, ^VIX) to infer the current
macro environment with rule-based logic. No LLM calls.

Never crashes the pipeline — all exceptions caught and logged.
"""
import logging
from typing import Optional

from app.state import GraphState
from app.data.yfinance_client import get_price_history

logger = logging.getLogger(__name__)


def _six_month_return(history: list[dict]) -> Optional[float]:
    """Compute 6-month return from a list of OHLCV dicts (oldest first)."""
    closes = [row["close"] for row in history if row.get("close")]
    if len(closes) < 2:
        return None
    # Approximately 126 trading days = 6 months
    lookback = min(126, len(closes) - 1)
    start_price = closes[-(lookback + 1)]
    end_price = closes[-1]
    if start_price <= 0:
        return None
    return (end_price / start_price) - 1


async def _fetch_return(symbol: str) -> Optional[float]:
    """Fetch 6-month return for a symbol. Returns None on any failure."""
    try:
        data = await get_price_history(symbol, period="1y")
        history = data.get("history", [])
        return _six_month_return(history)
    except Exception as e:
        logger.warning("macro: failed to fetch %s: %s", symbol, e)
        return None


async def _fetch_current_close(symbol: str) -> Optional[float]:
    """Fetch the most recent closing price for a symbol."""
    try:
        data = await get_price_history(symbol, period="5d")
        history = data.get("history", [])
        if history:
            return history[-1].get("close")
    except Exception as e:
        logger.warning("macro: failed to fetch current close for %s: %s", symbol, e)
    return None


async def run(state: GraphState) -> dict:
    """Node 8: Macro. Rule-based regime detection using ETF proxies.

    Returns only the keys this node writes so LangGraph parallel fan-out
    does not raise InvalidUpdateError when multiple nodes run concurrently.
    """

    try:
        import asyncio

        tlt_return, uup_return, gld_return, vix_close = await asyncio.gather(
            _fetch_return("TLT"),
            _fetch_return("UUP"),
            _fetch_return("GLD"),
            _fetch_current_close("^VIX"),
        )

        # ------------------------------------------------------------------
        # Rule-based regime classification
        # ------------------------------------------------------------------
        macro_regime: str
        macro_regime_confidence: str

        if vix_close is not None and vix_close > 30:
            macro_regime = "recession"
            macro_regime_confidence = "high"
        elif (
            tlt_return is not None and tlt_return < -0.05
            and vix_close is not None and vix_close > 20
        ):
            macro_regime = "higher_for_longer_rates"
            macro_regime_confidence = "high"
        elif gld_return is not None and gld_return > 0.08:
            macro_regime = "sticky_inflation"
            macro_regime_confidence = "medium"
        elif (
            tlt_return is not None and tlt_return > 0.05
            and vix_close is not None and vix_close < 20
        ):
            macro_regime = "goldilocks"
            macro_regime_confidence = "high"
        else:
            macro_regime = "disinflation"
            macro_regime_confidence = "medium"

        # ------------------------------------------------------------------
        # Generic scenario impacts based on regime
        # ------------------------------------------------------------------
        scenario_impacts = _build_scenario_impacts(macro_regime)

        return {
            "macro": {
                "macro_regime": macro_regime,
                "macro_regime_confidence": macro_regime_confidence,
                "scenario_impacts": scenario_impacts,
                "polymarket_signals": [],
            },
        }

    except Exception as e:
        logger.warning("macro: node failed: %s", e)
        return {
            "macro": {
                "macro_regime": "unknown",
                "macro_regime_confidence": "low",
                "scenario_impacts": [],
                "polymarket_signals": [],
            },
        }


def _build_scenario_impacts(regime: str) -> list[dict]:
    """Return 2-3 generic scenario impacts for the detected macro regime."""
    scenarios: dict[str, list[dict]] = {
        "recession": [
            {
                "scenario": "Revenue contraction",
                "impact_on_business": "Top-line pressure as consumer and enterprise spending declines.",
                "impact_direction": "negative",
            },
            {
                "scenario": "Multiple compression",
                "impact_on_business": "Risk-off sentiment compresses P/E multiples.",
                "impact_direction": "negative",
            },
        ],
        "higher_for_longer_rates": [
            {
                "scenario": "Discount rate headwind",
                "impact_on_business": "Higher rates increase cost of capital, reducing DCF fair values.",
                "impact_direction": "negative",
            },
            {
                "scenario": "Consumer credit tightening",
                "impact_on_business": "Reduced consumer discretionary spending may weigh on revenues.",
                "impact_direction": "negative",
            },
            {
                "scenario": "Sector rotation",
                "impact_on_business": "Capital may rotate to value/dividend names, pressuring growth multiples.",
                "impact_direction": "negative",
            },
        ],
        "sticky_inflation": [
            {
                "scenario": "Input cost pressure",
                "impact_on_business": "Persistent inflation may compress operating margins.",
                "impact_direction": "negative",
            },
            {
                "scenario": "Pricing power test",
                "impact_on_business": "Companies with strong brands may pass costs through; others cannot.",
                "impact_direction": "neutral",
            },
        ],
        "goldilocks": [
            {
                "scenario": "Valuation expansion",
                "impact_on_business": "Low rates and stable growth support multiple expansion.",
                "impact_direction": "positive",
            },
            {
                "scenario": "Consumer resilience",
                "impact_on_business": "Healthy employment and spending support revenue growth.",
                "impact_direction": "positive",
            },
        ],
        "disinflation": [
            {
                "scenario": "Rate normalisation tailwind",
                "impact_on_business": "Falling inflation may lead to easing, supporting growth multiples.",
                "impact_direction": "positive",
            },
            {
                "scenario": "Margin recovery",
                "impact_on_business": "Lower input costs may expand margins if pricing holds.",
                "impact_direction": "positive",
            },
        ],
        "unknown": [],
    }
    return scenarios.get(regime, [])
