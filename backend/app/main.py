"""
FastAPI application for Price the Story.
POST /analyze-ticker         — full analysis, returns AnalyzeResponse JSON
GET  /analyze-ticker/stream  — SSE stream of progress events
GET  /health                 — health check
"""
import asyncio
import hashlib
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone

from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sse_starlette.sse import EventSourceResponse

from app.models import (
    AnalyzeRequest,
    AnalyzeResponse,
    HealthResponse,
    ProgressEvent,
    HallucinationCheck,
    SectionStatusDetail,
    Thesis,
    Valuation,
    Sentiment,
    Analysts,
    MacroAndCrowd,
    ProbabilityEngine,
    StressTest,
    RedFlag,
    PredictionRecord,
    LeaderboardRow,
    ScoreRequest,
)
from app.db.predictions import (
    init_db as _init_db,
    log_prediction,
    get_all_predictions,
    get_prediction,
    score_prediction,
    get_due_predictions,
)
from app.data.yfinance_client import get_current_price
from app.config import settings
from app.graph import graph

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _rate_limit_key(request: Request) -> str:
    """Use the first forwarded IP when available, else fall back to client host."""
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        first_ip = forwarded_for.split(",")[0].strip()
        if first_ip:
            return first_ip
    return request.client.host if request.client else "unknown"


limiter = Limiter(key_func=_rate_limit_key, default_limits=["5/minute"])
analysis_semaphore = asyncio.Semaphore(max(1, settings.max_concurrent_analyses))
analysis_cache: dict[str, tuple[float, AnalyzeResponse]] = {}
inflight_analyses: dict[str, asyncio.Future] = {}
analysis_cache_lock = asyncio.Lock()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Price the Story API v0.1.0 starting")
    await asyncio.to_thread(_init_db)
    yield


app = FastAPI(
    title="Price the Story",
    description="Long-horizon equity research assistant",
    version="0.1.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse()


@app.post("/analyze-ticker", response_model=AnalyzeResponse)
@limiter.limit("5/minute")
async def analyze_ticker(request: Request, body: AnalyzeRequest) -> AnalyzeResponse:
    _require_api_key(request)
    return await _run_analysis(body)


@app.get("/analyze-ticker/stream")
@limiter.limit("5/minute")
async def analyze_ticker_stream(
    request: Request,
    ticker: str = Query(...),
    target_cagr: float = Query(default=0.10),
    entry_price: float | None = Query(default=None),
    holding_period_years: int = Query(default=5),
    force_refresh: bool = Query(default=False),
) -> EventSourceResponse:
    _require_api_key(request)

    async def event_generator():
        progress_queue: asyncio.Queue = asyncio.Queue()

        async def progress_callback(stage: str, node: str, pct: int) -> None:
            await progress_queue.put(
                ProgressEvent(stage=stage, message=stage, node=node, progress_pct=pct)
            )

        req = AnalyzeRequest(
            ticker=ticker,
            target_cagr=target_cagr,
            entry_price=entry_price,
            horizons=[1, holding_period_years, 5, 10],
            force_refresh=force_refresh,
        )
        cached_response = None if req.force_refresh else await _get_cached_analysis(req)
        if cached_response is not None:
            yield {"event": "complete", "data": cached_response.model_dump_json()}
            return

        task = asyncio.create_task(_run_analysis(req, progress_callback=progress_callback, use_cache=True))

        try:
            while not task.done():
                try:
                    event = await asyncio.wait_for(progress_queue.get(), timeout=1.0)
                    yield {"event": "progress", "data": event.model_dump_json()}
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": "{}"}

            while not progress_queue.empty():
                event = progress_queue.get_nowait()
                yield {"event": "progress", "data": event.model_dump_json()}

            if task.exception():
                logger.error("SSE pipeline failed: %s", task.exception())
                yield {"event": "error", "data": '{"detail": "Analysis failed. Please try again."}'}
            else:
                yield {"event": "complete", "data": task.result().model_dump_json()}
        finally:
            if not task.done():
                task.cancel()
                logger.info("SSE task cancelled (client disconnected) for ticker=%s", ticker)

    return EventSourceResponse(event_generator())


# ---------------------------------------------------------------------------
# Prediction Ledger endpoints (Phase A)
# ---------------------------------------------------------------------------

def _compute_leaderboard_status(
    row: dict,
    current_price: Optional[float],
) -> dict:
    """Enrich a raw DB row with live market data and status classification."""
    entry_price = row.get("entry_price") or 0.0
    target_cagr = row.get("target_cagr") or 0.10

    # Already scored — outcome is final
    outcome = row.get("outcome_1yr")
    if isinstance(outcome, dict) and outcome.get("outcome"):
        return {
            "current_price": current_price,
            "ytd_growth": None,
            "required_by_year_end": None,
            "status": outcome["outcome"],  # hit | miss
            "days_remaining": 0,
        }

    if not current_price or entry_price <= 0:
        return {"current_price": current_price, "ytd_growth": None,
                "required_by_year_end": None, "status": None, "days_remaining": None}

    ytd_growth = (current_price - entry_price) / entry_price

    run_at = datetime.fromisoformat(row["run_at"])
    now = datetime.now(timezone.utc)
    days_elapsed = max((now - run_at).days, 0)
    horizon_1yr = date.fromisoformat(row["horizon_1yr_date"])
    days_remaining = max((horizon_1yr - date.today()).days, 0)

    # Time-weighted required pace: what % should you have by today
    time_frac = days_elapsed / 365.25
    time_weighted_required = (1 + target_cagr) ** time_frac - 1

    # Remaining return needed to finish the year at target pace
    required_by_year_end = ((1 + target_cagr) / (1 + ytd_growth)) - 1 if ytd_growth > -1 else None

    if time_weighted_required <= 0:
        status = "on_track"
    else:
        ratio = ytd_growth / time_weighted_required
        if ratio >= 0.80:
            status = "on_track"
        elif ratio >= 0.50:
            status = "at_risk"
        else:
            status = "off_track"

    return {
        "current_price": current_price,
        "ytd_growth": round(ytd_growth, 4),
        "required_by_year_end": round(required_by_year_end, 4) if required_by_year_end is not None else None,
        "status": status,
        "days_remaining": days_remaining,
    }


@app.get("/predictions/leaderboard", response_model=list[LeaderboardRow])
async def predictions_leaderboard() -> list[LeaderboardRow]:
    """All predictions enriched with live price, YTD growth, and status."""
    rows = await asyncio.to_thread(get_all_predictions)
    if not rows:
        return []

    # Fetch live prices for unique tickers concurrently
    tickers = list({r["ticker"] for r in rows})
    prices_list = await asyncio.gather(
        *[get_current_price(t) for t in tickers], return_exceptions=True
    )
    price_map: dict[str, Optional[float]] = {}
    for ticker, result in zip(tickers, prices_list):
        price_map[ticker] = result if isinstance(result, float) else None

    leaderboard = []
    for row in rows:
        live = _compute_leaderboard_status(row, price_map.get(row["ticker"]))
        leaderboard.append(LeaderboardRow(**{**row, **live}))
    return leaderboard


@app.get("/predictions/due", response_model=list[PredictionRecord])
async def predictions_due() -> list[PredictionRecord]:
    """Predictions with 1yr horizon within 14 days that haven't been scored yet."""
    rows = await asyncio.to_thread(get_due_predictions)
    return [PredictionRecord(**r) for r in rows]


@app.get("/predictions", response_model=list[PredictionRecord])
async def predictions_list(
    ticker: Optional[str] = Query(default=None),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
) -> list[PredictionRecord]:
    """All raw prediction records. Filterable by ticker and date range."""
    rows = await asyncio.to_thread(get_all_predictions, ticker, date_from, date_to)
    return [PredictionRecord(**r) for r in rows]


@app.get("/predictions/{prediction_id}", response_model=PredictionRecord)
async def predictions_get(prediction_id: str) -> PredictionRecord:
    """Single prediction record by ID."""
    row = await asyncio.to_thread(get_prediction, prediction_id)
    if not row:
        raise HTTPException(status_code=404, detail="Prediction not found")
    return PredictionRecord(**row)


@app.post("/predictions/{prediction_id}/score", response_model=PredictionRecord)
async def predictions_score(prediction_id: str, body: ScoreRequest) -> PredictionRecord:
    """Submit a grading outcome for a prediction."""
    updated = await asyncio.to_thread(
        score_prediction,
        prediction_id,
        body.realized_price,
        body.thesis_played_out,
        body.notes,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Prediction not found")
    return PredictionRecord(**updated)


def _build_prediction_dict(state: dict, request: AnalyzeRequest) -> dict:
    """Extract all fields needed for the prediction ledger from final pipeline state."""
    prob = state.get("probability_engine") or {}
    val = state.get("valuation") or {}

    # Find probability band at the user's holding period horizon
    horizons = request.horizons or [1, 3, 5, 10]
    holding_period = 5 if 5 in horizons else horizons[-1]
    prob_low = None
    prob_high = None
    for h in (prob.get("horizons") or []):
        if isinstance(h, dict) and h.get("years") == holding_period:
            prob_low = h.get("prob_ge_target_low")
            prob_high = h.get("prob_ge_target_high")
            break

    # Which nodes had real data (not stubs or failures)
    nodes_with_data = [
        k for k, v in state.get("section_statuses", {}).items()
        if isinstance(v, dict) and v.get("status") == "ok"
    ]

    pea = val.get("price_efficiency_assessment") or {}
    efficiency_verdict = pea.get("efficiency_verdict") if isinstance(pea, dict) else None

    run_at = datetime.now(timezone.utc)
    horizon_1yr_date = (run_at.date() + timedelta(days=365)).isoformat()

    return {
        "prediction_id": str(uuid.uuid4()),
        "ticker": state["ticker"],
        "run_at": run_at.isoformat(),
        "entry_price": val.get("current_price") or 0.0,
        "target_cagr": request.target_cagr,
        "holding_period_years": holding_period,
        "horizon_1yr_date": horizon_1yr_date,
        "prob_low": prob_low,
        "prob_high": prob_high,
        "confidence_verdict": state.get("confidence_verdict"),
        "verdict_paragraph": state.get("verdict_paragraph"),
        "fair_value_base": val.get("fair_value_base"),
        "macro_regime": (state.get("macro") or {}).get("macro_regime"),
        "segment": state.get("segment"),
        "nodes_with_data": json.dumps(nodes_with_data),
        "outcome_1yr": None,
        "outcome_notes": None,
        "stated_bet": None,
        "words_vs_numbers": None,
        "efficiency_verdict": efficiency_verdict,
    }


def _build_initial_state(request: AnalyzeRequest) -> dict:
    return {
        "ticker": request.ticker.upper().strip(),
        "target_cagr": request.target_cagr,
        "entry_price": request.entry_price,
        "horizons": request.horizons,
        "force_refresh": request.force_refresh,
        "debug": request.debug,
        "section_statuses": {},
        "errors": [],
        "red_flags": [],
        "progress_callback": None,
    }


def _require_api_key(request: Request) -> None:
    """Require the API key when INTERNAL_API_KEY is configured.

    Accepts the key from either:
    - x-api-key request header (used by fetch/POST)
    - x_api_key query parameter (used by EventSource, which cannot send headers)
    """
    if not settings.internal_api_key:
        return
    provided = (
        request.headers.get("x-api-key")
        or request.query_params.get("x_api_key")
        or ""
    )
    if provided != settings.internal_api_key:
        raise HTTPException(status_code=401, detail="Unauthorized")


def _analysis_cache_key(request: AnalyzeRequest) -> str:
    payload = request.model_dump(mode="json")
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


async def _get_cached_analysis(request: AnalyzeRequest) -> AnalyzeResponse | None:
    cache_key = _analysis_cache_key(request)
    now = time.monotonic()
    async with analysis_cache_lock:
        cached = analysis_cache.get(cache_key)
        if cached is None:
            return None
        expires_at, response = cached
        if expires_at <= now:
            analysis_cache.pop(cache_key, None)
            return None
        return response


async def _store_cached_analysis(request: AnalyzeRequest, response: AnalyzeResponse) -> None:
    cache_key = _analysis_cache_key(request)
    expires_at = time.monotonic() + max(1, settings.analysis_cache_ttl_s)
    async with analysis_cache_lock:
        analysis_cache[cache_key] = (expires_at, response)


async def _run_analysis(
    request: AnalyzeRequest,
    progress_callback=None,
    use_cache: bool = True,
) -> AnalyzeResponse:
    """Run or reuse an analysis with optional cache and in-flight deduplication."""
    if use_cache and not request.force_refresh:
        cached = await _get_cached_analysis(request)
        if cached is not None:
            return cached

    cache_key = _analysis_cache_key(request)
    waiter: asyncio.Future | None = None
    owner = False

    if progress_callback is None:
        async with analysis_cache_lock:
            waiter = inflight_analyses.get(cache_key)
            if waiter is None:
                waiter = asyncio.get_running_loop().create_future()
                inflight_analyses[cache_key] = waiter
                owner = True
        if not owner:
            return await waiter

    try:
        async with analysis_semaphore:
            state = _build_initial_state(request)
            state["progress_callback"] = progress_callback
            try:
                result = await graph.ainvoke(state)
            except ValueError as e:
                raise HTTPException(status_code=422, detail=str(e))
            except Exception:
                logger.exception("Pipeline failed for %s", request.ticker)
                raise HTTPException(status_code=500, detail="Analysis failed. Please try again.")
            response = _state_to_response(result, request)

        # Fire-and-forget — write prediction to SQLite without blocking the response
        try:
            pred = _build_prediction_dict(result, request)
            asyncio.create_task(asyncio.to_thread(log_prediction, pred))
        except Exception:
            logger.exception("Failed to build prediction dict for %s", request.ticker)

        if use_cache:
            await _store_cached_analysis(request, response)

        if owner and waiter is not None and not waiter.done():
            waiter.set_result(response)
        return response
    except Exception as exc:
        if owner and waiter is not None and not waiter.done():
            waiter.set_exception(exc)
            waiter.exception()
        raise
    finally:
        if owner:
            async with analysis_cache_lock:
                inflight_analyses.pop(cache_key, None)


def _state_to_response(state: dict, request: AnalyzeRequest) -> AnalyzeResponse:
    """Map LangGraph state dict to AnalyzeResponse Pydantic model."""
    synthesis = state.get("pm_synthesis") or {}
    prob = state.get("probability_engine") or {}
    stress = state.get("stress_test") or {}
    fund = state.get("fundamentals") or {}
    val = state.get("valuation") or {}
    sentiment_data = state.get("news_sentiment") or {}
    analysts_data = state.get("analyst_estimates") or {}
    macro_data = state.get("macro") or {}

    def safe_model(model_cls, data: dict):
        """Safely construct a Pydantic model from a dict, ignoring unknown fields."""
        if not data:
            return None
        try:
            return model_cls(**{k: v for k, v in data.items() if k in model_cls.model_fields})
        except Exception as e:
            logger.warning("Failed to construct %s: %s", model_cls.__name__, e)
            return None

    thesis_data = fund.get("thesis") if fund else None
    valuation_obj = safe_model(Valuation, val) if val else None
    sentiment_obj = safe_model(Sentiment, sentiment_data) if sentiment_data else None
    analysts_obj = safe_model(Analysts, analysts_data) if analysts_data else None
    macro_obj = safe_model(MacroAndCrowd, macro_data) if macro_data else None
    prob_obj = safe_model(ProbabilityEngine, prob) if prob else None
    stress_obj = safe_model(StressTest, stress) if stress else None

    red_flags = []
    for f in state.get("red_flags", []):
        try:
            red_flags.append(RedFlag(**f))
        except Exception:
            pass

    section_statuses = {}
    for k, v in state.get("section_statuses", {}).items():
        try:
            section_statuses[k] = SectionStatusDetail(**v)
        except Exception:
            pass

    hallucination_check = HallucinationCheck()
    if synthesis.get("hallucination_check"):
        try:
            hallucination_check = HallucinationCheck(**synthesis["hallucination_check"])
        except Exception:
            pass

    return AnalyzeResponse(
        ticker=state["ticker"],
        as_of=datetime.now(timezone.utc).isoformat(),
        segment=state.get("segment"),
        segment_confidence=state.get("segment_confidence"),
        data_quality=state.get("data_quality"),
        verdict_paragraph=state.get("verdict_paragraph"),
        confidence_verdict=state.get("confidence_verdict"),
        thesis=safe_model(Thesis, thesis_data) if thesis_data else None,
        valuation=valuation_obj,
        sentiment=sentiment_obj,
        analysts=analysts_obj,
        macro_and_crowd=macro_obj,
        probability_engine=prob_obj,
        stress_test=stress_obj,
        red_flags_and_failure_modes=red_flags,
        section_statuses=section_statuses,
        hallucination_check=hallucination_check,
        disclaimers=synthesis.get("disclaimers", [
            "This tool is for informational purposes only and does not constitute investment advice.",
            "Data sourced from public APIs. Always verify before acting.",
        ]),
        debug=(
            {
                "classifier": ((state.get("ticker_meta") or {}).get("_classification_debug")),
                "valuation": {
                    "confidence": val.get("valuation_confidence"),
                    "notes": val.get("valuation_notes"),
                    "base_growth_source": val.get("_base_growth_source"),
                },
                "probability_engine": {
                    "confidence_tier": prob.get("confidence_tier"),
                    "scenario_weights": prob.get("scenario_weights"),
                    "methodology_notes": prob.get("methodology_notes"),
                },
            }
            if request.debug
            else None
        ),
    )


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
