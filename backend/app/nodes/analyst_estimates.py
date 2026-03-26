"""
Node 4: Analyst Estimates.

Perplexity (web-search) is the PRIMARY source — returns buy/hold/sell counts,
price targets, and a narrative in one structured JSON call.
yfinance is the complete fallback if Perplexity is unavailable.

Never crashes the pipeline — all exceptions caught and logged.
"""
import logging
import math
from typing import Optional

from app.state import GraphState
from app.data.yfinance_client import get_analyst_data

logger = logging.getLogger(__name__)


def _safe_float(val) -> Optional[float]:
    try:
        if val is None:
            return None
        f = float(val)
        return None if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return None


async def run(state: GraphState) -> dict:
    """Node 4: Analyst Estimates.

    Perplexity (web-search) is the primary source — returns buy/hold/sell counts,
    price targets, and a narrative in one structured JSON call.
    yfinance is the complete fallback if Perplexity is unavailable.

    Returns delta dict on success or failure.
    """
    ticker: str = state["ticker"]

    try:
        from app.config import settings

        # ------------------------------------------------------------------
        # Path A: Perplexity — structured JSON + narrative in one call
        # ------------------------------------------------------------------
        if settings.perplexity_api_key:
            try:
                result = await _fetch_from_perplexity(ticker, settings.perplexity_api_key)
                if result:
                    return {"analyst_estimates": result}
            except Exception as e:
                logger.warning("analyst_estimates: Perplexity failed for %s: %s", ticker, e)

        # ------------------------------------------------------------------
        # Path B: yfinance fallback
        # ------------------------------------------------------------------
        return await _fetch_from_yfinance(ticker, settings)

    except Exception as e:
        logger.warning("analyst_estimates: node failed for %s: %s", ticker, e)
        return {
            "analyst_estimates": {
                "coverage_level": "low",
                "analyst_sentiment_notes": "Analyst data unavailable.",
            },
        }


async def _fetch_from_perplexity(ticker: str, api_key: str) -> Optional[dict]:
    """Fetch analyst data via Perplexity web search.

    Returns a fully-formed analyst_estimates dict, or None if the response
    cannot be parsed as valid JSON with required fields.
    """
    import json
    import httpx as _httpx

    prompt = (
        f"Search Yahoo Finance, MarketWatch, and similar sources for the CURRENT analyst "
        f"consensus on {ticker} stock. Return ONLY valid JSON — no markdown, no explanation:\n"
        f"{{\n"
        f'  "total_analysts": <integer, total number of analysts covering the stock>,\n'
        f'  "buy_count": <integer, number of Buy / Strong Buy / Outperform ratings>,\n'
        f'  "hold_count": <integer, number of Hold / Neutral / Market Perform ratings>,\n'
        f'  "sell_count": <integer, number of Sell / Underperform / Underweight ratings>,\n'
        f'  "avg_price_target": <float, mean analyst price target in USD>,\n'
        f'  "median_price_target": <float, median analyst price target in USD>,\n'
        f'  "top_analysts": [\n'
        f'    {{"firm": "<firm name>", "rating": "<rating>", "price_target": <float>}}\n'
        f'  ],\n'
        f'  "narrative": "<3-4 sentence summary of analyst consensus, key bulls/bears, recent target changes>"\n'
        f"}}"
    )

    async with _httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            "https://api.perplexity.ai/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "sonar",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 600,
                "temperature": 0.1,
            },
        )
        resp.raise_for_status()

    content = resp.json()["choices"][0]["message"]["content"].strip()

    # Strip markdown code fences if present
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    content = content.strip()

    data = json.loads(content)

    # Validate required fields
    buy_count = int(data.get("buy_count") or 0)
    hold_count = int(data.get("hold_count") or 0)
    sell_count = int(data.get("sell_count") or 0)
    total = buy_count + hold_count + sell_count

    avg_target = _safe_float(data.get("avg_price_target"))
    median_target = _safe_float(data.get("median_price_target"))
    narrative = str(data.get("narrative") or "").strip()
    top_analysts = data.get("top_analysts") or []

    if total == 0 and not narrative:
        return None  # Perplexity returned empty — fall through to yfinance

    coverage_level = "high" if total >= 10 else "medium" if total >= 3 else "low"

    rating_summary = {"buy": buy_count, "hold": hold_count, "sell": sell_count} if total > 0 else None

    tracked_analysts = []
    for a in top_analysts[:5]:
        firm = str(a.get("firm") or "")
        if firm:
            tracked_analysts.append({
                "analyst_id": firm.lower().replace(" ", "_"),
                "analyst_name": "Unknown",
                "firm": firm,
                "current_rating": str(a.get("rating") or ""),
                "current_price_target": _safe_float(a.get("price_target")),
                "accuracy_score": None,
                "graded_calls_count": 0,
            })

    logger.info(
        "analyst_estimates: Perplexity succeeded for %s — %d analysts, avg target $%s",
        ticker, total, avg_target,
    )

    return {
        "coverage_level": coverage_level,
        "consensus_growth_path": [],
        "revision_trend": None,
        "surprise_history": [],
        "rating_summary": rating_summary,
        "avg_price_target": avg_target,
        "weighted_target_price": median_target,
        "analyst_sentiment_notes": narrative,
        "tracked_analysts": tracked_analysts,
    }


async def _fetch_from_yfinance(ticker: str, settings) -> dict:
    """Fetch analyst data via yfinance (complete fallback path).

    Extracted from the original run() body — returns the same dict shape.
    """
    data = await get_analyst_data(ticker)

    if not data:
        return {
            "analyst_estimates": {
                "coverage_level": "low",
                "analyst_sentiment_notes": "Analyst data unavailable.",
            },
        }

    # ------------------------------------------------------------------
    # Consensus growth path from earnings_estimate / revenue_estimate
    # ------------------------------------------------------------------
    consensus_growth_path: list[dict] = []
    earnings_est: list[dict] = data.get("earnings_estimate", []) or []
    revenue_est: list[dict] = data.get("revenue_estimate", []) or []

    # Build a map: period_label → estimates
    period_map: dict[str, dict] = {}
    for row in earnings_est:
        period = str(row.get("period", row.get("0", "")))
        period_map.setdefault(period, {})["eps_estimate"] = _safe_float(
            row.get("avg") or row.get("Avg") or row.get("mean")
        )
    for row in revenue_est:
        period = str(row.get("period", row.get("0", "")))
        period_map.setdefault(period, {})["revenue_estimate"] = _safe_float(
            row.get("avg") or row.get("Avg") or row.get("mean")
        )

    # Convert period labels to approximate years
    from datetime import datetime
    current_year = datetime.now().year
    for i, (period, est) in enumerate(sorted(period_map.items())):
        year_val = current_year + i
        consensus_growth_path.append({
            "year": year_val,
            "eps_estimate": est.get("eps_estimate"),
            "revenue_estimate": est.get("revenue_estimate"),
        })

    # ------------------------------------------------------------------
    # Revision trend: compare current vs 3-month-ago EPS estimate
    # ------------------------------------------------------------------
    revision_trend: Optional[str] = None
    eps_trend: list[dict] = data.get("eps_trend", []) or []
    if eps_trend:
        # Look for current vs 3-month-ago fields
        for row in eps_trend:
            current_est = _safe_float(row.get("current") or row.get("0w") or row.get("current_estimate"))
            three_mo = _safe_float(row.get("3monthsago") or row.get("3m") or row.get("3_months_ago"))
            if current_est is not None and three_mo is not None and three_mo != 0:
                change = (current_est - three_mo) / abs(three_mo)
                if change > 0.02:
                    revision_trend = "up"
                elif change < -0.02:
                    revision_trend = "down"
                else:
                    revision_trend = "flat"
                break

    # ------------------------------------------------------------------
    # Surprise history from earnings_history (last 4 quarters)
    # ------------------------------------------------------------------
    surprise_history: list[dict] = []
    earnings_hist: list[dict] = data.get("earnings_history", []) or []
    for row in earnings_hist[-4:]:
        quarter = str(row.get("quarter", row.get("date", "N/A")))
        eps_surprise = _safe_float(row.get("surprisePercent") or row.get("epsSurprisePercent"))
        if eps_surprise is not None:
            surprise_history.append({
                "quarter": quarter,
                "eps_surprise_pct": round(eps_surprise * 100, 2) if abs(eps_surprise) < 10 else eps_surprise,
                "revenue_surprise_pct": None,
            })

    # ------------------------------------------------------------------
    # Rating summary — handle yfinance 0.2.x summary format AND legacy
    # ------------------------------------------------------------------
    buy_count = hold_count = sell_count = 0
    recommendations: list[dict] = data.get("recommendations", []) or []
    upgrades_downgrades: list[dict] = data.get("upgrades_downgrades", []) or []

    # yfinance 0.2.x: recommendations rows have strongBuy/buy/hold/sell/strongSell
    # Use the most recent period row (index 0 = current month)
    if recommendations and ("strongBuy" in recommendations[0] or "buy" in recommendations[0]):
        # Summary format — aggregate across all periods for robustness
        for row in recommendations:
            buy_count += int(row.get("strongBuy") or 0) + int(row.get("buy") or 0)
            hold_count += int(row.get("hold") or 0)
            sell_count += int(row.get("sell") or 0) + int(row.get("strongSell") or 0)
    elif upgrades_downgrades:
        # Use upgrades_downgrades for firm-level data (available in 0.2.x)
        recent = upgrades_downgrades[-90:] if len(upgrades_downgrades) > 90 else upgrades_downgrades
        for row in recent:
            grade = str(row.get("ToGrade") or row.get("To Grade") or row.get("toGrade") or "").lower()
            if any(t in grade for t in ("buy", "outperform", "overweight", "strong buy", "positive")):
                buy_count += 1
            elif any(t in grade for t in ("sell", "underperform", "underweight", "reduce", "negative")):
                sell_count += 1
            else:
                hold_count += 1
    else:
        # Legacy format fallback
        recent_recs = recommendations[-30:] if len(recommendations) > 30 else recommendations
        for row in recent_recs:
            grade = str(row.get("To Grade", row.get("toGrade", row.get("action", "")))).lower()
            if any(t in grade for t in ("buy", "outperform", "overweight", "strong buy", "positive")):
                buy_count += 1
            elif any(t in grade for t in ("sell", "underperform", "underweight", "reduce", "negative")):
                sell_count += 1
            else:
                hold_count += 1

    total_ratings = buy_count + hold_count + sell_count
    rating_summary = {
        "buy": buy_count,
        "hold": hold_count,
        "sell": sell_count,
    } if total_ratings > 0 else None

    # Coverage level
    if total_ratings >= 10:
        coverage_level = "high"
    elif total_ratings >= 3:
        coverage_level = "medium"
    else:
        coverage_level = "low"

    # ------------------------------------------------------------------
    # Average price target
    # ------------------------------------------------------------------
    avg_target_price: Optional[float] = None
    price_targets_raw = data.get("price_targets") or {}
    if isinstance(price_targets_raw, dict):
        avg_target_price = _safe_float(price_targets_raw.get("mean") or price_targets_raw.get("average"))
    elif isinstance(price_targets_raw, list) and price_targets_raw:
        targets = [_safe_float(r.get("priceTarget") or r.get("price_target")) for r in price_targets_raw]
        valid_targets = [t for t in targets if t is not None]
        if valid_targets:
            avg_target_price = sum(valid_targets) / len(valid_targets)

    # ------------------------------------------------------------------
    # Analyst sentiment notes — LLM if key available, else template
    # ------------------------------------------------------------------
    analyst_sentiment_notes: str

    if settings.anthropic_api_key and (rating_summary or avg_target_price):
        try:
            from langchain_anthropic import ChatAnthropic
            from langchain_core.messages import HumanMessage

            llm = ChatAnthropic(
                model="claude-haiku-4-5-20251001",
                api_key=settings.anthropic_api_key,
                max_tokens=150,
            )
            prompt = (
                f"In 2 sentences, summarise analyst sentiment for {ticker}. "
                f"Rating breakdown: buy={buy_count}, hold={hold_count}, sell={sell_count}. "
                f"Average price target: {f'${avg_target_price:.2f}' if avg_target_price else 'N/A'}. "
                f"Revision trend: {revision_trend or 'unknown'}. "
                "Be factual. Do not add information not in the data."
            )
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            analyst_sentiment_notes = str(response.content).strip()
        except Exception as e:
            logger.warning("analyst_estimates: LLM notes failed: %s", e)
            analyst_sentiment_notes = _template_notes(ticker, buy_count, hold_count, sell_count, avg_target_price, revision_trend)
    else:
        analyst_sentiment_notes = _template_notes(ticker, buy_count, hold_count, sell_count, avg_target_price, revision_trend)

    # ------------------------------------------------------------------
    # Tracked analysts — use upgrades_downgrades for firm-level history
    # ------------------------------------------------------------------
    tracked_analysts: list[dict] = []
    seen_firms: set = set()
    source_for_firms = upgrades_downgrades if upgrades_downgrades else recommendations
    for row in reversed(source_for_firms):
        firm = str(row.get("Firm") or row.get("firm") or "")
        if firm and firm not in seen_firms:
            seen_firms.add(firm)
            tracked_analysts.append({
                "analyst_id": firm.lower().replace(" ", "_"),
                "analyst_name": "Unknown",
                "firm": firm,
                "current_rating": str(row.get("ToGrade") or row.get("To Grade") or row.get("toGrade") or ""),
                "current_price_target": None,
                "accuracy_score": None,
                "graded_calls_count": 0,
            })
        if len(tracked_analysts) >= 5:
            break

    # ------------------------------------------------------------------
    # Return delta — only keys this node owns
    # ------------------------------------------------------------------
    return {
        "analyst_estimates": {
            "coverage_level": coverage_level,
            "consensus_growth_path": consensus_growth_path,
            "revision_trend": revision_trend,
            "surprise_history": surprise_history,
            "rating_summary": rating_summary,
            "avg_target_price": avg_target_price,
            "weighted_target_price": avg_target_price,
            "analyst_sentiment_notes": analyst_sentiment_notes,
            "tracked_analysts": tracked_analysts,
        },
    }


def _template_notes(
    ticker: str,
    buy: int,
    hold: int,
    sell: int,
    avg_target: Optional[float],
    revision_trend: Optional[str],
) -> str:
    total = buy + hold + sell
    if total == 0:
        return f"Analyst coverage for {ticker} is limited or unavailable."
    pct_buy = buy / total * 100
    target_str = f"${avg_target:.2f}" if avg_target else "N/A"
    trend_str = revision_trend or "stable"
    return (
        f"{ticker} has {total} analyst ratings with {pct_buy:.0f}% buy recommendations "
        f"and an average price target of {target_str}. "
        f"Estimate revisions have been trending {trend_str}."
    )
