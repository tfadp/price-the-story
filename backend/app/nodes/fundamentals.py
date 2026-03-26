"""
Node 2: Fundamentals.

Fetches financial statements — Financial Datasets is tried first, yfinance
is the fallback. Computes derived metrics, factor scores, and generates a
business summary (via Claude Haiku if an API key is available, otherwise
a template string).

This node NEVER crashes the pipeline — all exceptions are caught,
logged, and a "failed" status is written to state.
"""
import asyncio
import logging
import math
from typing import Optional

from app.state import GraphState
from app.data.yfinance_client import get_financials, get_current_price
from app.data.financial_datasets_client import (
    get_income_statements,
    get_balance_sheets,
    get_cash_flow_statements,
    get_snapshot_price,
)

logger = logging.getLogger(__name__)


def _safe_float(val) -> Optional[float]:
    """Convert a value to float, returning None on any error."""
    try:
        if val is None:
            return None
        f = float(val)
        return None if math.isnan(f) or math.isinf(f) else f
    except (TypeError, ValueError):
        return None


def _extract_series(records: list[dict], field_name: str) -> list[Optional[float]]:
    """Extract a named field from a list of financial records (oldest first)."""
    values = []
    # Records come in newest-first from yfinance; we reverse to get oldest-first
    for row in reversed(records):
        # yfinance field names vary; try common variants
        val = row.get(field_name)
        if val is None:
            # Try title-case and lower-case variants
            for key in row:
                if key.lower().replace(" ", "_") == field_name.lower().replace(" ", "_"):
                    val = row[key]
                    break
        values.append(_safe_float(val))
    return values


def _find_field(row: dict, *candidates: str) -> Optional[float]:
    """Look up the first matching key (case-insensitive) from a dict row."""
    lower_row = {k.lower(): v for k, v in row.items()}
    for candidate in candidates:
        val = lower_row.get(candidate.lower())
        if val is not None:
            return _safe_float(val)
    return None


def _compute_cagr(values: list[Optional[float]]) -> Optional[float]:
    """Compute CAGR from a time series, using up to 5 years of data."""
    cleaned = [v for v in values if v is not None and v > 0]
    if len(cleaned) < 2:
        return None
    # Use up to 5 data points (oldest and newest)
    subset = cleaned[-5:] if len(cleaned) >= 5 else cleaned
    n = len(subset) - 1
    if n == 0:
        return None
    try:
        return (subset[-1] / subset[0]) ** (1 / n) - 1
    except (ZeroDivisionError, ValueError):
        return None


async def run(state: GraphState) -> dict:
    """Node 2: Fundamentals. Returns delta dict on success or failure.

    Returns only the keys this node writes so LangGraph parallel fan-out
    does not raise InvalidUpdateError when multiple nodes run concurrently.
    """
    ticker: str = state["ticker"]
    _section_statuses: dict = {}

    # Emit progress — signals parallel data phase has started
    callback = state.get("progress_callback")
    if callback is not None:
        await callback("Pulling financials", "fundamentals", 20)

    try:
        # ------------------------------------------------------------------
        # Fetch financial statements — Financial Datasets first, yfinance fallback
        # ------------------------------------------------------------------
        _fundamentals_source = "financial_datasets"
        try:
            fd_income, fd_balance, fd_cashflow = await asyncio.gather(
                get_income_statements(ticker),
                get_balance_sheets(ticker),
                get_cash_flow_statements(ticker),
            )
            # FD returns records newest-first; reverse once so oldest is index 0
            income_fd = list(reversed(fd_income))
            balance_fd = list(reversed(fd_balance))
            cashflow_fd = list(reversed(fd_cashflow))
            _use_fd = bool(income_fd or balance_fd or cashflow_fd)
        except Exception as fd_err:
            logger.warning("fundamentals: FD fetch failed, falling back to yfinance: %s", fd_err)
            _use_fd = False

        if _use_fd:
            # Build time series directly from FD snake_case field names
            revenues: list[Optional[float]] = [_safe_float(r.get("revenue")) for r in income_fd]
            gross_profits: list[Optional[float]] = [_safe_float(r.get("gross_profit")) for r in income_fd]
            operating_incomes: list[Optional[float]] = [_safe_float(r.get("operating_income")) for r in income_fd]
            net_incomes: list[Optional[float]] = [_safe_float(r.get("net_income")) for r in income_fd]
            # Prefer diluted EPS; eps field also acceptable
            eps_list: list[Optional[float]] = [
                _safe_float(r.get("eps_diluted") or r.get("eps")) for r in income_fd
            ]

            # FD provides free_cash_flow directly — no need to recompute from parts
            free_cash_flows: list[Optional[float]] = [
                _safe_float(r.get("free_cash_flow")) for r in cashflow_fd
            ]

            net_debts: list[Optional[float]] = []
            for bs_row in balance_fd:
                total_debt = _safe_float(bs_row.get("total_debt"))
                cash = _safe_float(bs_row.get("cash_and_equivalents"))
                if total_debt is not None and cash is not None:
                    net_debts.append(_safe_float(total_debt - cash))
                else:
                    net_debts.append(None)

            # ROIC: net_income / (total_equity + total_debt) — approximate
            roic_list: list[Optional[float]] = []
            for ni, bs_row in zip(net_incomes, balance_fd):
                equity = _safe_float(bs_row.get("total_equity"))
                ltd = _safe_float(bs_row.get("total_debt"))
                if ni is not None and equity is not None:
                    denom = (equity or 0) + (ltd or 0)
                    roic_list.append(_safe_float(ni / denom) if denom else None)
                else:
                    roic_list.append(None)
        else:
            # yfinance fallback — field names use Title Case (yfinance convention)
            _fundamentals_source = "yfinance"
            financials = await get_financials(ticker)
            income_records: list[dict] = financials.get("income_stmt", [])
            balance_records: list[dict] = financials.get("balance_sheet", [])
            cashflow_records: list[dict] = financials.get("cashflow", [])

            revenues = []
            gross_profits = []
            operating_incomes = []
            net_incomes = []
            eps_list = []

            # yfinance income statement field names vary by version
            for row in reversed(income_records):
                revenues.append(_find_field(row, "Total Revenue", "TotalRevenue", "Revenue"))
                gross_profits.append(_find_field(row, "Gross Profit", "GrossProfit"))
                operating_incomes.append(_find_field(row, "Operating Income", "OperatingIncome", "EBIT"))
                net_incomes.append(_find_field(row, "Net Income", "NetIncome", "Net Income Common Stockholders"))
                eps_list.append(_find_field(row, "Basic EPS", "Diluted EPS", "EPS", "BasicEPS", "DilutedEPS"))

            # Free cash flow: operating cash flow + capex (capex is negative in yfinance)
            free_cash_flows = []
            for cf_row in reversed(cashflow_records):
                op_cf = _find_field(cf_row, "Operating Cash Flow", "Cash From Operations", "OperatingCashFlow")
                capex = _find_field(cf_row, "Capital Expenditure", "CapEx", "CapitalExpenditure", "Purchase Of PPE")
                if op_cf is not None:
                    capex_val = capex or 0
                    free_cash_flows.append(_safe_float(op_cf + capex_val))
                else:
                    free_cash_flows.append(None)

            net_debts = []
            for bs_row in reversed(balance_records):
                total_debt = _find_field(bs_row, "Total Debt", "TotalDebt", "Long Term Debt And Capital Lease Obligation")
                cash = _find_field(bs_row, "Cash And Cash Equivalents", "Cash", "CashAndCashEquivalents")
                if total_debt is not None and cash is not None:
                    net_debts.append(_safe_float(total_debt - cash))
                else:
                    net_debts.append(None)

            # ROIC: net_income / (total_equity + long_term_debt) — approximate
            roic_list = []
            for ni, bs_row in zip(net_incomes, reversed(balance_records)):
                equity = _find_field(bs_row, "Stockholders Equity", "Total Stockholders Equity", "CommonStockEquity")
                ltd = _find_field(bs_row, "Long Term Debt", "LongTermDebt")
                if ni is not None and equity is not None:
                    denom = (equity or 0) + (ltd or 0)
                    roic_list.append(_safe_float(ni / denom) if denom else None)
                else:
                    roic_list.append(None)

        # ------------------------------------------------------------------
        # Derived per-year margin metrics (same formula regardless of source)
        # ------------------------------------------------------------------
        gross_margins: list[Optional[float]] = []
        operating_margins: list[Optional[float]] = []
        for rev, gp, oi in zip(revenues, gross_profits, operating_incomes):
            if rev and rev != 0:
                gross_margins.append(_safe_float((gp or 0) / rev) if gp is not None else None)
                operating_margins.append(_safe_float((oi or 0) / rev) if oi is not None else None)
            else:
                gross_margins.append(None)
                operating_margins.append(None)

        # ------------------------------------------------------------------
        # Factor scores (normalised 0–1)
        # ------------------------------------------------------------------
        ticker_meta: dict = state.get("ticker_meta") or {}
        pe_ratio = _safe_float(ticker_meta.get("trailingPE") or ticker_meta.get("forwardPE"))

        # Value score: score = max(0, min(1, 1 - pe/30))
        value_score: Optional[float] = None
        if pe_ratio is not None and pe_ratio > 0:
            value_score = max(0.0, min(1.0, 1 - pe_ratio / 30))

        # Quality score: avg operating margin over last 5 years, clipped to [0,1] / 0.25
        valid_op_margins = [m for m in operating_margins[-5:] if m is not None]
        quality_score: Optional[float] = None
        if valid_op_margins:
            avg_op_margin = sum(valid_op_margins) / len(valid_op_margins)
            quality_score = min(1.0, max(0.0, avg_op_margin / 0.25))

        # Growth score: 5yr revenue CAGR / 0.15, clipped to [0,1]
        revenue_cagr = _compute_cagr(revenues)
        growth_score: Optional[float] = None
        if revenue_cagr is not None:
            growth_score = min(1.0, max(0.0, revenue_cagr / 0.15))

        # ------------------------------------------------------------------
        # Current price — FD snapshot preferred, yfinance as fallback
        # ------------------------------------------------------------------
        try:
            current_price = await get_snapshot_price(ticker)
        except Exception:
            try:
                current_price = await get_current_price(ticker)
            except ValueError:
                current_price = _safe_float(
                    ticker_meta.get("regularMarketPrice") or ticker_meta.get("previousClose")
                )

        # ------------------------------------------------------------------
        # Business summary (LLM if key available, else template)
        # ------------------------------------------------------------------
        from app.config import settings

        recent_revenues = [r for r in revenues[-3:] if r is not None]
        recent_margins = [m for m in operating_margins[-3:] if m is not None]

        def _fmt_revenue(v: Optional[float]) -> str:
            if v is None:
                return "N/A"
            if abs(v) >= 1e9:
                return f"${v/1e9:.1f}B"
            if abs(v) >= 1e6:
                return f"${v/1e6:.0f}M"
            return f"${v:,.0f}"

        segment = state.get("segment", "unknown")

        business_summary: str
        if settings.anthropic_api_key:
            try:
                from langchain_anthropic import ChatAnthropic
                from langchain_core.messages import HumanMessage

                llm = ChatAnthropic(
                    model="claude-haiku-4-5-20251001",
                    api_key=settings.anthropic_api_key,
                    max_tokens=256,
                )
                prompt = (
                    f"In 2-3 sentences, describe {ticker}'s business model based on: "
                    f"Revenue trend (most recent 3yr): {[_fmt_revenue(r) for r in recent_revenues]}. "
                    f"Gross margin trend: {[f'{m*100:.1f}%' if m else 'N/A' for m in recent_margins]}. "
                    "Only use the data provided. Do not invent figures."
                )
                response = await llm.ainvoke([HumanMessage(content=prompt)])
                business_summary = str(response.content).strip()
            except Exception as e:
                logger.warning("fundamentals: LLM business_summary failed: %s", e)
                business_summary = _template_summary(ticker, segment, recent_revenues, recent_margins)
        else:
            business_summary = _template_summary(ticker, segment, recent_revenues, recent_margins)

        # ------------------------------------------------------------------
        # Key drivers
        # ------------------------------------------------------------------
        key_drivers: list[dict] = []

        if revenue_cagr is not None:
            if revenue_cagr > 0.10:
                key_drivers.append({
                    "driver": "Revenue growth",
                    "direction": "positive",
                    "importance": "high",
                })

        # Margin trend: compare first half vs second half
        if len(operating_margins) >= 4:
            early = [m for m in operating_margins[: len(operating_margins) // 2] if m is not None]
            late = [m for m in operating_margins[len(operating_margins) // 2:] if m is not None]
            if early and late:
                if sum(late) / len(late) > sum(early) / len(early) + 0.02:
                    key_drivers.append({
                        "driver": "Margin expansion",
                        "direction": "positive",
                        "importance": "high",
                    })
                elif sum(late) / len(late) < sum(early) / len(early) - 0.02:
                    key_drivers.append({
                        "driver": "Margin compression",
                        "direction": "negative",
                        "importance": "high",
                    })

        # Balance sheet leverage — extract equity from the correct source's rows
        recent_net_debts = [d for d in net_debts[-3:] if d is not None]
        recent_equities: list[Optional[float]] = []
        if _use_fd:
            for bs_row in balance_fd[-3:]:
                recent_equities.append(_safe_float(bs_row.get("total_equity")))
        else:
            for bs_row in reversed(balance_records[-3:]):
                eq = _find_field(bs_row, "Stockholders Equity", "Total Stockholders Equity", "CommonStockEquity")
                recent_equities.append(eq)
        valid_equities = [e for e in recent_equities if e is not None and e > 0]
        if recent_net_debts and valid_equities:
            avg_net_debt = sum(recent_net_debts) / len(recent_net_debts)
            avg_equity = sum(valid_equities) / len(valid_equities)
            if avg_net_debt > avg_equity * 1.5:
                key_drivers.append({
                    "driver": "Balance sheet leverage",
                    "direction": "negative",
                    "importance": "medium",
                })

        # ------------------------------------------------------------------
        # Build delta — only keys this node owns
        # ------------------------------------------------------------------
        _section_statuses["fundamentals"] = {
            "status": "ok",
            "source": _fundamentals_source,
            "cached": False,
            "ttl_remaining_s": None,
        }
        return {
            "fundamentals": {
                "thesis": {
                    "business_summary": business_summary,
                    "key_drivers": key_drivers,
                    "long_term_themes": [],
                    "growth_bet": None,
                },
                "time_series": {
                    "revenue": revenues,
                    "gross_profit": gross_profits,
                    "operating_income": operating_incomes,
                    "net_income": net_incomes,
                    "eps": eps_list,
                    "gross_margin": gross_margins,
                    "operating_margin": operating_margins,
                    "free_cash_flow": free_cash_flows,
                    "net_debt": net_debts,
                    "roic": roic_list,
                },
                "factor_scores": {
                    "value_score": value_score,
                    "quality_score": quality_score,
                    "growth_score": growth_score,
                },
                "current_price": current_price,
            },
        }

    except Exception as e:
        logger.warning("fundamentals: node failed for %s: %s", ticker, e)
        return {"fundamentals": None}


def _template_summary(
    ticker: str,
    segment: str,
    recent_revenues: list,
    recent_margins: list,
) -> str:
    """Generate a template business summary when no LLM is available."""
    rev_str = f"${recent_revenues[-1]/1e9:.1f}B" if recent_revenues else "N/A"
    margin_str = f"{recent_margins[-1]*100:.1f}%" if recent_margins else "N/A"
    return (
        f"{ticker} is a {segment.replace('_', ' ')} company with {rev_str} "
        f"in trailing twelve-month revenue and {margin_str} operating margins."
    )
