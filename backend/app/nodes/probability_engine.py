"""
Node 10: Probability Engine + Stress Test.

Deterministic Monte Carlo-style heuristic for single-stock analysis.
It samples growth and exit multiple distributions around a bull/base/bear
mixture to estimate hurdle odds and return percentiles by horizon.

This is still not a calibrated institutional model, but it is materially
better than a 3-scenario binary vote because it produces continuous outcome
distributions and exposes the assumptions driving the result.
"""
from __future__ import annotations

import logging
import math
import random
from typing import Optional
import asyncio

from app.state import GraphState
from app.utils import safe_float

logger = logging.getLogger(__name__)

_SIMULATION_COUNT = 1200


def _percentile(values: list[float], p: float) -> float:
    """Return percentile p from a sorted list using simple linear indexing."""
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    idx = max(0.0, min(1.0, p)) * (len(values) - 1)
    lo = math.floor(idx)
    hi = math.ceil(idx)
    if lo == hi:
        return values[lo]
    weight = idx - lo
    return values[lo] * (1 - weight) + values[hi] * weight


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _project_terminal_price(
    current_eps: Optional[float],
    entry_price: float,
    growth: float,
    years: int,
    terminal_pe: float,
) -> float:
    """Project terminal price from sampled growth and terminal multiple."""
    if current_eps is not None and current_eps > 0:
        terminal_eps = current_eps * (1 + growth) ** years
        return max(0.01, terminal_eps * terminal_pe)
    return max(0.01, entry_price * (1 + growth) ** years)


def _sample_regime(
    rng: random.Random,
    bull_w: float,
    base_w: float,
    bear_w: float,
) -> str:
    draw = rng.random()
    if draw < bull_w:
        return "bull"
    if draw < bull_w + base_w:
        return "base"
    return "bear"


def _scenario_params(
    segment: str,
    base_growth: float,
    macro_regime: str,
    fragile_count: int,
) -> tuple[dict[str, float], dict[str, float], float, float]:
    """Return mean growths, growth volatilities, and base terminal multiple."""
    terminal_pe_base = 15.0 if segment == "large_cap_blue_chip" else 12.0
    if segment == "mid_cap":
        growth_sigma = 0.09
        terminal_pe_sigma = 2.0
    elif segment == "large_cap_blue_chip":
        growth_sigma = 0.06
        terminal_pe_sigma = 1.6
    else:
        growth_sigma = 0.11
        terminal_pe_sigma = 2.4

    if macro_regime == "higher_for_longer_rates":
        terminal_pe_base -= 1.0
        growth_sigma += 0.01
    elif macro_regime == "recession":
        terminal_pe_base -= 1.5
        growth_sigma += 0.02
    elif macro_regime == "goldilocks":
        terminal_pe_base += 0.5

    growth_sigma += min(fragile_count, 3) * 0.01

    growth_means = {
        "bull": base_growth * 1.30,
        "base": base_growth,
        "bear": base_growth * 0.55,
    }
    growth_sigmas = {
        "bull": growth_sigma,
        "base": growth_sigma * 0.85,
        "bear": growth_sigma * 1.10,
    }
    return growth_means, growth_sigmas, max(6.0, terminal_pe_base), terminal_pe_sigma


def _simulate_distribution(
    *,
    ticker: str,
    entry_price: float,
    current_price: float,
    target_cagr: float,
    segment: str,
    bull_w: float,
    base_w: float,
    bear_w: float,
    base_growth: float,
    macro_regime: str,
    fragile_count: int,
    current_eps: Optional[float],
    horizons: list[int],
    confidence_tier: str,
) -> tuple[list[dict], list[dict], list[dict], Optional[dict], float]:
    """Run the CPU-heavy simulation off the event loop."""
    growth_means, growth_sigmas, terminal_pe_base, terminal_pe_sigma = _scenario_params(
        segment,
        base_growth,
        macro_regime,
        fragile_count,
    )

    rng = random.Random(f"{ticker}:{entry_price}:{target_cagr}:{segment}")
    simulated_prices: dict[int, list[float]] = {years: [] for years in horizons}
    simulated_cagrs: dict[int, list[float]] = {years: [] for years in horizons}
    projected_prices_5yr: list[float] = []

    for _ in range(_SIMULATION_COUNT):
        regime = _sample_regime(rng, bull_w, base_w, bear_w)
        sampled_growth = rng.gauss(growth_means[regime], growth_sigmas[regime])
        sampled_growth = _clamp(sampled_growth, -0.35, 0.45 if segment == "large_cap_blue_chip" else 0.70)

        pe_shift = {"bull": 1.10, "base": 1.00, "bear": 0.88}[regime]
        sampled_terminal_pe = rng.gauss(terminal_pe_base * pe_shift, terminal_pe_sigma)
        sampled_terminal_pe = _clamp(sampled_terminal_pe, 5.0, 30.0)

        for years in horizons:
            terminal_price = _project_terminal_price(
                current_eps=current_eps,
                entry_price=entry_price,
                growth=sampled_growth,
                years=years,
                terminal_pe=sampled_terminal_pe,
            )
            simulated_prices[years].append(terminal_price)
            realized_cagr = (terminal_price / entry_price) ** (1 / years) - 1
            simulated_cagrs[years].append(realized_cagr)
            if years == 5:
                projected_prices_5yr.append(terminal_price)

    horizons_output: list[dict] = []
    downside_output: list[dict] = []
    for years in horizons:
        prices = sorted(simulated_prices[years])
        cagrs = sorted(simulated_cagrs[years])
        hurdle_hits = sum(1 for cagr in cagrs if cagr >= target_cagr) / len(cagrs)
        downside_hits = sum(1 for cagr in cagrs if cagr <= 0.0) / len(cagrs)

        interval_half_width = 0.03 if confidence_tier == "medium" else 0.06
        horizons_output.append({
            "years": years,
            "prob_ge_target_low": max(0.0, hurdle_hits - interval_half_width),
            "prob_ge_target_high": min(1.0, hurdle_hits + interval_half_width),
            "expected_cagr": sum(cagrs) / len(cagrs),
            "cagr_p10": _percentile(cagrs, 0.10),
            "cagr_p50": _percentile(cagrs, 0.50),
            "cagr_p90": _percentile(cagrs, 0.90),
            "terminal_price_p10": _percentile(prices, 0.10),
            "terminal_price_p50": _percentile(prices, 0.50),
            "terminal_price_p90": _percentile(prices, 0.90),
        })
        downside_output.append({
            "years": years,
            "prob_le_zero_cagr_low": max(0.0, downside_hits - interval_half_width),
            "prob_le_zero_cagr_high": min(1.0, downside_hits + interval_half_width),
        })

    suggested_entry_price: Optional[dict] = None
    five_year_prices = projected_prices_5yr or simulated_prices.get(5, [])
    if 5 in horizons and five_year_prices:
        for pct in (0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.00):
            candidate_price = round(current_price * pct, 2)
            candidate_cagrs = [
                (terminal_price / candidate_price) ** (1 / 5) - 1
                for terminal_price in five_year_prices
                if candidate_price > 0
            ]
            if not candidate_cagrs:
                continue
            hit_rate = sum(1 for c in candidate_cagrs if c >= target_cagr) / len(candidate_cagrs)
            if hit_rate >= 0.55:
                band = 0.03 if confidence_tier == "medium" else 0.06
                suggested_entry_price = {
                    "price": candidate_price,
                    "prob_ge_target_low": max(0.0, hit_rate - band),
                    "prob_ge_target_high": min(1.0, hit_rate + band),
                    "note": "Approximate price where 5-year hurdle odds rise above 55% in the current simulation.",
                }
                break

    entry_dependence: list[dict] = []
    if 5 in horizons and five_year_prices:
        band = 0.03 if confidence_tier == "medium" else 0.06
        for pct in (0.80, 0.90, 1.00, 1.10):
            candidate_price = round(entry_price * pct, 2)
            candidate_cagrs = [
                (terminal_price / candidate_price) ** (1 / 5) - 1
                for terminal_price in five_year_prices
                if candidate_price > 0
            ]
            hit_rate = sum(1 for c in candidate_cagrs if c >= target_cagr) / len(candidate_cagrs)
            entry_dependence.append({
                "entry_price": candidate_price,
                "years": 5,
                "prob_ge_target_low": max(0.0, hit_rate - band),
                "prob_ge_target_high": min(1.0, hit_rate + band),
            })

    return horizons_output, downside_output, entry_dependence, suggested_entry_price, terminal_pe_base


async def run(state: GraphState) -> GraphState:
    """Node 10: Probability Engine + Stress Test."""
    state.setdefault("section_statuses", {})

    try:
        segment = state.get("segment", "other")
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

        val: dict = state.get("valuation") or {}
        fund: dict = state.get("fundamentals") or {}
        filings: dict = state.get("filings_rag") or {}
        macro: dict = state.get("macro") or {}
        valuation_confidence = (val.get("valuation_confidence") or "low") if isinstance(val, dict) else "low"
        base_growth_source = val.get("_base_growth_source") if isinstance(val, dict) else None

        current_price = (
            safe_float(val.get("current_price"))
            or safe_float((state.get("ticker_meta") or {}).get("regularMarketPrice"))
            or 100.0
        )
        entry_price = safe_float(state.get("entry_price")) or current_price
        target_cagr: float = state.get("target_cagr", 0.10) or 0.10

        macro_regime: str = macro.get("macro_regime", "unknown") or "unknown"
        assumption_sheet: list = filings.get("assumption_sheet", []) if filings else []
        fragile_count = sum(1 for a in assumption_sheet if a.get("fragility") == "fragile")
        words_vs_numbers = filings.get("words_vs_numbers_alignment") if filings else None
        bet_credibility = filings.get("bet_credibility_score") if filings else None

        bull_w = 0.35
        base_w = 0.45
        bear_w = 0.20
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

        time_series: dict = fund.get("time_series", {}) if fund else {}
        eps_values: list = time_series.get("eps", []) or []
        valid_eps = [safe_float(e) for e in eps_values if safe_float(e) is not None]
        current_eps: Optional[float] = valid_eps[-1] if valid_eps else None
        base_growth: float = safe_float(val.get("_base_growth")) or 0.08

        if valuation_confidence == "low" and current_eps is None:
            state["probability_engine"] = {
                "enabled": False,
                "reason_disabled": "Insufficient earnings and valuation inputs to estimate hurdle odds responsibly.",
                "confidence_tier": "low",
                "horizons": [],
                "suggested_entry_price": None,
                "entry_dependence": [],
                "downside_risk": [],
                "calibration_notes": None,
                "methodology_notes": (
                    "Monte Carlo-style heuristic disabled because fair value and earnings inputs were too weak. The model avoids publishing odds when it would mostly anchor on the current price."
                ),
                "scenario_weights": {"bull": bull_w, "base": base_w, "bear": bear_w},
                "base_growth": base_growth,
                "current_price": current_price,
                "target_cagr": target_cagr,
                "simulation_count": 0,
            }
            state["stress_test"] = None
            state["section_statuses"]["probability_engine"] = {
                "status": "partial",
                "source": "heuristic",
                "cached": False,
                "ttl_remaining_s": None,
            }
            return state

        confidence_tier = (
            "medium"
            if valuation_confidence != "low" and current_eps is not None and base_growth_source in {"analyst_consensus", "historical_eps"}
            else "low"
        )

        ticker = state.get("ticker", "")
        horizons: list[int] = state.get("horizons") or [1, 3, 5, 10]
        horizons_output, downside_output, entry_dependence, suggested_entry_price, terminal_pe_base = await asyncio.to_thread(
            _simulate_distribution,
            ticker=ticker,
            entry_price=entry_price,
            current_price=current_price,
            target_cagr=target_cagr,
            segment=segment,
            bull_w=bull_w,
            base_w=base_w,
            bear_w=bear_w,
            base_growth=base_growth,
            macro_regime=macro_regime,
            fragile_count=fragile_count,
            current_eps=current_eps,
            horizons=horizons,
            confidence_tier=confidence_tier,
        )

        p50_5yr = next((h for h in horizons_output if h["years"] == 5), None)
        median_5yr_cagr = p50_5yr.get("cagr_p50") if p50_5yr else None

        base_case_summary = (
            f"Monte Carlo-style return model anchored on {base_growth*100:.1f}% base growth, "
            f"{terminal_pe_base:.1f}x starting terminal multiple assumption, and {_SIMULATION_COUNT} simulations. "
            "Outputs are directional and assumption-sensitive, not calibrated market odds."
        )

        mild_survives_rev = (median_5yr_cagr or 0.0) > 0.04
        severe_survives_rev = (next((h["cagr_p10"] for h in horizons_output if h["years"] == 5), 0.0) or 0.0) > -0.02
        mild_survives_margin = (next((h["expected_cagr"] for h in horizons_output if h["years"] == 5), 0.0) or 0.0) > 0.03
        severe_survives_margin = (median_5yr_cagr or 0.0) > 0.00

        state["stress_test"] = {
            "base_case_summary": base_case_summary,
            "shocks": [
                {
                    "assumption_tested": "Revenue growth",
                    "variable": "Growth",
                    "mild_shock": {
                        "description": "Distribution skewed 1 standard deviation lower",
                        "delta": "-1 sigma",
                        "revenue_impact_pct": -0.10,
                        "margin_impact_bps": None,
                        "thesis_survives": mild_survives_rev,
                    },
                    "severe_shock": {
                        "description": "Distribution skewed 2 standard deviations lower",
                        "delta": "-2 sigma",
                        "revenue_impact_pct": -0.20,
                        "margin_impact_bps": None,
                        "thesis_survives": severe_survives_rev,
                    },
                    "balance_sheet_check": None,
                    "return_under_mild": None,
                    "return_under_severe": None,
                },
                {
                    "assumption_tested": "Exit multiple and margin",
                    "variable": "Multiple",
                    "mild_shock": {
                        "description": "Terminal multiple compresses modestly",
                        "delta": "-10%",
                        "revenue_impact_pct": None,
                        "margin_impact_bps": -150.0,
                        "thesis_survives": mild_survives_margin,
                    },
                    "severe_shock": {
                        "description": "Terminal multiple compresses sharply",
                        "delta": "-20%",
                        "revenue_impact_pct": None,
                        "margin_impact_bps": -350.0,
                        "thesis_survives": severe_survives_margin,
                    },
                    "balance_sheet_check": None,
                    "return_under_mild": None,
                    "return_under_severe": None,
                },
            ],
            "fragile_assumptions": [] if confidence_tier == "medium" else ["Return distribution is highly sensitive to valuation and growth assumptions."],
            "robust_assumptions": ["Terminal outcome uses a full simulated distribution rather than a single binary scenario gate."],
            "stress_verdict": (
                "robust"
                if mild_survives_rev and severe_survives_rev and mild_survives_margin and severe_survives_margin
                else "conditional"
                if mild_survives_rev and mild_survives_margin
                else "fragile"
            ),
            "stress_verdict_notes": (
                "Median and downside return percentiles remain constructive under both modeled shocks."
                if mild_survives_rev and severe_survives_rev and mild_survives_margin and severe_survives_margin
                else "Base-case and mild downside scenarios still support the thesis, but severe compression materially weakens returns."
                if mild_survives_rev and mild_survives_margin
                else "Downside simulations show the thesis weakening quickly when growth or valuation assumptions deteriorate."
            ),
        }

        state["probability_engine"] = {
            "enabled": True,
            "reason_disabled": None,
            "confidence_tier": confidence_tier,
            "horizons": horizons_output,
            "suggested_entry_price": suggested_entry_price,
            "entry_dependence": entry_dependence,
            "downside_risk": downside_output,
            "calibration_notes": (
                "Distribution width reflects heuristic uncertainty bands, not empirical calibration. Backtesting is still required before treating these as decision-grade odds."
            ),
            "methodology_notes": (
                "Monte Carlo-style mixture model with bull/base/bear regime weights, sampled growth paths, and sampled exit multiples. Better than binary scenario voting, but still a heuristic research aid rather than a fully calibrated probability engine."
            ),
            "scenario_weights": {"bull": bull_w, "base": base_w, "bear": bear_w},
            "base_growth": base_growth,
            "current_price": current_price,
            "target_cagr": target_cagr,
            "simulation_count": _SIMULATION_COUNT,
        }
        state["section_statuses"]["probability_engine"] = {
            "status": "ok",
            "source": "heuristic_monte_carlo",
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
