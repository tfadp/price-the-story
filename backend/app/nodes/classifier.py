"""
Node 1: Ticker Classifier.

This is the ONLY node that hard-fails. If the ticker is not a US equity,
we raise ValueError immediately — the rest of the pipeline should not run.
"""
import asyncio
import logging
import math

from app.state import GraphState
from app.data.alpha_vantage_client import get_market_cap, get_ticker_info
from app.data.yfinance_client import get_price_history, get_current_price
from app.data.financial_datasets_client import get_company_facts, get_snapshot_price
from app.utils import safe_float

logger = logging.getLogger(__name__)

# Exchanges we consider "US-based" for v1.
# Includes both yfinance short codes and the full strings returned by Financial Datasets.
_US_EXCHANGES = {
    "NMS", "NYQ", "NGM", "ASE", "PCX", "BTS", "NAS",
    "NASDAQ", "NYSE", "NYSE MKT", "NYSE ARCA",
}

# Max wall-clock time for the entire classifier node.
# Must be longer than get_ticker_info's retry window (2 attempts × ~8s each = ~20s).
_NODE_TIMEOUT_S = 30


async def _classify(state: GraphState) -> GraphState:
    """Inner implementation — wrapped in asyncio.wait_for by run()."""
    ticker: str = state["ticker"]

    # Step 1: Fetch ticker info — hard fail if the ticker does not exist.
    # Try Financial Datasets first; fall back to yfinance if FD is unavailable.
    info: dict
    current_price: float
    _source = "financial_datasets"

    try:
        facts = await get_company_facts(ticker)
        current_price = await get_snapshot_price(ticker)
        # FD only covers equities — treat a successful response as quoteType=EQUITY
        info = {
            "quoteType": "EQUITY",
            "exchange": facts.get("exchange", ""),
            "marketCap": facts.get("market_cap"),
            "regularMarketPrice": current_price,
            # FD does not provide volume; avg_vol will default to 0 below
            "averageDailyVolume10Day": None,
            "regularMarketVolume": None,
            "previousClose": None,
            "shortName": facts.get("name", ticker),
            "longName": facts.get("name", ticker),
            # Preserve FD-specific fields for downstream nodes
            "_fd_facts": facts,
        }
    except Exception as fd_error:
        # A 404 from FD means the ticker genuinely does not exist — hard fail
        if "not found" in str(fd_error).lower() or "404" in str(fd_error):
            raise
        # Any other FD error (timeout, rate limit, etc.) — fall back to Alpha Vantage
        logger.warning(
            "classifier: Financial Datasets unavailable, falling back to Alpha Vantage: %s",
            fd_error,
        )
        _source = "alpha_vantage"
        info = await get_ticker_info(ticker)
        current_price = (
            info.get("regularMarketPrice") or info.get("previousClose") or 0
        )

    # Step 1b: Supplement missing market_cap / volume from Alpha Vantage when FD path was used.
    # FD never returns volume and often omits market_cap for large caps.
    market_cap_raw: float = safe_float(info.get("marketCap")) or 0.0

    if _source == "financial_datasets" and market_cap_raw == 0:
        # Single OVERVIEW call — avoids AV's 1 req/sec limit that fires
        # when OVERVIEW + GLOBAL_QUOTE are requested in parallel.
        supplemented = await get_market_cap(ticker)
        if supplemented:
            info["marketCap"] = supplemented
            logger.info("classifier: supplemented market_cap=%s from AV for %s", supplemented, ticker)

    # Step 2: Must be an equity
    quote_type = info.get("quoteType")
    if quote_type != "EQUITY":
        raise ValueError(
            f"unsupported_ticker: {ticker} is not an equity (quoteType={quote_type!r})"
        )

    # Step 3: Must be on a US exchange
    exchange = info.get("exchange", "")
    if exchange not in _US_EXCHANGES:
        raise ValueError(
            "unsupported_ticker: International tickers are not supported in v1."
        )

    # Step 4: Gather market data for classification
    market_cap: float = safe_float(info.get("marketCap")) or 0.0
    avg_vol: float = safe_float(
        info.get("averageDailyVolume10Day")
        or info.get("regularMarketVolume")
    ) or 0.0

    # If FD gave us the current price above, we already have it.
    # For the AV fallback path, try a fresh fetch to be consistent.
    if _source != "financial_datasets":
        try:
            current_price = await get_current_price(ticker)
        except Exception:
            current_price = info.get("regularMarketPrice") or info.get("previousClose") or 0

    # Annualised volatility + history-derived avg daily volume from 10yr weekly data.
    # We compute both in one pass since the history fetch is the expensive part.
    annualized_vol: float = 0.0
    # Initialized before the try so Step 7 can always read it (empty list on failure).
    history_data: dict = {}
    try:
        history_data = await get_price_history(ticker, period="10y")
        history = history_data.get("history", [])
        closes = [row["close"] for row in history if row["close"]]
        if len(closes) >= 20:
            import statistics

            log_returns = [
                math.log(closes[i] / closes[i - 1])
                for i in range(1, len(closes))
                if closes[i - 1] > 0
            ]
            daily_std = statistics.stdev(log_returns)
            annualized_vol = daily_std * math.sqrt(252)

        # Derive avg daily volume from last 52 weekly bars (≈1 year).
        # Weekly volume ÷ 5 approximates average daily volume.
        # Only used when the API didn't supply a usable volume figure.
        if avg_vol == 0:
            recent_weekly_vols = [
                row["volume"] for row in history[-52:] if row.get("volume", 0) > 0
            ]
            if recent_weekly_vols:
                avg_vol = (sum(recent_weekly_vols) / len(recent_weekly_vols)) / 5
    except Exception as e:
        logger.warning("classifier: could not compute annualized vol for %s: %s", ticker, e)

    # Step 4 (cont): Segment classification
    dollar_volume = avg_vol * current_price

    has_market_cap = market_cap > 0
    has_volume = avg_vol > 0

    # Safety net: mega-caps are always liquid regardless of measured volume.
    # Protects against misclassification when price history is unavailable.
    if market_cap > 200e9:
        segment = "large_cap_blue_chip"
    elif market_cap > 50e9 and dollar_volume > 500e6:
        segment = "large_cap_blue_chip"
    elif 2e9 <= market_cap <= 50e9:
        segment = "mid_cap"
    elif has_market_cap and market_cap < 2e9:
        segment = "small_cap_high_vol"
    elif has_market_cap and market_cap <= 5e9 and annualized_vol > 0.60:
        segment = "small_cap_high_vol"
    else:
        segment = "other"

    # Step 5: Confidence
    if has_market_cap and has_volume:
        segment_confidence = "high"
    elif has_market_cap or has_volume:
        segment_confidence = "medium"
    else:
        segment_confidence = "low"

    # Step 6: Data quality
    data_quality_map = {
        "large_cap_blue_chip": "high",
        "mid_cap": "medium",
        "small_cap_high_vol": "low",
        "other": "medium",
    }
    data_quality = data_quality_map[segment]

    # Step 7: Write to state
    state["segment"] = segment
    state["segment_confidence"] = segment_confidence
    state["data_quality"] = data_quality
    state["is_us_equity"] = True
    info["_classification_debug"] = {
        "market_cap": market_cap,
        "avg_daily_volume": avg_vol,
        "dollar_volume": dollar_volume,
        "annualized_volatility": annualized_vol,
        "source": _source,
    }
    state["ticker_meta"] = info
    # Stash the 10yr history so downstream nodes (e.g. valuation) can reuse it
    # without making a second network call.
    state["price_history"] = history_data.get("history", [])

    # Step 8: Emit progress if callback provided
    callback = state.get("progress_callback")
    if callback is not None:
        await callback("Pulling financials", "classifier", 5)

    # Step 9: Update section status — record which source actually served the data
    state.setdefault("section_statuses", {})["classifier"] = {
        "status": "ok",
        "source": _source,
        "cached": False,
        "ttl_remaining_s": None,
    }

    return state


async def run(state: GraphState) -> GraphState:
    """Node 1: Ticker Classifier. HARD FAIL on unsupported ticker."""
    try:
        return await asyncio.wait_for(_classify(state), timeout=_NODE_TIMEOUT_S)
    except asyncio.TimeoutError:
        raise ValueError(f"Classifier timed out after {_NODE_TIMEOUT_S}s for {state.get('ticker')}")
    # ValueError propagates up — intentional hard fail
