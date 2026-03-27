# todo.md — Roadmap

## Session State
- branch: main
- last_test: 14/14 passed (2026-03-27)
- blocked: none
- pending_decisions:
  - Confirm AAPL shows `large_cap_blue_chip` after latest fixes (need live test)
  - Analyst "limited or unavailable" may still appear if Perplexity throws a silent exception in pipeline — debug logging added (Fix 3), check backend logs on next run

## Build Phases (from spec)
- [x] Phase 0 — Claude OS sidecar, skeleton, contracts
- [x] Phase 1 — Backend: nodes 1-4, 10-11, FastAPI
- [x] Phase 1 — Frontend: Next.js, VerdictCard, InputForm, ProgressRail
- [x] Phase 1 hardening — rate limiting, input validation, error handling, SSE progress
- [x] Phase 1 data layer — Financial Datasets (primary), Alpha Vantage (market cap supplement), yfinance (price history + analyst), Perplexity (analyst estimates primary)
- [x] Phase 1 perf — eliminated redundant network calls, LLM singletons, httpx pooling, safe_float dedup
- [ ] Phase 2 — RAG & Growth Bet: EdgarTools, Finnhub, ChromaDB, nodes 5-7
- [ ] Phase 3 — Macro, Crowd & Stress Test: nodes 8-9, full stress test
- [ ] Phase 4 — Probability Engine improvements + calibration
- [ ] Phase 5 — Analyst Tracking & Grading
- [ ] Phase 6 — Prediction Ledger
- [ ] Phase 7 — PM Synthesis hardening & full frontend polish
- [ ] Phase 8 — Calibration Feedback & Hardening

## Active Tasks (immediate)
1. Run live AAPL test — confirm `large_cap_blue_chip` + Perplexity analyst data shows
2. If analyst data still missing: check backend terminal for "Perplexity traceback" warning
3. Review `equity-research-addendum.docx` (untracked file — may contain spec updates)

## Backlog
- Redis caching (Phase 2)
- ChromaDB + EdgarTools for filings RAG (Phase 2)
- Stress test node (Phase 3) — currently shows "unavailable"
- Probability engine calibration (Phase 4)
- `_safe_float` still exists in `alpha_vantage_client.py` (intentionally kept — different logic for AV string values)
