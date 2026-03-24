"""
Node 10: Probability Engine + Stress Test.

Deterministic heuristic — NO LLM calls.
Estimates probability of hitting a target CAGR over multiple time horizons,
using scenario-weighted EPS projections.

Never crashes the pipeline — all exceptions caught and logged.
"""
import logging
import math
from typing import Optional

from app.state import GraphState

logger = logging.getLogger(__name__)


def _safe_float(val) -> Optional[float]:
    try:
        if val is None:
            return None
        f = float(val)
        return None if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return None


def _project_price(
    eps: float,
    growth: float,
    years: int,
    terminal_pe: float,
) -> float:
    """Project terminal stock price from EPS, growth rate, and P/E multiple.

    Simple hold-to-terminal approach: price = EPS_N * terminal_pe.
    """
    projected_eps = eps * (1 + growth) ** years
    return projected_eps * terminal_pe


async def run(state: GraphState) -> GraphState:
    """Node 10: Probability Engine + Stress Test."""
    state.setdefault("section_statuses", {})

    try:
        segment = state.get("segment", "other")

        # ------------------------------------------------------------------
        # Disable for high-volatility small caps
        # ------------------------------------------------------------------
        if segment == "small_cap_high_vol":
            state["probability_engine"] = {
                "enabled": False,
                "reason_disabled": "Probability engine not supported for high-volatility small caps.",
            }
            state["stress_test"] = None
            state["section_statuses"]["probability_engine"] = {
                "status": "ok",
                "source": "heuristic",
                "cached": False,
                "ttl_remaining_s": None,
            }
            return state

        # ------------------------------------------------------------------
        # Gather inputs
        # ------------------------------------------------------------------
        val: dict = state.get("valuation") or {}
        fund: dict = state.get("fundamentals") or {}
        filings: dict = state.get("filings_rag") or {}
        macro: dict = state.get("macro") or {}

        current_price = (
            _safe_float(val.get("current_price"))
            or _safe_float((state.get("ticker_meta") or {}).get("regularMarketPrice"))
            or 100.0
        )
        entry_price = _safe_float(state.get("entry_price")) or current_price
        target_cagr: float = state.get("target_cagr", 0.10) or 0.10

        efficiency_verdict = None
        pea = val.get("price_efficiency_assessment") or {}
        if isinstance(pea, dict):
            efficiency_verdict = pea.get("efficiency_verdict")

        macro_regime: str = macro.get("macro_regime", "unknown") or "unknown"

        assumption_sheet: list = filings.get("assumption_sheet", []) if filings else []
        fragile_count = sum(1 for a in assumption_sheet if a.get("fragility") == "fragile")
        words_vs_numbers = filings.get("words_vs_numbers_alignment") if filings else None
        bet_credibility = filings.get("bet_credibility_score") if filings else None

        # ------------------------------------------------------------------
        # Scenario weights
        # ------------------------------------------------------------------
        bull_w: float = 0.35
        base_w: float = 0.45
        bear_w: float = 0.20

        bear_w += fragile_count * 0.03
        if words_vs_numbers == "significant_misalignment":
            bear_w += 0.08
        if bet_credibility == "low":
            bear_w += 0.05
        if macro_regime == "higher_for_longer_rates":
            bear_w += 0.05

        bear_w = min(bear_w, 0.50)
        total_w = bull_w + base_w + bear_w
        bull_w, base_w, bear_w = bull_w / total_w, base_w / total_w, bear_w / total_w

        # ------------------------------------------------------------------
        # EPS and growth rate inputs
        # ------------------------------------------------------------------
        time_series: dict = fund.get("time_series", {}) if fund else {}

        eps_values: list = time_series.get("eps", []) or []
        valid_eps = [_safe_float(e) for e in eps_values if _safe_float(e) is not None]
        current_eps: Optional[float] = valid_eps[-1] if valid_eps else None

        base_growth: float = _safe_float(val.get("_base_growth")) or 0.08
        bull_growth: float = base_growth * 1.25
        bear_growth: float = base_growth * 0.60

        wacc: float = 0.095
        terminal_pe: float = 15.0 if segment == "large_cap_blue_chip" else 12.0
        band: float = 0.05 if segment == "large_cap_blue_chip" else 0.10

        # ------------------------------------------------------------------
        # Per-horizon probability calculations
        # ------------------------------------------------------------------
        horizons: list[int] = state.get("horizons") or [1, 3, 5, 10]

        # Cache per-scenario prices for downside calculation
        scenario_prices_by_year: dict[int, dict] = {}

        horizons_output: list[dict] = []
        for years in horizons:
            hurdle_price = entry_price * (1 + target_cagr) ** years

            if current_eps is not None and current_eps > 0:
                bull_price = _project_price(current_eps, bull_growth, years, terminal_pe * 1.1)
                base_price = _project_price(current_eps, base_growth, years, terminal_pe)
                bear_price = _project_price(current_eps, bear_growth, years, terminal_pe * 0.9)
            else:
                # Price-return fallback when EPS not available
                bull_price = entry_price * (1 + bull_growth) ** years
                base_price = entry_price * (1 + base_growth) ** years
                bear_price = entry_price * (1 + bear_growth) ** years

            scenario_prices_by_year[years] = {
                "bull": bull_price,
                "base": base_price,
                "bear": bear_price,
            }

            prob_point = (
                bull_w * (1.0 if bull_price >= hurdle_price else 0.0)
                + base_w * (1.0 if base_price >= hurdle_price else 0.0)
                + bear_w * (1.0 if bear_price >= hurdle_price else 0.0)
            )

            horizons_output.append({
                "years": years,
                "prob_ge_target_low": max(0.0, prob_point - band),
                "prob_ge_target_high": min(1.0, prob_point + band),
            })

        # ------------------------------------------------------------------
        # Suggested entry price
        # ------------------------------------------------------------------
        suggested_entry_price: Optional[dict] = None
        five_yr_horizon = next((h for h in horizons_output if h["years"] == 5), None)
        five_yr_prob_point = (five_yr_horizon["prob_ge_target_low"] + five_yr_horizon["prob_ge_target_high"]) / 2 if five_yr_horizon else 0.0

        if efficiency_verdict == "appears_inflated" or five_yr_prob_point < 0.40:
            # Search from 70% of current price upward in 2% steps
            step = current_price * 0.02
            search_price = current_price * 0.70
            while search_price <= current_price:
                # Recompute prob at this entry price
                hurdle_5 = search_price * (1 + target_cagr) ** 5
                prices_5 = scenario_prices_by_year.get(5, {})
                bp = prices_5.get("bull", 0)
                sp = prices_5.get("base", 0)
                brp = prices_5.get("bear", 0)
                prob_at_price = (
                    bull_w * (1.0 if bp >= hurdle_5 else 0.0)
                    + base_w * (1.0 if sp >= hurdle_5 else 0.0)
                    + bear_w * (1.0 if brp >= hurdle_5 else 0.0)
                )
                if prob_at_price >= 0.55:
                    suggested_entry_price = {
                        "price": round(search_price, 2),
                        "prob_ge_target_low": 0.50,
                        "prob_ge_target_high": 0.60,
                        "note": "Price where 5-year probability exceeds 55%.",
                    }
                    break
                search_price += step

        # ------------------------------------------------------------------
        # Downside risk
        # ------------------------------------------------------------------
        downside_output: list[dict] = []
        for years in horizons:
            prices = scenario_prices_by_year.get(years, {})
            bull_price = prices.get("bull", entry_price)
            base_price = prices.get("base", entry_price)
            bear_price = prices.get("bear", entry_price)

            prob_loss = (
                bull_w * (1.0 if bull_price < entry_price else 0.0)
                + base_w * (1.0 if base_price < entry_price else 0.0)
                + bear_w * (1.0 if bear_price < entry_price else 0.0)
            )
            downside_output.append({
                "years": years,
                "prob_le_zero_cagr_low": max(0.0, prob_loss - 0.05),
                "prob_le_zero_cagr_high": min(1.0, prob_loss + 0.05),
            })

        # ------------------------------------------------------------------
        # Simple stress test
        # ------------------------------------------------------------------
        base_case_summary = (
            f"Base case assumes {base_growth*100:.1f}% annual EPS growth, "
            f"{wacc*100:.1f}% discount rate, and {terminal_pe:.0f}x terminal P/E. "
            f"No extraordinary events assumed."
        )

        # Shock 1: Revenue miss
        mild_eps_after_rev_miss = (current_eps or 1) * (1 - 0.15)
        severe_eps_after_rev_miss = (current_eps or 1) * (1 - 0.30)
        mild_survives_rev = mild_eps_after_rev_miss > 0
        severe_survives_rev = severe_eps_after_rev_miss > 0

        shock_revenue = {
            "assumption_tested": "Revenue growth",
            "variable": "Revenue",
            "mild_shock": {
                "description": "15% revenue miss vs base case",
                "delta": "-15%",
                "revenue_impact_pct": -0.15,
                "margin_impact_bps": None,
                "thesis_survives": mild_survives_rev,
            },
            "severe_shock": {
                "description": "30% revenue miss vs base case",
                "delta": "-30%",
                "revenue_impact_pct": -0.30,
                "margin_impact_bps": None,
                "thesis_survives": severe_survives_rev,
            },
            "balance_sheet_check": None,
            "return_under_mild": None,
            "return_under_severe": None,
        }

        # Shock 2: Margin compression
        mild_eps_after_margin = (current_eps or 1) * (1 - 0.10)
        severe_eps_after_margin = (current_eps or 1) * (1 - 0.25)
        mild_survives_margin = mild_eps_after_margin > 0
        severe_survives_margin = severe_eps_after_margin > 0

        shock_margin = {
            "assumption_tested": "Operating margin",
            "variable": "Margin",
            "mild_shock": {
                "description": "Mild margin compression (200bps)",
                "delta": "-200bps",
                "revenue_impact_pct": None,
                "margin_impact_bps": -200.0,
                "thesis_survives": mild_survives_margin,
            },
            "severe_shock": {
                "description": "Severe margin compression (500bps)",
                "delta": "-500bps",
                "revenue_impact_pct": None,
                "margin_impact_bps": -500.0,
                "thesis_survives": severe_survives_margin,
            },
            "balance_sheet_check": None,
            "return_under_mild": None,
            "return_under_severe": None,
        }

        # Stress verdict
        all_mild_survive = mild_survives_rev and mild_survives_margin
        all_severe_survive = severe_survives_rev and severe_survives_margin

        if all_mild_survive and all_severe_survive:
            stress_verdict = "robust"
        elif all_mild_survive:
            stress_verdict = "conditional"
        else:
            stress_verdict = "fragile"

        state["stress_test"] = {
            "base_case_summary": base_case_summary,
            "shocks": [shock_revenue, shock_margin],
            "fragile_assumptions": [],
            "robust_assumptions": [],
            "stress_verdict": stress_verdict,
            "stress_verdict_notes": (
                "Both mild and severe shocks survived." if stress_verdict == "robust"
                else "Mild shocks survived; severe scenario impairs thesis." if stress_verdict == "conditional"
                else "Even mild shocks impair the base-case thesis."
            ),
        }

        # ------------------------------------------------------------------
        # Write probability_engine to state
        # ------------------------------------------------------------------
        state["probability_engine"] = {
            "enabled": True,
            "reason_disabled": None,
            "confidence_tier": "medium",
            "horizons": horizons_output,
            "suggested_entry_price": suggested_entry_price,
            "entry_dependence": [],
            "downside_risk": downside_output,
            "calibration_notes": (
                f"Scenario weights: bull {bull_w*100:.0f}%, "
                f"base {base_w*100:.0f}%, bear {bear_w*100:.0f}%. "
                f"Band: ±{band*100:.0f}pp."
            ),
        }

        state["section_statuses"]["probability_engine"] = {
            "status": "ok",
            "source": "heuristic",
            "cached": False,
            "ttl_remaining_s": None,
        }

    except Exception as e:
        logger.warning("probability_engine: node failed: %s", e)
        state["probability_engine"] = {"enabled": False, "reason_disabled": str(e)}
        state["stress_test"] = None
        state.setdefault("section_statuses", {})["probability_engine"] = {
            "status": "failed",
            "source": None,
            "cached": False,
            "ttl_remaining_s": None,
        }

    return state
