# exceptions.md — Proactive Catches

## Format
- [DATE] | [FILE] | [WHAT WAS CAUGHT] | [RESOLUTION]

## Log

- 2026-03-24 | app/data/financial_datasets_client.py | httpx.AsyncClient missing `follow_redirects=True` — all 5 FD endpoints returned 301 Moved Permanently, crashing the classifier node. | Added `follow_redirects=True` to all 5 AsyncClient instantiations (get_company_facts, get_snapshot_price, get_income_statements, get_balance_sheets, get_cash_flow_statements).

- 2026-03-24 | app/data/yfinance_client.py | Two f-strings with no placeholders (ruff F541). | Removed extraneous `f` prefix from both string literals in the 429 error message inside get_ticker_info.

- 2026-03-24 | app/nodes/{fundamentals,valuation,analyst_estimates,macro,news_sentiment,filings_rag,themes,polymarket}.py | All 8 parallel LangGraph nodes returned the full state dict instead of a delta. LangGraph 0.2.x raises `InvalidUpdateError: At key 'ticker': Can receive only one value per step` when multiple parallel nodes each try to write the same shared key. Caused 2 out of 5 smoke tests to fail with HTTP 500. | Changed all 8 parallel nodes to return only their own output key(s) as a partial dict (delta), not the full state. Serial nodes (classifier, probability_engine, pm_synthesis) were not affected.
