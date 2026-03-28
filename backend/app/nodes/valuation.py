"""
Node 3: Valuation.

Deterministic DCF + P/E multiple approach. NO LLM calls.
All numbers come from prior state; current price is fetched fresh.

Never crashes the pipeline — exceptions are caught, logged, and
state["valuation"] is set to None.
"""
import logging
import math
from typing import Optional

from app.state import GraphState
from app.utils import safe_float
from app.data.yfinance_client import get_current_price
from app.data.financial_datasets_client import get_snapshot_price

logger = logging.getLogger(__name__)

# Constants for base-case DCF
_WACC_BASE = 0.095        # risk-free 4.5% + equity premium 4.5% + 0.5% spread
_TERMINAL_GROWTH = 0.03
_TERMINAL_PE_BASE = 15.0


def _dcf(
    eps_base: float,
    growth: float,
    wacc: float,
    terminal_pe: float,
    years: int = 5,
) -> float:
    """Simple EPS-based DCF.

    Projects EPS forward 'years' periods, discounts back, adds terminal value.
    Terminal value = projected EPS[year N] * terminal_pe, also discounted.
    """
    eps_values = [eps_base * (1 + growth) ** i for i in range(1, years + 1)]
    pv = sum(e / (1 + wacc) ** i for i, e in enumerate(eps_values, 1))
    terminal = eps_values[-1] * terminal_pe / (1 + wacc) ** years
    return pv + terminal


def _solve_implied_growth(
    eps: float,
    target_price: float,
    wacc: float,
    terminal_pe: float,
    years: int = 5,
) -> Optional[float]:
    """Binary-search for the growth rate where DCF price equals target_price."""
    if eps <= 0:
        return None
    lo, hi = -0.50, 2.00
    for _ in range(60):  # enough iterations for ~0.0001% accuracy
        mid = (lo + hi) / 2
        try:
            val = _dcf(eps, mid, wacc, terminal_pe, years)
        except (OverflowError, ZeroDivisionError):
            return None
        if val < target_price:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


async def run(state: GraphState) -> dict:
    """Node 3: Valuation. Returns delta dict on success or failure.

    Returns only the keys this node writes so LangGraph parallel fan-out
    does not raise InvalidUpdateError when multiple nodes run concurrently.
    """
    ticker: str = state["ticker"]

    try:
        # Always use a fresh price — Financial Datasets snapshot first, yfinance fallback
        try:
            current_price = await get_snapshot_price(ticker)
        except Exception:
            try:
                current_price = await get_current_price(ticker)
            except ValueError as e:
                logger.warning("valuation: could not fetch current price for %s: %s", ticker, e)
                ticker_meta = state.get("ticker_meta") or {}
                current_price = safe_float(
                    ticker_meta.get("regularMarketPrice") or ticker_meta.get("previousClose")
                )
                if current_price is None:
                    raise ValueError("Current price unavailable") from e

        fund = state.get("fundamentals") or {}
        analyst_estimates = state.get("analyst_estimates") or {}

        time_series = fund.get("time_series", {}) if fund else {}
        eps_values: list = time_series.get("eps", []) or []
        revenue_values: list = time_series.get("revenue", []) or []

        # Current (most recent annual) EPS
        valid_eps = [safe_float(e) for e in eps_values if safe_float(e) is not None]
        current_eps: Optional[float] = valid_eps[-1] if valid_eps else None

        # ------------------------------------------------------------------
        # Determine baseline EPS growth rate
        # ------------------------------------------------------------------
        # Prefer analyst consensus; fall back to historical CAGR
        base_growth: float = 0.08  # default fallback
        base_growth_source = "default"
        valuation_notes: list[str] = []
        valuation_confidence = "medium"

        consensus_path: list = analyst_estimates.get("consensus_growth_path", []) or []
        if consensus_path:
            # Use average of available EPS estimates
            growth_estimates = []
            for cp in consensus_path:
                eps_est = safe_float(cp.get("eps_estimate"))
                if eps_est is not None and current_eps and current_eps > 0:
                    years_out = cp.get("year", 1)
                    if isinstance(years_out, int) and years_out > 0:
                        g = (eps_est / current_eps) ** (1 / years_out) - 1
                        growth_estimates.append(g)
            if growth_estimates:
                base_growth = sum(growth_estimates) / len(growth_estimates)
                base_growth_source = "analyst_consensus"
        else:
            # Historical EPS CAGR
            if len(valid_eps) >= 2 and valid_eps[0] > 0:
                n = len(valid_eps) - 1
                try:
                    hist_cagr = (valid_eps[-1] / valid_eps[0]) ** (1 / n) - 1
                    if not math.isnan(hist_cagr) and not math.isinf(hist_cagr):
                        base_growth = min(max(hist_cagr, -0.30), 0.50)
                        base_growth_source = "historical_eps"
                except (ValueError, ZeroDivisionError):
                    pass

        if base_growth_source == "default":
            valuation_confidence = "low"
            valuation_notes.append(
                "Base growth fell back to the default 8% assumption because analyst and historical EPS inputs were insufficient."
            )

        # ------------------------------------------------------------------
        # Handle negative/zero EPS: P/S multiple fallback
        # ------------------------------------------------------------------
        use_ps_fallback = current_eps is None or current_eps <= 0

        if use_ps_fallback:
            ticker_meta = state.get("ticker_meta") or {}
            ps_ratio = safe_float(ticker_meta.get("priceToSalesTrailing12Months"))
            shares_outstanding = safe_float(ticker_meta.get("sharesOutstanding"))
            valuation_notes.append(
                "Valuation used a sales-based fallback because positive EPS inputs were unavailable."
            )

            if ps_ratio and ps_ratio > 0 and revenue_values:
                valid_revs = [safe_float(r) for r in revenue_values if safe_float(r) is not None and r > 0]
                if valid_revs:
                    # Project revenue 5yr at base_growth, apply median P/S
                    median_ps = ps_ratio
                    fv_base_rev = valid_revs[-1] * (1 + base_growth) ** 5 * median_ps
                    fv_low_rev = valid_revs[-1] * (1 + base_growth * 0.80) ** 5 * median_ps * 0.80
                    fv_high_rev = valid_revs[-1] * (1 + base_growth * 1.20) ** 5 * median_ps * 1.20
                    if shares_outstanding and shares_outstanding > 0:
                        fair_value_base = fv_base_rev / shares_outstanding
                        fair_value_low = fv_low_rev / shares_outstanding
                        fair_value_high = fv_high_rev / shares_outstanding
                    else:
                        fair_value_base = current_price
                        fair_value_low = current_price * 0.80
                        fair_value_high = current_price * 1.20
                        valuation_confidence = "low"
                        valuation_notes.append(
                            "Shares outstanding were unavailable, so fair value was anchored around the current price."
                        )
                else:
                    fair_value_base = current_price
                    fair_value_low = current_price * 0.80
                    fair_value_high = current_price * 1.20
                    valuation_confidence = "low"
                    valuation_notes.append(
                        "Revenue history was unavailable, so fair value was anchored around the current price."
                    )
            else:
                # No useful data at all: centre on current price
                fair_value_base = current_price
                fair_value_low = current_price * 0.80
                fair_value_high = current_price * 1.20
                valuation_confidence = "low"
                valuation_notes.append(
                    "P/S inputs were unavailable, so fair value was anchored around the current price rather than estimated independently."
                )
        else:
            # Full DCF
            fair_value_base = _dcf(current_eps, base_growth, _WACC_BASE, _TERMINAL_PE_BASE)
            fair_value_low = _dcf(
                current_eps,
                base_growth * 0.80,
                _WACC_BASE + 0.01,
                _TERMINAL_PE_BASE * 0.90,
            )
            fair_value_high = _dcf(
                current_eps,
                base_growth * 1.20,
                _WACC_BASE - 0.01,
                _TERMINAL_PE_BASE * 1.10,
            )
            if base_growth_source == "analyst_consensus" and len(valid_eps) >= 3:
                valuation_confidence = "medium"
            elif base_growth_source == "historical_eps":
                valuation_confidence = "medium"

        # ------------------------------------------------------------------
        # Entry band
        # ------------------------------------------------------------------
        accumulate_below = fair_value_base * 0.90
        strong_buy_below = fair_value_low * 0.95

        # ------------------------------------------------------------------
        # Price efficiency assessment
        # ------------------------------------------------------------------
        if valuation_confidence == "low":
            efficiency_verdict = "insufficient_data"
            efficiency_notes = (
                "Price efficiency is not being judged confidently because fair value relied on fallback assumptions rather than a fully independent estimate."
            )
        elif current_price > fair_value_high:
            efficiency_verdict = "appears_inflated"
            efficiency_notes = (
                f"At ${current_price:.2f}, the stock trades above our bull-case fair value "
                f"of ${fair_value_high:.2f}, suggesting the market is pricing in more optimism "
                f"than our base case supports."
            )
        elif current_price < fair_value_low:
            efficiency_verdict = "appears_conservative"
            efficiency_notes = (
                f"At ${current_price:.2f}, the stock trades below our bear-case fair value "
                f"of ${fair_value_low:.2f}, suggesting potential under-appreciation by the market."
            )
        else:
            efficiency_verdict = "fairly_priced"
            efficiency_notes = (
                f"At ${current_price:.2f}, the stock is within our fair value range of "
                f"${fair_value_low:.2f}–${fair_value_high:.2f}."
            )

        # Implied growth rate (back-solved)
        implied_growth: Optional[float] = None
        sentiment_premium_flag = False
        sentiment_premium_notes: Optional[str] = None

        if not use_ps_fallback and current_eps and current_eps > 0:
            implied_growth = _solve_implied_growth(
                current_eps, current_price, _WACC_BASE, _TERMINAL_PE_BASE
            )

            # Sentiment premium: check if 12mo price return > 2x EPS growth
            # Use price history already fetched by classifier — avoids a redundant network call
            try:
                history = state.get("price_history") or []
                closes = [row["close"] for row in history if row.get("close")]
                if len(closes) >= 2:
                    price_return_1yr = (closes[-1] / closes[0]) - 1
                    if price_return_1yr > base_growth * 2:
                        sentiment_premium_flag = True
                        sentiment_premium_notes = (
                            f"12-month price return ({price_return_1yr*100:.1f}%) is more than "
                            f"2x the estimated EPS growth rate ({base_growth*100:.1f}%), "
                            f"suggesting possible sentiment premium."
                        )
            except Exception as e:
                logger.warning("valuation: sentiment premium check failed: %s", e)

        # Valuation method summary (template, NOT LLM)
        valuation_method_summary = (
            f"Heuristic DCF + P/E framework. Base case uses {base_growth*100:.1f}% growth, "
            f"{_WACC_BASE*100:.1f}% discount rate, {_TERMINAL_PE_BASE:.0f}x terminal P/E. "
            f"Bear case: -20% growth, +1pp rate. Bull case: +20% growth, -1pp rate."
        )

        # Save _base_growth so probability_engine can read it
        return {
            "valuation": {
                "current_price": current_price,
                "currency": "USD",
                "fair_value_low": round(fair_value_low, 2),
                "fair_value_base": round(fair_value_base, 2),
                "fair_value_high": round(fair_value_high, 2),
                "valuation_method_summary": valuation_method_summary,
                "suggested_entry_band": {
                    "accumulate_below": round(accumulate_below, 2),
                    "strong_buy_below": round(strong_buy_below, 2),
                    "notes": None,
                },
                "price_efficiency_assessment": {
                    "implied_revenue_cagr_5yr": implied_growth,
                    "implied_vs_management_guidance": None,
                    "implied_vs_stress_base": None,
                    "implied_vs_stress_bear": None,
                    "efficiency_verdict": efficiency_verdict,
                    "efficiency_notes": efficiency_notes,
                    "sentiment_premium_flag": sentiment_premium_flag,
                    "sentiment_premium_notes": sentiment_premium_notes,
                    "historical_analog": None,
                },
                "valuation_confidence": valuation_confidence,
                "valuation_notes": " ".join(valuation_notes) if valuation_notes else None,
                # Internal: read by probability_engine
                "_base_growth": base_growth,
                "_base_growth_source": base_growth_source,
            },
        }

    except Exception as e:
        logger.warning("valuation: node failed for %s: %s", ticker, e)
        return {"valuation": None}
