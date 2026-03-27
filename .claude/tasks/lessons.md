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

## L7 — git worktrees conflict when main has uncommitted changes
When a worktree branch is merged into main and main has unstaged edits to the same file,
the merge aborts. Always stash before merging from a worktree.

## L8 — Hard refresh clears stuck React state
If the Next.js app gets into a broken state (buttons unresponsive, analyze frozen),
`Cmd+Shift+R` hard refresh resets it. The EventSource from a previous analysis can
linger and block new interactions if the state machine doesn't reset cleanly.
