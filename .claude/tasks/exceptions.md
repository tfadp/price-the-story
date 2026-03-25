# exceptions.md — Proactive Catches

## Format
- [DATE] | [FILE] | [WHAT WAS CAUGHT] | [RESOLUTION]

## Log
- 2026-03-25 | backend/app/state.py + all parallel nodes | Pre-existing LangGraph `InvalidUpdateError`: all 8 parallel nodes returned the full `state` dict including input keys (ticker, target_cagr, etc.), causing LangGraph to detect concurrent writes on keys that no node actually changed. Caught while running the Fix 6 test suite — happy-path tests returned 500. Resolution: (1) added `Annotated[dict, _merge_section_statuses]` reducer to `section_statuses` in state.py so parallel nodes can each contribute their subkey without conflict; (2) changed each parallel node's `return state` to return only the keys it actually wrote, as a partial dict. Serial nodes (classifier, probability_engine, pm_synthesis) left unchanged.
- 2026-03-25 | backend/app/main.py | `from __future__ import annotations` caused FastAPI to treat `body: AnalyzeRequest` as a query parameter instead of a request body, because the annotation became a forward-ref string and FastAPI 0.115.5 could not resolve it to a Pydantic model type for body detection. Caught when happy-path tests returned 422 with `loc: ['query', 'body']`. Resolution: removed `from __future__ import annotations` from main.py — the project targets Python 3.11+ so `float | None` union syntax works natively without the future import.
