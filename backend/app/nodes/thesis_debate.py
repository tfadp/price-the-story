"""
Node 10.5: Thesis Debate Engine.

Runs a structured bull-vs-bear debate before PM Synthesis to produce sharper verdicts.
Bull and Bear agents run in parallel, then a Judge synthesizes.

Skip conditions (returns empty thesis_debate):
- data_quality == "low"
- probability_engine.enabled == False
- segment == "small_cap_high_vol" AND fewer than 3 items in assumption_sheet
  AND no stress_test AND no words_vs_numbers_alignment

Degraded mode (runs with fundamentals+valuation instead of assumption sheet):
- assumption_sheet has fewer than 3 items — still runs but uses richer fundamentals context

Minimum viable input to run at all:
- current_price (from valuation or ticker_meta)
- fair_value_base (from valuation)
- business_summary (from fundamentals.thesis)
- at least one of: assumption_sheet, stress_test, or words_vs_numbers_alignment
"""
import asyncio
import json
import logging
from typing import Optional

from app.config import settings
from app.state import GraphState
from app.utils import safe_float

logger = logging.getLogger(__name__)

# How long to wait for each LLM call before giving up.
# Wrapped around every ainvoke to prevent a slow Claude call from stalling the pipeline.
_LLM_TIMEOUT_S = 30.0

_BULL_PROMPT_TEMPLATE = """You are a senior equity analyst who believes in this investment thesis.

Company: {ticker} ({segment})
Business: {business_summary}
{assumption_context}
Fair value range: ${fair_value_low} – ${fair_value_high} (base: ${fair_value_base})
Current price: ${current_price}
Target: {target_cagr_pct}% CAGR over {holding_period} years
Probability at target: {prob_low}–{prob_high}%
Stress test verdict: {stress_verdict}

Make the strongest possible case that this investment achieves the target return.
Be specific: which assumptions are most robust? What evidence supports the growth
story? What does the market appear to be underpricing? Reference the actual numbers
from the data above.

Do not hedge. Do not caveat. Make the bull case as if your reputation depends on it.
If the case is genuinely weak, say so — a credible bull analyst doesn't argue a losing position.

Output: 3–5 sentences. Plain English. No jargon."""

_BEAR_PROMPT_TEMPLATE = """You are a senior equity analyst who is skeptical of this investment thesis.

Company: {ticker} ({segment})
Business: {business_summary}
{assumption_context}
Fair value range: ${fair_value_low} – ${fair_value_high} (base: ${fair_value_base})
Current price: ${current_price}
Target: {target_cagr_pct}% CAGR over {holding_period} years
Probability at target: {prob_low}–{prob_high}%
Stress test verdict: {stress_verdict}

Make the strongest possible case that this investment fails to achieve the target return.
Be specific: which assumption is the single most likely to break? What is the market
pricing in that management hasn't delivered? Where does the words-vs-numbers alignment
raise doubt?

Focus on the most likely failure mode, not the worst-case scenario. A good bear case
identifies the specific, plausible path to disappointing returns — not a catastrophe fantasy.

Do not hedge. Do not acknowledge the bull case. Make the bear case as if your
reputation depends on it. If the bear case is genuinely weak, say so.

Output: 3–5 sentences. Plain English. No jargon."""

_JUDGE_PROMPT_TEMPLATE = """You are a portfolio manager reviewing a bull/bear debate on {ticker}.

Bull case: {bull_output}

Bear case: {bear_output}

Your job is NOT to pick a winner. Your job is to identify:

1. thesis_tension: One sentence naming the core disagreement between bull and bear.
2. strongest_bull_point: The single most compelling element of the bull case.
3. strongest_bear_point: The single most compelling element of the bear case.
4. unresolved_question: One specific, answerable question that would resolve the
   debate if answered. Must be tied to an observable metric or upcoming event.
5. verdict_lean: "bull" | "bear" | "genuinely_uncertain"
6. conviction_modifier: "strengthens" | "weakens" | "unchanged" — does this debate
   change the probability engine's output?

Output as JSON only. No hedging in thesis_tension — name the actual tension.

Return this JSON:
{{
  "thesis_tension": "...",
  "strongest_bull_point": "...",
  "strongest_bear_point": "...",
  "unresolved_question": "...",
  "verdict_lean": "bull|bear|genuinely_uncertain",
  "conviction_modifier": "strengthens|weakens|unchanged"
}}"""

_SKIP_STATUS = {
    "thesis_debate": {
        "status": "partial",
        "source": "skipped",
        "cached": False,
        "ttl_remaining_s": None,
    }
}

_FAIL_STATUS = {
    "thesis_debate": {
        "status": "failed",
        "source": None,
        "cached": False,
        "ttl_remaining_s": None,
    }
}

_OK_STATUS = {
    "thesis_debate": {
        "status": "ok",
        "source": "claude-sonnet-4-6",
        "cached": False,
        "ttl_remaining_s": None,
    }
}


def _should_skip(state: GraphState) -> bool:
    """Return True when the node should be bypassed entirely.

    The debate adds no value when data quality is too low to debate,
    when the probability engine was disabled, or when a small-cap high-vol
    ticker lacks even minimal growth-bet context.
    """
    data_quality: str = state.get("data_quality", "low") or "low"
    if data_quality == "low":
        return True

    prob: dict = state.get("probability_engine") or {}
    if not prob.get("enabled", True):
        return True

    segment: str = state.get("segment", "other") or "other"
    filings: dict = state.get("filings_rag") or {}
    assumption_sheet: list = filings.get("assumption_sheet", []) if filings else []
    stress_test: Optional[dict] = state.get("stress_test")
    words_vs_numbers = filings.get("words_vs_numbers_alignment") if filings else None

    if (
        segment == "small_cap_high_vol"
        and len(assumption_sheet) < 3
        and stress_test is None
        and words_vs_numbers is None
    ):
        return True

    return False


def _build_assumption_context(state: GraphState) -> str:
    """Build the assumption_context block that goes into both analyst prompts.

    Uses the full assumption sheet when rich enough (>=3 items).
    Falls back to a fundamentals summary when the sheet is thin.
    Always appends words-vs-numbers alignment when available.
    """
    filings: dict = state.get("filings_rag") or {}
    assumption_sheet: list = filings.get("assumption_sheet", []) if filings else []
    stated_bet: Optional[str] = filings.get("stated_bet") if filings else None
    words_vs_numbers: Optional[str] = filings.get("words_vs_numbers_alignment") if filings else None

    lines: list[str] = []

    if len(assumption_sheet) >= 3:
        # Full mode — show the growth bet and up to 5 assumptions
        if stated_bet:
            lines.append(f"Stated growth bet: {stated_bet}")
        lines.append("Assumption sheet:")
        for item in assumption_sheet[:5]:
            if isinstance(item, dict):
                assumption_text = item.get("assumption", str(item))
                lines.append(f"- {assumption_text}")
            else:
                lines.append(f"- {item}")
    else:
        # Degraded mode — use fundamentals context instead
        fund: dict = state.get("fundamentals") or {}
        time_series: dict = fund.get("time_series", {}) if fund else {}

        revenue_values: list = time_series.get("revenue", []) or []
        valid_revenues = [safe_float(r) for r in revenue_values if safe_float(r) is not None]
        rev_growth_str = "N/A"
        if len(valid_revenues) >= 2:
            rev_growth = (valid_revenues[-1] / valid_revenues[0]) ** (1 / max(len(valid_revenues) - 1, 1)) - 1
            rev_growth_str = f"{rev_growth * 100:.1f}%"

        val: dict = state.get("valuation") or {}
        op_margin_str = "N/A"
        op_income = safe_float(val.get("operating_income"))
        revenue = safe_float(val.get("revenue"))
        if op_income is not None and revenue is not None and revenue > 0:
            op_margin_str = f"{op_income / revenue * 100:.1f}%"

        fcf_yield_str = "N/A"
        current_price = safe_float(val.get("current_price"))
        fcf_per_share = safe_float(val.get("fcf_per_share"))
        if current_price is not None and fcf_per_share is not None and current_price > 0:
            fcf_yield_str = f"{fcf_per_share / current_price * 100:.1f}%"

        lines.append(
            f"Fundamentals context: Revenue growth {rev_growth_str}, "
            f"Operating margin {op_margin_str}, FCF yield {fcf_yield_str}"
        )

    if words_vs_numbers:
        lines.append(f"Words-vs-numbers alignment: {words_vs_numbers}")

    return "\n".join(lines)


def _build_prompt_context(state: GraphState) -> Optional[dict]:
    """Extract the shared context variables needed to fill both analyst prompts.

    Returns None when the minimum viable inputs are absent.
    """
    val: dict = state.get("valuation") or {}
    fund: dict = state.get("fundamentals") or {}
    prob: dict = state.get("probability_engine") or {}

    current_price = (
        safe_float(val.get("current_price"))
        or safe_float((state.get("ticker_meta") or {}).get("regularMarketPrice"))
    )
    fair_value_base = safe_float(val.get("fair_value_base"))

    thesis_dict: Optional[dict] = fund.get("thesis") if fund else None
    business_summary: Optional[str] = (
        thesis_dict.get("business_summary") if isinstance(thesis_dict, dict) else None
    )

    # Minimum viable check — all three must be present
    if current_price is None or fair_value_base is None or not business_summary:
        return None

    # At least one growth-bet signal must exist
    filings: dict = state.get("filings_rag") or {}
    assumption_sheet: list = filings.get("assumption_sheet", []) if filings else []
    stress_test = state.get("stress_test")
    words_vs_numbers = filings.get("words_vs_numbers_alignment") if filings else None
    if not assumption_sheet and stress_test is None and words_vs_numbers is None:
        return None

    fair_value_low = safe_float(val.get("fair_value_low")) or fair_value_base * 0.85
    fair_value_high = safe_float(val.get("fair_value_high")) or fair_value_base * 1.15

    target_cagr: float = state.get("target_cagr", 0.10) or 0.10
    target_cagr_pct = round(target_cagr * 100, 1)

    horizons: list[int] = state.get("horizons") or [1, 3, 5, 10]
    holding_period: int = 5 if 5 in horizons else horizons[-1]

    # Pull probability range for the holding period
    prob_low_str = "N/A"
    prob_high_str = "N/A"
    for h in (prob.get("horizons") or []):
        if isinstance(h, dict) and h.get("years") == holding_period:
            low = h.get("prob_ge_target_low")
            high = h.get("prob_ge_target_high")
            if low is not None:
                prob_low_str = f"{low * 100:.0f}"
            if high is not None:
                prob_high_str = f"{high * 100:.0f}"
            break

    stress_verdict: str = (state.get("stress_test") or {}).get("stress_verdict", "unknown") or "unknown"

    return {
        "ticker": state.get("ticker", ""),
        "segment": state.get("segment", "unknown") or "unknown",
        "business_summary": business_summary,
        "assumption_context": _build_assumption_context(state),
        "fair_value_low": round(fair_value_low, 2),
        "fair_value_high": round(fair_value_high, 2),
        "fair_value_base": round(fair_value_base, 2),
        "current_price": round(current_price, 2),
        "target_cagr_pct": target_cagr_pct,
        "holding_period": holding_period,
        "prob_low": prob_low_str,
        "prob_high": prob_high_str,
        "stress_verdict": stress_verdict,
    }


async def run(state: GraphState) -> dict:
    """Node 10.5: Thesis Debate Engine.

    Serial node — reads state["probability_engine"] and state["stress_test"]
    which are both written by the previous serial node (node_probability_engine).
    Returns a partial dict so LangGraph merges it into state.
    """
    # Emit progress before any work starts
    callback = state.get("progress_callback")
    if callback is not None:
        await callback("Debating the thesis", "thesis_debate", 83)

    if _should_skip(state):
        logger.info("thesis_debate: skipped (data_quality=%s, prob_enabled=%s, segment=%s)",
                    state.get("data_quality"), (state.get("probability_engine") or {}).get("enabled"), state.get("segment"))
        return {
            "thesis_debate": None,
            "section_statuses": _SKIP_STATUS,
        }

    if not settings.anthropic_api_key:
        logger.info("thesis_debate: skipped — no ANTHROPIC_API_KEY configured")
        return {
            "thesis_debate": None,
            "section_statuses": _SKIP_STATUS,
        }

    ctx = _build_prompt_context(state)
    if ctx is None:
        logger.info("thesis_debate: skipped — minimum viable inputs absent")
        return {
            "thesis_debate": None,
            "section_statuses": _SKIP_STATUS,
        }

    try:
        # Lazy import — never at module level (breaks pytest collection)
        try:
            from langchain_anthropic import ChatAnthropic
            from langchain_core.messages import HumanMessage
        except ImportError as e:
            raise RuntimeError("langchain_anthropic not installed") from e

        bull_llm = ChatAnthropic(
            model="claude-sonnet-4-6",
            api_key=settings.anthropic_api_key,
            max_tokens=800,
        )
        bear_llm = ChatAnthropic(
            model="claude-sonnet-4-6",
            api_key=settings.anthropic_api_key,
            max_tokens=800,
        )
        judge_llm = ChatAnthropic(
            model="claude-sonnet-4-6",
            api_key=settings.anthropic_api_key,
            max_tokens=600,
        )

        bull_prompt = _BULL_PROMPT_TEMPLATE.format(**ctx)
        bear_prompt = _BEAR_PROMPT_TEMPLATE.format(**ctx)

        # Bull and Bear run in parallel — neither reads the other's output
        bull_task = asyncio.wait_for(
            bull_llm.ainvoke([HumanMessage(content=bull_prompt)]),
            timeout=_LLM_TIMEOUT_S,
        )
        bear_task = asyncio.wait_for(
            bear_llm.ainvoke([HumanMessage(content=bear_prompt)]),
            timeout=_LLM_TIMEOUT_S,
        )

        bull_response, bear_response = await asyncio.gather(bull_task, bear_task)
        bull_output: str = bull_response.content
        bear_output: str = bear_response.content

        # Judge synthesizes both arguments
        judge_prompt = _JUDGE_PROMPT_TEMPLATE.format(
            ticker=ctx["ticker"],
            bull_output=bull_output,
            bear_output=bear_output,
        )
        judge_response = await asyncio.wait_for(
            judge_llm.ainvoke([HumanMessage(content=judge_prompt)]),
            timeout=_LLM_TIMEOUT_S,
        )

        # Parse JSON from judge — strip markdown fences if present
        raw = judge_response.content.strip()
        if raw.startswith("```"):
            # Strip opening fence (e.g. ```json) and closing fence
            raw = raw.split("\n", 1)[-1]
            if raw.endswith("```"):
                raw = raw[:-3].strip()

        judge_result: dict = json.loads(raw)

        # Validate that all required judge keys are present
        required_keys = {
            "thesis_tension",
            "strongest_bull_point",
            "strongest_bear_point",
            "unresolved_question",
            "verdict_lean",
            "conviction_modifier",
        }
        missing = required_keys - judge_result.keys()
        if missing:
            logger.warning("thesis_debate: judge response missing keys: %s", missing)
            raise ValueError(f"Judge JSON missing required keys: {missing}")

        return {
            "thesis_debate": {
                "bull_case": bull_output,
                "bear_case": bear_output,
                "thesis_tension": judge_result["thesis_tension"],
                "strongest_bull_point": judge_result["strongest_bull_point"],
                "strongest_bear_point": judge_result["strongest_bear_point"],
                "unresolved_question": judge_result["unresolved_question"],
                "verdict_lean": judge_result["verdict_lean"],
                "conviction_modifier": judge_result["conviction_modifier"],
            },
            "section_statuses": _OK_STATUS,
        }

    except json.JSONDecodeError as e:
        logger.warning("thesis_debate: judge returned non-JSON: %s", e)
        return {
            "thesis_debate": None,
            "section_statuses": _FAIL_STATUS,
        }
    except asyncio.TimeoutError:
        logger.warning("thesis_debate: LLM call timed out after %ss", _LLM_TIMEOUT_S)
        return {
            "thesis_debate": None,
            "section_statuses": _FAIL_STATUS,
        }
    except Exception as e:
        logger.warning("thesis_debate: node failed: %s", e)
        return {
            "thesis_debate": None,
            "section_statuses": _FAIL_STATUS,
        }
