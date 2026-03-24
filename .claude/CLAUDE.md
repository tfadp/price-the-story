# Price the Story
A buy-and-hold equity research assistant: given a stock + target return + holding period, it outputs a confidence assessment and a suggested entry price if current price makes that return unlikely.

## Tech Stack
- Backend: Python 3.11+, FastAPI, LangGraph (orchestration), Redis (cache + DLQ)
- Data: OpenBB, yfinance, FMP, Finnhub, EdgarTools (EDGAR), Polymarket API
- RAG: ChromaDB (local) + sentence-transformers or OpenAI embeddings
- LLMs: Claude Haiku (node summarization), Claude Sonnet (PM synthesis + growth bet extraction)
- Frontend: React + Next.js 14 (App Router), TypeScript, Tailwind CSS, Recharts

## Commands
(To be defined as we build)

## Key Files
equity-research-spec-v5.docx  — Master product spec (source of truth for features)
.claude/SPECS.md               — Locked naming conventions, schemas, invariants

## Project Rules
- Check .claude/SPECS.md only when modifying naming, schemas, or contracts.
  Do NOT load SPECS.md at session start.
- Spec file is the authority on all features, schemas, and data shapes.
- US equities only in v1. Return 422 for non-US tickers.
- Never hallucinate financial data — all numbers must trace to a real data source node.
- The spec defines 8 build phases. Work one phase at a time. Do not skip ahead.
