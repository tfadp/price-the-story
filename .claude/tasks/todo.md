# todo.md — Roadmap

## Session State
- branch: main
- last_test: 22/22 passed (2026-03-28) — EPS fix not yet regression-tested
- blocked: none
- pending_decisions:
  - Run live V/AAPL test to confirm EPS fix + probability engine now enabled
  - Addendum reviewed 2026-03-29 — new phase order (A–H) supersedes old 0–8 numbering

## Build Phases (addendum A–H order, from equity-research-addendum.md)
- [x] Baseline — classifier, fundamentals, valuation, analyst, macro, probability engine, PM synthesis, frontend, API hardening
- [x] Baseline+ — Monte Carlo probability engine, valuation hardening, PM synthesis hallucination check
- [ ] Phase A — Prediction Ledger: SQLite, auto-log after PM synthesis, 5 API endpoints, leaderboard UI tab
- [ ] Phase B — Growth Bet Extraction: EdgarTools, Finnhub transcripts, ChromaDB, assumption sheet, words-vs-numbers check
- [ ] Phase C — Filings RAG Full: risk evolution queries, insider (Form 4), institutional (13F)
- [ ] Phase D — News Sentiment: Finnhub /company-news, VADER scoring, Haiku narrative clusters
- [ ] Phase E — Price Efficiency: sentiment premium flag, optional historical analog
- [ ] Phase F — Analyst Tracking & Grading: FMP + Finnhub ingestion, auto-grading, leaderboard tab
- [ ] Phase G — Polymarket: public API, mapping file, populate stub
- [ ] Phase H — Redis cache + Brier score calibration feedback

## Active Tasks (immediate)
1. Live test V — confirm EPS fix lands, probability engine enabled, Monte Carlo P10/P50/P90 shows
2. Begin Phase A: Prediction Ledger (SQLite auto-log + leaderboard tab)

## Backlog
- `_safe_float` still exists in `alpha_vantage_client.py` (intentionally kept — different string-handling logic for AV)
- Pydantic v2 Config deprecation warning — `class Config:` → `model_config = SettingsConfigDict(...)` in config.py (low priority)
- Stress test node currently shows "unavailable" — Phase B/C territory
- Open questions from addendum (resolve before relevant phase):
  - EdgarTools: set_identity email in env (blocks Phase B)
  - Finnhub API key (blocks Phase B/D)
  - FMP key verification for /analyst-stock-recommendations (blocks Phase F)
  - Polymarket mapping file polymarket_markets.json (blocks Phase G)
  - Redis install (blocks Phase H)
