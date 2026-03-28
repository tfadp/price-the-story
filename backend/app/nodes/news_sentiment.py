import logging
from app.state import GraphState
from app.data.yfinance_client import get_options_sentiment
from app.utils import safe_float

logger = logging.getLogger(__name__)


async def run(state: GraphState) -> dict:
    """Node 5: News & Sentiment.

    Returns only this node's delta so LangGraph parallel fan-out does not
    raise InvalidUpdateError when multiple nodes write to shared state keys.
    """
    ticker = state["ticker"]
    segment = state.get("segment")
    if segment not in {"large_cap_blue_chip", "mid_cap"}:
        return {
            "news_sentiment": None,
            "section_statuses": {
                "news_sentiment": {
                    "status": "partial",
                    "source": "skipped",
                    "cached": False,
                    "ttl_remaining_s": None,
                }
            },
        }

    current_price = safe_float((state.get("ticker_meta") or {}).get("regularMarketPrice")) or 0.0
    if current_price <= 0:
        return {
            "news_sentiment": None,
            "section_statuses": {
                "news_sentiment": {
                    "status": "partial",
                    "source": "missing_price",
                    "cached": False,
                    "ttl_remaining_s": None,
                }
            },
        }

    options = await get_options_sentiment(ticker, current_price)
    if not options:
        logger.info("news_sentiment: options unavailable for %s", ticker)
        return {
            "news_sentiment": None,
            "section_statuses": {
                "news_sentiment": {
                    "status": "partial",
                    "source": "yfinance",
                    "cached": False,
                    "ttl_remaining_s": None,
                }
            },
        }

    lean = options.get("lean")
    if lean == "bullish":
        thesis_alignment = "supports_thesis"
    elif lean == "bearish":
        thesis_alignment = "contradicts_thesis"
    else:
        thesis_alignment = "mixed"

    implied_move_pct = safe_float(options.get("implied_move_pct"))
    call_put_oi_ratio = safe_float(options.get("call_put_oi_ratio"))
    move_text = f"roughly a +/-{implied_move_pct * 100:.0f}% move" if implied_move_pct is not None else "a meaningful move"
    if call_put_oi_ratio is None:
        ratio_text = "Call and put activity look balanced near the current price"
    elif call_put_oi_ratio >= 1:
        ratio_text = f"Bullish call activity outweighs puts by {call_put_oi_ratio:.1f}:1 near the current price"
    else:
        ratio_text = f"Put activity outweighs calls by {(1 / max(call_put_oi_ratio, 0.01)):.1f}:1 near the current price"

    alignment_text = {
        "supports_thesis": "This is consistent with our base case.",
        "mixed": "This sends a mixed signal versus our base case.",
        "contradicts_thesis": "This leans against our base case.",
    }[thesis_alignment]

    return {
        "news_sentiment": {
            "options_sentiment": {
                **options,
                "thesis_alignment": thesis_alignment,
                "summary": (
                    f"The options market is pricing in {move_text} over the next "
                    f"{round(options.get('days_to_expiry', 0) / 30)} months. {ratio_text}, suggesting traders lean toward "
                    f"{lean or 'neutral'} positioning. {alignment_text}"
                ),
            }
        },
        "section_statuses": {
            "news_sentiment": {
                "status": "ok",
                "source": "yfinance",
                "cached": False,
                "ttl_remaining_s": None,
            }
        },
    }
