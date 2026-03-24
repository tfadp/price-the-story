"""
FastAPI application for Price the Story.
POST /analyze-ticker         — full analysis, returns AnalyzeResponse JSON
GET  /analyze-ticker/stream  — SSE stream of progress events
GET  /health                 — health check
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
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
    Analysts,
    MacroAndCrowd,
    ProbabilityEngine,
    StressTest,
    RedFlag,
)
from app.graph import graph

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Price the Story API v0.1.0 starting")
    yield


app = FastAPI(
    title="Price the Story",
    description="Long-horizon equity research assistant",
    version="0.1.0",
    lifespan=lifespan,
)

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
async def analyze_ticker(request: AnalyzeRequest) -> AnalyzeResponse:
    state = _build_initial_state(request)
    try:
        result = await graph.ainvoke(state)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.exception("Pipeline failed for %s", request.ticker)
        raise HTTPException(status_code=500, detail=str(e))
    return _state_to_response(result, request)


@app.get("/analyze-ticker/stream")
async def analyze_ticker_stream(
    ticker: str = Query(...),
    target_cagr: float = Query(default=0.10),
    entry_price: float | None = Query(default=None),
    holding_period_years: int = Query(default=5),
    force_refresh: bool = Query(default=False),
) -> EventSourceResponse:
    async def event_generator():
        progress_queue: asyncio.Queue = asyncio.Queue()

        async def progress_callback(stage: str, node: str, pct: int) -> None:
            await progress_queue.put(
                ProgressEvent(stage=stage, message=stage, node=node, progress_pct=pct)
            )

        request = AnalyzeRequest(
            ticker=ticker,
            target_cagr=target_cagr,
            entry_price=entry_price,
            horizons=[1, holding_period_years, 5, 10],
            force_refresh=force_refresh,
        )
        state = _build_initial_state(request)
        state["progress_callback"] = progress_callback

        task = asyncio.create_task(graph.ainvoke(state))

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
            yield {"event": "error", "data": f'{{"detail": "{task.exception()}"}}'}
        else:
            response = _state_to_response(task.result(), request)
            yield {"event": "complete", "data": response.model_dump_json()}

    return EventSourceResponse(event_generator())


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


def _state_to_response(state: dict, request: AnalyzeRequest) -> AnalyzeResponse:
    """Map LangGraph state dict to AnalyzeResponse Pydantic model."""
    synthesis = state.get("pm_synthesis") or {}
    prob = state.get("probability_engine") or {}
    stress = state.get("stress_test") or {}
    fund = state.get("fundamentals") or {}
    val = state.get("valuation") or {}
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
    )


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
