"""
Node 11: PM Synthesis.

Generates a verdict paragraph via Claude Sonnet (if API key available),
then runs a post-synthesis hallucination check against a number registry
built from prior node outputs.

Never crashes the pipeline — all exceptions caught and logged.
"""
import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional

from app.state import GraphState
from app.config import settings

logger = logging.getLogger(__name__)


async def run(state: GraphState) -> GraphState:
    """Node 11: PM Synthesis. Generates verdict_paragraph via Claude Sonnet."""
    state.setdefault("section_statuses", {})

    # Emit progress — signals final synthesis phase has started
    callback = state.get("progress_callback")
    if callback is not None:
        await callback("Writing verdict", "pm_synthesis", 80)

    try:
        val: dict = state.get("valuation") or {}
        prob: dict = state.get("probability_engine") or {}
        fund: dict = state.get("fundamentals") or {}

        # ------------------------------------------------------------------
        # Build number_registry (only concrete numbers — no Nones)
        # ------------------------------------------------------------------
        number_registry: dict[str, float] = {}
        if val:
            for key in ("current_price", "fair_value_low", "fair_value_base", "fair_value_high"):
                v = val.get(key)
                if v is not None:
                    number_registry[key] = float(v)

        if prob and prob.get("horizons"):
            for h in prob["horizons"]:
                low = h.get("prob_ge_target_low")
                high = h.get("prob_ge_target_high")
                if low is not None:
                    number_registry[f"prob_{h['years']}yr_low"] = float(low)
                if high is not None:
                    number_registry[f"prob_{h['years']}yr_high"] = float(high)

        # ------------------------------------------------------------------
        # Determine holding period (prefer 5yr, else last horizon)
        # ------------------------------------------------------------------
        horizons: list[int] = state.get("horizons") or [1, 3, 5, 10]
        holding_period: int = 5 if 5 in horizons else horizons[-1]

        # ------------------------------------------------------------------
        # Attempt LLM synthesis
        # ------------------------------------------------------------------
        result: Optional[dict] = None

        if settings.anthropic_api_key:
            try:
                from langchain_anthropic import ChatAnthropic
                from langchain_core.messages import HumanMessage

                llm = ChatAnthropic(
                    model="claude-sonnet-4-6",
                    api_key=settings.anthropic_api_key,
                    max_tokens=1024,
                )

                pea = val.get("price_efficiency_assessment") or {}
                efficiency_verdict = pea.get("efficiency_verdict", "unknown") if isinstance(pea, dict) else "unknown"
                stress_verdict = (state.get("stress_test") or {}).get("stress_verdict", "unknown")
                macro_regime = (state.get("macro") or {}).get("macro_regime", "unknown")
                business_summary = (
                    (fund.get("thesis") or {}).get("business_summary", "Description unavailable")
                    if fund else "Description unavailable"
                )

                prob_low_str = (
                    f"{number_registry[f'prob_{holding_period}yr_low']*100:.0f}%"
                    if f"prob_{holding_period}yr_low" in number_registry
                    else "N/A"
                )
                prob_high_str = (
                    f"{number_registry[f'prob_{holding_period}yr_high']*100:.0f}%"
                    if f"prob_{holding_period}yr_high" in number_registry
                    else "N/A"
                )

                prompt = f"""You are a trusted senior analyst writing a verdict for a long-horizon investor.

TASK: Write a verdict for this exact situation:
- Ticker: {state['ticker']}
- Segment: {state.get('segment', 'unknown')}
- Business: {business_summary}
- Current price: ${number_registry.get('current_price', 'unavailable')}
- Target: {state['target_cagr']*100:.0f}% annually over {holding_period} years
- Fair value range: ${number_registry.get('fair_value_low', 'N/A')} – ${number_registry.get('fair_value_high', 'N/A')}
- Probability at {holding_period}yr: {prob_low_str} – {prob_high_str}
- Price efficiency: {efficiency_verdict}
- Stress verdict: {stress_verdict}
- Macro regime: {macro_regime}

NUMBER REGISTRY (only use these numbers — never invent others): {json.dumps(number_registry)}

RULES:
1. Only use numbers from the registry above
2. 3–5 sentences, verdict-first
3. No jargon. No "buy"/"sell". Write like a trusted friend with deep expertise.
4. Be honest about uncertainty. Give a clear bottom line.
5. Return ONLY valid JSON, no markdown.

Return this JSON structure:
{{
  "verdict_paragraph": "...",
  "confidence_verdict": "high_confidence|moderate_confidence|low_confidence|insufficient_data",
  "red_flags": [
    {{"category": "valuation|execution|competitive|balance_sheet|macro|regulatory|governance", "description": "...", "likelihood": "low|medium|high", "impact": "low|medium|high"}}
  ],
  "disclaimers": [
    "This analysis is for informational purposes only and does not constitute investment advice.",
    "Data sourced from public market data. Verify before acting on any information."
  ]
}}"""

                response = await llm.ainvoke([HumanMessage(content=prompt)])
                result = json.loads(response.content)

            except json.JSONDecodeError as e:
                logger.warning("pm_synthesis: LLM returned non-JSON: %s", e)
                result = None
            except Exception as e:
                logger.warning("pm_synthesis: LLM call failed: %s", e)
                result = None

        # ------------------------------------------------------------------
        # Fallback: template-based synthesis
        # ------------------------------------------------------------------
        if result is None:
            prob_low = number_registry.get(f"prob_{holding_period}yr_low", 0.0)
            prob_high = number_registry.get(f"prob_{holding_period}yr_high", 0.0)
            pea = val.get("price_efficiency_assessment") or {}
            efficiency = pea.get("efficiency_verdict", "unknown") if isinstance(pea, dict) else "unknown"
            prob_enabled = (state.get("probability_engine") or {}).get("enabled", True)

            if prob_enabled:
                verdict_text = (
                    f"At today's price of ${number_registry.get('current_price', 'N/A')}, "
                    f"our heuristic model estimates a {prob_low*100:.0f}%–{prob_high*100:.0f}% chance of reaching a "
                    f"{state['target_cagr']*100:.0f}% annual return over {holding_period} years. "
                    f"The price appears {str(efficiency).replace('_', ' ')} relative to our fair value range "
                    f"of ${number_registry.get('fair_value_low', 'N/A')}–${number_registry.get('fair_value_high', 'N/A')}. "
                    "Treat this as a screening output, not calibrated odds."
                )
            else:
                verdict_text = (
                    f"At today's price of ${number_registry.get('current_price', 'N/A')}, "
                    "the model does not have enough independent inputs to publish return odds responsibly. "
                    f"The current valuation signal is {str(efficiency).replace('_', ' ')} relative to our fair value range "
                    f"of ${number_registry.get('fair_value_low', 'N/A')}–${number_registry.get('fair_value_high', 'N/A')}. "
                    "Treat this ticker as requiring manual review rather than a model-led decision."
                )
            result = {
                "verdict_paragraph": verdict_text,
                "confidence_verdict": "insufficient_data",
                "red_flags": [],
                "disclaimers": ["Analysis based on publicly available data. Not investment advice."],
            }

        # ------------------------------------------------------------------
        # Deterministic confidence_verdict override
        # ------------------------------------------------------------------
        prob_5yr = number_registry.get("prob_5yr_low", 0.0)
        stress_verdict = (state.get("stress_test") or {}).get("stress_verdict") if state.get("stress_test") else None
        data_quality: str = state.get("data_quality", "low") or "low"
        prob_state = state.get("probability_engine") or {}
        prob_enabled = prob_state.get("enabled", True)

        if data_quality == "low" or not prob_enabled:
            confidence_verdict = "insufficient_data"
        elif prob_5yr > 0.50 and stress_verdict == "robust":
            confidence_verdict = "high_confidence"
        elif prob_5yr >= 0.35 or stress_verdict == "conditional":
            confidence_verdict = "moderate_confidence"
        else:
            confidence_verdict = "low_confidence"

        # ------------------------------------------------------------------
        # Post-synthesis hallucination check
        # ------------------------------------------------------------------
        verdict_text = result.get("verdict_paragraph", "")
        numbers_in_verdict = re.findall(r'\$[\d,.]+|\d+\.?\d*%', verdict_text)
        flagged = 0

        for num_str in numbers_in_verdict:
            try:
                val_num = float(num_str.replace('$', '').replace('%', '').replace(',', ''))
                if '%' in num_str:
                    val_num /= 100
                # Check if within 2% of any registry value
                matched = any(
                    abs(val_num - v) / max(abs(v), 0.001) < 0.02
                    for v in number_registry.values()
                    if v
                )
                if not matched:
                    flagged += 1
                    logger.warning("Potential hallucination in verdict: %s", num_str)
            except ValueError:
                pass

        overall_status: str
        if flagged == 0:
            overall_status = "clean"
        elif flagged <= 2:
            overall_status = "warnings"
        else:
            overall_status = "blocked"

        hallucination_check = {
            "validated_at": datetime.now(timezone.utc).isoformat(),
            "numbers_checked": len(numbers_in_verdict),
            "numbers_matched": len(numbers_in_verdict) - flagged,
            "numbers_flagged": flagged,
            "overall_status": overall_status,
        }

        # ------------------------------------------------------------------
        # Write to state
        # ------------------------------------------------------------------
        state["verdict_paragraph"] = result.get("verdict_paragraph")
        state["confidence_verdict"] = confidence_verdict  # deterministic override
        state["red_flags"] = result.get("red_flags", [])
        state["pm_synthesis"] = {
            "verdict_paragraph": result.get("verdict_paragraph"),
            "confidence_verdict": confidence_verdict,
            "hallucination_check": hallucination_check,
            "disclaimers": result.get("disclaimers", []),
            "number_registry": number_registry,
        }
        state["section_statuses"]["pm_synthesis"] = {
            "status": "ok",
            "source": "claude-sonnet-4-6" if settings.anthropic_api_key else "template",
            "cached": False,
            "ttl_remaining_s": None,
        }

    except Exception as e:
        logger.warning("pm_synthesis: node failed: %s", e)
        state.setdefault("section_statuses", {})["pm_synthesis"] = {
            "status": "failed",
            "source": None,
            "cached": False,
            "ttl_remaining_s": None,
        }

    return state
