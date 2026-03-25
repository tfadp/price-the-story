# todo.md — Roadmap

## Session State
- branch: main
- last_test: (pending — agents building now)
- blocked: none
- pending_decisions: user needs Anthropic API key before running

## Build Phases (from spec)
- [x] Phase 0 — Claude OS sidecar, skeleton, contracts
- [ ] Phase 1 — Backend: nodes 1-4, 10-11, FastAPI (AGENT BUILDING NOW)
- [ ] Phase 1 — Frontend: Next.js, VerdictCard, InputForm, ProgressRail (AGENT BUILDING NOW)
- [ ] Phase 2 — RAG & Growth Bet: EdgarTools, Finnhub, ChromaDB, nodes 5-7
- [ ] Phase 3 — Macro, Crowd & Stress Test: nodes 8-9, full stress test
- [ ] Phase 4 — Probability Engine improvements + calibration
- [ ] Phase 5 — Analyst Tracking & Grading
- [ ] Phase 6 — Prediction Ledger
- [ ] Phase 7 — PM Synthesis hardening & full frontend polish
- [ ] Phase 8 — Calibration Feedback & Hardening

## Next 3 Steps (after agents complete)
1) User gets Anthropic API key → copies .env.example to .env → adds key
2) `cd backend && pip install -r requirements.txt && uvicorn app.main:app --port 8000`
3) `cd frontend && npm install && npm run dev` → open http://localhost:3000

## Backlog
- Add FMP API key for better analyst estimates
- Add Finnhub API key for news + transcripts
- Redis caching (Phase 2)
- ChromaDB + EdgarTools for filings RAG (Phase 2)
