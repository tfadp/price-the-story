# exceptions.md — Proactive Catches

## Format
- [DATE] | [FILE] | [WHAT WAS CAUGHT] | [RESOLUTION]

## Log

- 2026-03-24 | app/data/financial_datasets_client.py | httpx.AsyncClient missing `follow_redirects=True` — all 5 FD endpoints returned 301 Moved Permanently, crashing the classifier node. | Added `follow_redirects=True` to all 5 AsyncClient instantiations (get_company_facts, get_snapshot_price, get_income_statements, get_balance_sheets, get_cash_flow_statements).

- 2026-03-24 | app/data/yfinance_client.py | Two f-strings with no placeholders (ruff F541). | Removed extraneous `f` prefix from both string literals in the 429 error message inside get_ticker_info.

- 2026-03-24 | app/nodes/{fundamentals,valuation,analyst_estimates,macro,news_sentiment,filings_rag,themes,polymarket}.py | All 8 parallel LangGraph nodes returned the full state dict instead of a delta. LangGraph 0.2.x raises `InvalidUpdateError: At key 'ticker': Can receive only one value per step` when multiple parallel nodes each try to write the same shared key. Caused 2 out of 5 smoke tests to fail with HTTP 500. | Changed all 8 parallel nodes to return only their own output key(s) as a partial dict (delta), not the full state. Serial nodes (classifier, probability_engine, pm_synthesis) were not affected.

- 2026-03-25 | backend/app/state.py + all parallel nodes | Pre-existing LangGraph `InvalidUpdateError`: all 8 parallel nodes returned the full `state` dict including input keys (ticker, target_cagr, etc.), causing LangGraph to detect concurrent writes on keys that no node actually changed. Caught while running the Fix 6 test suite — happy-path tests returned 500. Resolution: (1) added `Annotated[dict, _merge_section_statuses]` reducer to `section_statuses` in state.py so parallel nodes can each contribute their subkey without conflict; (2) changed each parallel node's `return state` to return only the keys it actually wrote, as a partial dict. Serial nodes (classifier, probability_engine, pm_synthesis) left unchanged.

- 2026-03-25 | backend/app/main.py | `from __future__ import annotations` caused FastAPI to treat `body: AnalyzeRequest` as a query parameter instead of a request body, because the annotation became a forward-ref string and FastAPI 0.115.5 could not resolve it to a Pydantic model type for body detection. Caught when happy-path tests returned 422 with `loc: ['query', 'body']`. Resolution: removed `from __future__ import annotations` from main.py — the project targets Python 3.11+ so `float | None` union syntax works natively without the future import.

- 2026-03-25 | backend/app/nodes/valuation.py | Performance bottleneck: get_price_history("1y") for sentiment-premium check is called sequentially AFTER the DCF is complete, adding a serial 15-second network call to what could otherwise be an already-parallel node. No fix implemented — presented to user (Phase 3 of QA pass). Status: presented to user.

- 2026-03-25 | backend/app/nodes/fundamentals.py | Performance bottleneck: LLM instantiation (ChatAnthropic) is done inside the hot path on every request instead of being cached/reused. A new client object is constructed each time. No fix implemented — presented to user (Phase 3 of QA pass). Status: presented to user.

- 2026-03-25 | backend/app/data/financial_datasets_client.py | Performance bottleneck: each of get_income_statements, get_balance_sheets, and get_cash_flow_statements creates a fresh httpx.AsyncClient. Even when called via asyncio.gather they each pay connection-setup overhead. A shared/reused client would remove this. No fix implemented — presented to user (Phase 3 of QA pass). Status: presented to user.
