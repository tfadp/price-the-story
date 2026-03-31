# lessons.md — What We Learned

## L1 — Alpha Vantage free tier: 25 req/day, 1 req/sec
AV's free key is far too limited for heavy use in a pipeline that makes many calls.
Using AV for only ONE call per analysis (OVERVIEW for market cap supplement) keeps the free tier viable.
Never fire AV calls in parallel — the 1 req/sec limit kills one of the two concurrent calls silently.

## L2 — API parallel calls need rate-limit awareness
When `asyncio.gather` fires two calls to the same service, a per-second rate limit can kill one silently.
`return_exceptions=True` catches the exception but the caller gets an empty dict, not an error.
Fix: use sequential calls or dedicated single-purpose functions when rate limits are per-second.

## L3 — Financial Datasets returns market_cap=None for large caps
FD's `get_company_facts` endpoint does not always populate `market_cap` (returns None for AAPL).
Without a supplement, market_cap=0 triggers `market_cap < 2B` → `small_cap_high_vol`.
Fix: supplement from Alpha Vantage OVERVIEW (single call) when FD returns None.

## L4 — Pydantic field name mismatches are silent
When a node returns a dict with a key that doesn't match the Pydantic model field name,
`safe_model()` silently drops the field. No error, no warning, just None in the response.
Fix: grep the model definition before naming return dict keys in nodes.

## L5 — yfinance rate-limiting produces "possibly delisted" errors
When yfinance is hammered with rapid test calls, it returns empty history and logs
"possibly delisted; no price data found" — even for AAPL. This is a rate-limit artifact.
Fix: use history-derived volume from the data already in state rather than new fetches.

## L6 — LangGraph parallel nodes must return partial dicts (deltas)
Returning the full state from a parallel node causes `InvalidUpdateError` on shared keys.
Every parallel node must return only the keys it owns, e.g. `{"fundamentals": {...}}`.
Exception: `section_statuses` can also be returned because it has a merge reducer.

## L7 — git worktrees conflict when main has uncommitted changes
When a worktree branch is merged into main and main has unstaged edits to the same file,
the merge aborts. Always stash before merging from a worktree.

## L8 — Hard refresh clears stuck React state
If the Next.js app gets into a broken state (buttons unresponsive, analyze frozen),
`Cmd+Shift+R` hard refresh resets it. The EventSource from a previous analysis can
linger and block new interactions if the state machine doesn't reset cleanly.

## L9 — GitHub remote must be set before first push
This repo had no git remote configured. Running `git push origin main` before `git remote add`
causes a fatal error. The fix is `git remote add origin <url>` first, or if origin already
exists with wrong URL: `git remote set-url origin <correct-url>`.
Creating a GitHub repo with a README causes a divergent history — pull with
`--allow-unrelated-histories` before pushing.

## L10 — Parallel nodes cannot read state written by other parallel nodes
`news_sentiment` and `valuation` both run in the parallel fan-out. `news_sentiment`
cannot read `state["valuation"]` because it hasn't been written yet at that point.
Always use `ticker_meta` (written by the serial classifier node) for current price in parallel nodes.

## L11 — Binary 3-scenario probability voting is too coarse
A model that votes bull/base/bear each as 0.0 or 1.0 produces only 4 possible outputs
(0%, 35%, 80%, 100%) regardless of how good or bad the inputs are.
Fix: Monte Carlo simulation sampling continuous growth and multiple distributions produces
a real probability range that meaningfully differentiates stocks.

## L12 — FD income statement uses earnings_per_share_diluted, not eps_diluted
Financial Datasets API returns `earnings_per_share_diluted` and `earnings_per_share`.
The original code looked for `eps_diluted` and `eps` — silent None for every ticker.
This cascaded: no EPS → P/S fallback → low valuation confidence → probability engine disabled.
Fix: always check actual API response keys before writing field extraction code.

## L13 — EventSource cannot send custom headers; pass auth via query param
Browser EventSource API has no option to set request headers. If the backend requires
an API key via x-api-key header, SSE always returns 401.
Fix: backend accepts key from either header (POST) or x_api_key query param (SSE).
Frontend passes key as query param for SSE, header for fetch/POST.

## L14 — Prediction ledger uses 1-year grading, not holding-period CAGR
The ledger grades at 1 year (horizon_1yr_date). Scoring computes `realized/entry - 1`
(simple 1yr return). The modal preview must use the same formula — not CAGR with
holding_period_years as the exponent, which produces a different number for 5yr targets.
Lesson: UI math and backend math must use identical formulas. Verify both ends when writing
any financial calculation that appears in two places.

## L15 — Hard module imports break pytest collection and app startup
Importing `chromadb` at module level in filings_rag.py caused `ModuleNotFoundError`
during pytest collection — before any tests ran or fallbacks could fire.
Fix: move optional/heavy dependencies into lazy imports inside the function that needs them.
Pattern: `try: import heavy_lib except ImportError as e: raise RuntimeError("install X") from e`
Apply this to any Phase B+ dependency that isn't in the base requirements.
