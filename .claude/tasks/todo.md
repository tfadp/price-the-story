# todo.md — Roadmap

## Session State
- branch: main
- last_test: passing (exact count TBD — tests run during sync but slow due to model load)
- last_commit: e3655b8 — fix: review findings — auth, scoring, lazy imports, SSE cancel
- blocked: none
- pending_decisions:
  - Live test V or AAPL — confirm EPS fix working, probability engine enabled, Phase B filings show in verdict

## Build Phases (addendum A–H order, from equity-research-addendum.md)
- [x] Baseline — classifier, fundamentals, valuation, analyst, macro, probability engine, PM synthesis, frontend, API hardening
- [x] Baseline+ — Monte Carlo probability engine, valuation hardening, PM synthesis hallucination check
- [x] Phase A — Prediction Ledger: SQLite, auto-log after PM synthesis, 5 API endpoints, leaderboard UI tab
- [x] Phase B — Growth Bet Extraction: EdgarTools, Finnhub transcripts, ChromaDB, assumption sheet, words-vs-numbers check
- [x] Review fixes — auth/SSE, scoring CAGR, lazy imports, SSE stream cancel
- [ ] Phase C — Filings RAG Full: risk evolution queries, insider (Form 4), institutional (13F)
- [ ] Phase D — News Sentiment: Finnhub /company-news, VADER scoring, Haiku narrative clusters
- [ ] Phase E — Price Efficiency: sentiment premium flag, optional historical analog
- [ ] Phase F — Analyst Tracking & Grading: FMP + Finnhub ingestion, auto-grading, leaderboard tab
- [ ] Phase G — Polymarket: public API, mapping file, populate stub
- [ ] Phase H — Redis cache + Brier score calibration feedback

## Active Tasks (immediate — cliffhanger)
1. Live test V or AAPL — restart backend, run analysis, confirm:
   - Probability engine enabled (EPS fix working)
   - "The Bet & The Evidence" section shows real assumption sheet from filings
   - "My Predictions" tab logs the run automatically
2. Begin Phase D (News Sentiment) — Finnhub key is already set

## Backlog
- Phase B gap: `implied_vs_guidance` field in valuation not yet wired (needs filings_rag output fed back into valuation node — Phase B.2)
- `_safe_float` still exists in `alpha_vantage_client.py` (intentionally kept — different string-handling logic for AV)
- Pydantic v2 Config deprecation warning — `class Config:` → `model_config = SettingsConfigDict(...)` in config.py (low priority)
- Open questions from addendum:
  - FMP key verification for /analyst-stock-recommendations (blocks Phase F)
  - Polymarket mapping file polymarket_markets.json (blocks Phase G)
  - Redis install (blocks Phase H)
