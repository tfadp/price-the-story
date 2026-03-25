"""
Node 4: Analyst Estimates.

Fetches analyst consensus data via yfinance and optionally generates a
short narrative via Claude Haiku.

NOTE: yfinance is the intentional primary source for this node.
Financial Datasets (financialdatasets.ai) does not provide analyst
recommendations, price targets, or earnings estimate revisions — the
data that this node is specifically responsible for. yfinance is not
a fallback here; it is the only source of this data in v1.

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
    """Node 4: Analyst Estimates. Returns delta dict on success or failure.

    Returns only the keys this node writes so LangGraph parallel fan-out
    does not raise InvalidUpdateError when multiple nodes run concurrently.
    """
    ticker: str = state["ticker"]

    try:
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
        # Analyst sentiment notes — Perplexity web search, then LLM, then template
        # ------------------------------------------------------------------
        from app.config import settings

        analyst_sentiment_notes: str
        perplexity_succeeded = False

        if settings.perplexity_api_key and (rating_summary or avg_target_price):
            try:
                import httpx as _httpx
                payload = {
                    "model": "sonar",
                    "messages": [
                        {
                            "role": "user",
                            "content": (
                                f"In exactly 2 sentences, summarise the current Wall Street analyst "
                                f"consensus for {ticker} stock. Mention the buy/hold/sell breakdown, "
                                f"the average price target, and any notable recent revision trends. "
                                f"Use only data from reputable financial sources. Be factual and concise."
                            ),
                        }
                    ],
                    "max_tokens": 120,
                    "temperature": 0.1,
                    "return_citations": False,
                }
                async with _httpx.AsyncClient(timeout=10) as client:
                    resp = await client.post(
                        "https://api.perplexity.ai/chat/completions",
                        headers={
                            "Authorization": f"Bearer {settings.perplexity_api_key}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    )
                    resp.raise_for_status()
                    pdata = resp.json()
                    analyst_sentiment_notes = pdata["choices"][0]["message"]["content"].strip()
                    perplexity_succeeded = True
                    logger.info("analyst_estimates: Perplexity narrative succeeded for %s", ticker)
            except Exception as e:
                logger.warning("analyst_estimates: Perplexity narrative failed for %s: %s", ticker, e)

        if not perplexity_succeeded:
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

    except Exception as e:
        logger.warning("analyst_estimates: node failed for %s: %s", ticker, e)
        return {
            "analyst_estimates": {
                "coverage_level": "low",
                "analyst_sentiment_notes": "Analyst data unavailable.",
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
