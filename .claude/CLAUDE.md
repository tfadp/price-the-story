# Price the Story
A buy-and-hold equity research assistant: given a stock + target return + holding period, it outputs a confidence assessment and a suggested entry price if current price makes that return unlikely.

## Tech Stack
- Backend: Python 3.11+, FastAPI, LangGraph (orchestration), Redis (cache + DLQ)
- Data: Financial Datasets AI (primary), Alpha Vantage (market cap supplement only — 1 call/analysis), yfinance (price history + analyst data), Perplexity API (analyst estimates primary)
- RAG: ChromaDB (local) + sentence-transformers or OpenAI embeddings
- LLMs: Claude Haiku (node summarization), Claude Sonnet (PM synthesis + growth bet extraction)
- Frontend: React + Next.js 14 (App Router), TypeScript, Tailwind CSS, Recharts

## Commands
```bash
# Backend
cd backend && uvicorn app.main:app --reload

# Frontend
cd frontend && npm run dev

# Tests
cd backend && python -m pytest tests/ -v

# Lint
cd backend && python -m ruff check app/ tests/
cd frontend && npx tsc --noEmit
```

## Key Files
equity-research-spec-v5.md     — Master product spec (source of truth for features)
.claude/SPECS.md               — Locked naming conventions, schemas, invariants

## Project Rules
- Check .claude/SPECS.md only when modifying naming, schemas, or contracts.
  Do NOT load SPECS.md at session start.
- Spec file is the authority on all features, schemas, and data shapes.
- US equities only in v1. Return 422 for non-US tickers.
- Never hallucinate financial data — all numbers must trace to a real data source node.
- The spec defines 8 build phases. Work one phase at a time. Do not skip ahead.

## Data Source Rules
- Financial Datasets: primary for financials, company facts, snapshot price
- Alpha Vantage: ONE call only (OVERVIEW for market cap when FD returns None). NEVER fire AV calls in parallel — 1 req/sec free tier limit kills one silently.
- yfinance: price history (macro ETFs, volatility calc), analyst data fallback
- Perplexity: primary for analyst estimates (pay-per-use, no daily cap)

## LangGraph Rules
- Parallel nodes MUST return only their own output key as a partial dict (delta).
  NEVER return the full state from a parallel node.
- Serial nodes (classifier, probability_engine, pm_synthesis) may modify state in-place.
- Parallel nodes CANNOT read state written by other parallel nodes (they run concurrently).
  Use `ticker_meta` (written by the serial classifier) for current price inside parallel nodes.
  Never try to read `state["valuation"]` or `state["fundamentals"]` from within another parallel node.
- `section_statuses` may also be returned from parallel nodes — it has a merge reducer and won't conflict.

## Pydantic / API Contract Rules
- Before naming a return dict key in a node, grep the Pydantic model for the exact field name.
  Mismatches are silently dropped — no error thrown.
- Never use `from __future__ import annotations` in main.py — FastAPI cannot resolve
  forward-ref strings to Pydantic body types.
