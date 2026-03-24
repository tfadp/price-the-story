# SPECS.md — Source of Truth (Contracts + Decisions)

## A) Naming Conventions (LOCKED)
- Variables: snake_case
- Functions: snake_case
- Classes: PascalCase
- Files: snake_case (Python), kebab-case (frontend components)
- Folders: lowercase
RULE: Do not change unless you follow Change Control in CLAUDE.md.

## B) Data Shapes / Schemas (LOCKED)
### API Request — POST /analyze-ticker
{
  "ticker":        string,   // required; US exchange symbol
  "target_cagr":   number,   // optional; decimal. Default: 0.10
  "entry_price":   number,   // optional; USD. Default: current close
  "horizons":      int[],    // optional; years. Default: [1,3,5,10]
  "preferences":   object,   // optional
  "force_refresh": boolean,  // optional; bypass cache. Default: false
  "debug":         boolean   // optional. Default: false
}

### Segment enum (LOCKED)
large_cap_blue_chip | mid_cap | small_cap_high_vol | other

### Confidence verdict enum (LOCKED)
high_confidence | moderate_confidence | low_confidence | insufficient_data

### Stress verdict enum (LOCKED)
robust | conditional | fragile

### Price efficiency verdict enum (LOCKED)
appears_inflated | fairly_priced | appears_conservative | insufficient_data

### Data quality enum (LOCKED)
high | medium | low

RULE: Any schema change requires before/after + impact + tests.

## C) Invariants (LOCKED)
- Timestamps: ISO 8601 format
- IDs: string (analyst_id format: firm_name:analyst_name, normalized lowercase with underscores)
- Prices: USD, number type
- CAGR/probabilities: decimal (0.10 = 10%), not percentage
- current_price: NEVER cached — always live from yfinance
- probability output: ALWAYS a range (low/high), never a point estimate
- US equities only in v1 — non-US returns HTTP 422

RULE: Add invariants early and treat them like law.

## D) Domain Rules (LOCKED)
- The tool answers ONE question per run. No portfolio context, no position sizing.
- Probability engine is DISABLED for small_cap_high_vol segment.
- suggested_entry_price is shown ONLY when efficiency_verdict = appears_inflated OR prob < 40% at user's horizon.
- verdict_paragraph must contain ZERO numbers not traced to a node output (anti-hallucination invariant).
- Node 1 (Classifier) failure = hard fail (HTTP 500). All other node failures = partial result.
- Bear weight is capped at 50% regardless of assumption fragility adjustments.
- Default target_cagr = 0.10 (10%). Default holding_period_years = 5.

RULE: Treat like invariants. Do not change without Change Control.

## E) Decisions Log (editable)
- 2026-03-24: Project initialized; Claude OS installed.
- 2026-03-24: Spec v5 read and ingested. Full 8-phase build plan confirmed.
- 2026-03-24: File naming — snake_case for Python, kebab-case for frontend components.
