# todo.md — Roadmap

## Session State
- branch: main
- last_test: 22/22 passed (2026-03-28)
- blocked: none
- pending_decisions:
  - Run live AAPL test — confirm `large_cap_blue_chip` + options sentiment panel shows
  - Analyst "limited or unavailable" may still appear if Perplexity throws silently — check backend logs
  - Review `equity-research-addendum.docx` (untracked in repo root — may contain Phase 2+ spec updates)

## Build Phases (from spec)
- [x] Phase 0 — Claude OS sidecar, skeleton, contracts
- [x] Phase 1 — Backend: nodes 1-4, 10-11, FastAPI
- [x] Phase 1 — Frontend: Next.js, VerdictCard, InputForm, ProgressRail
- [x] Phase 1 hardening — rate limiting, input validation, error handling, SSE progress
- [x] Phase 1 data layer — Financial Datasets (primary), Alpha Vantage (market cap supplement), yfinance (price history + analyst), Perplexity (analyst estimates primary)
- [x] Phase 1 perf — eliminated redundant network calls, LLM singletons, httpx pooling, safe_float dedup
- [x] Phase 1+ — Monte Carlo probability engine, options sentiment signal, valuation hardening, PM synthesis hallucination check
- [ ] Phase 2 — RAG & Growth Bet: EdgarTools, Finnhub, ChromaDB, nodes 5-7
- [ ] Phase 3 — Macro, Crowd & Stress Test: nodes 8-9, full stress test
- [ ] Phase 4 — Probability Engine calibration
- [ ] Phase 5 — Analyst Tracking & Grading
- [ ] Phase 6 — Prediction Ledger
- [ ] Phase 7 — PM Synthesis hardening & full frontend polish
- [ ] Phase 8 — Calibration Feedback & Hardening

## Active Tasks (immediate)
1. Run live AAPL + V test — confirm large_cap_blue_chip, options sentiment panel, analyst data
2. Review `equity-research-addendum.docx` — check for Phase 2 spec updates before starting Phase 2
3. Begin Phase 2: RAG & Growth Bet (EdgarTools, Finnhub, ChromaDB, nodes 5-7)

## Backlog
- Redis caching (Phase 2)
- ChromaDB + EdgarTools for filings RAG (Phase 2)
- Stress test node (Phase 3) — currently shows "unavailable"
- Probability engine backtesting / calibration (Phase 4)
- `_safe_float` still exists in `alpha_vantage_client.py` (intentionally kept — different string-handling logic for AV)
- Pydantic v2 Config deprecation warning — `class Config:` → `model_config = SettingsConfigDict(...)` in config.py (low priority)
