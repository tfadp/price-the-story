# Open-Source Integration Spec

**Price the Story — Analytical Depth Upgrade**

Version 1.0 | March 2026

Owner: Dan (Product)

Status: Ready for Review

---

## 1. Purpose

Price the Story produces a single-pass analysis: one LLM call per node, one synthesis pass, one verdict. That architecture is fast and honest, but it leaves analytical depth on the table. The most interesting open-source projects in this space — virattt/ai-hedge-fund and TauricResearch/TradingAgents — have demonstrated that multi-perspective LLM evaluation produces materially better output than single-pass analysis, particularly on the questions that matter most for long-horizon research: is the growth story credible, and is the price already ahead of the business?

This spec defines a phased plan to deepen Price the Story's analytical quality by selectively integrating patterns and code from these repos, while preserving the project's core identity: a confidence assessment tool, not a trading signal generator.

---

## 2. What We're Drawing From

### 2.1 virattt/ai-hedge-fund (49.6K ★, MIT)

**What it does well that we don't:**

The system runs 12 investor-philosophy agents (Buffett, Graham, Damodaran, Cathie Wood, Burry, etc.) in parallel, each evaluating the same stock through a distinct investment lens. A Portfolio Manager agent then synthesizes their conflicting signals into a single decision. The key insight is that the "debate" emerges passively — the PM sees Burry at "bearish 70%" and Cathie Wood at "bullish 85%" on the same stock and must reconcile that tension in its reasoning.

**What we want from it:**

- The Financial Datasets API wrapper (`src/tools/api.py`) — production-tested, handles auth, rate limiting, and pagination. Direct fork candidate.
- The in-memory cache with deduplication (`src/data/cache.py`) — clean pattern for our Redis migration.
- The multi-provider LLM abstraction (`src/llm/models.py`) — factory pattern across Anthropic, OpenAI, Groq, DeepSeek. Useful if we ever need to swap models per node.
- The philosophy-based agent prompt pattern — not the specific agents, but the template: specialized system prompt → financial metrics input → structured signal with confidence score → JSON output. This maps directly to what we need for the Thesis Stress Agent (Phase 1).

**What we don't want:**

- The trading signal output format (bullish/bearish/neutral with position sizing). We produce probability bands and confidence verdicts, not trade recommendations.
- The Portfolio Manager synthesis pattern — it's too shallow for our use case. It compresses 12 agent signals into buy/sell/hold. Our PM synthesis node already does something more sophisticated: it writes a narrative verdict paragraph that explains the reasoning, not just the conclusion.
- The frontend — ours is already more purpose-built.

### 2.2 TauricResearch/TradingAgents (44K ★, Apache-2.0)

**What it does well that we don't:**

A structured bull-vs-bear debate with configurable rounds. Two researcher agents argue opposing positions across N rounds, then a judge agent synthesizes both perspectives into a balanced conclusion. Separately, a three-way risk debate (aggressive / conservative / neutral) produces risk assessment through structured disagreement. The framework also uses a dual-model strategy: `deep_think_llm` for complex reasoning and `quick_think_llm` for fast extraction — which maps exactly to our Sonnet/Haiku split.

**What we want from it:**

- The dialectical debate pattern for thesis stress-testing. Our current stress test applies mechanical shocks to assumptions. A bull/bear debate that argues over whether those assumptions are actually fragile would produce materially better verdicts.
- The hybrid state management approach: structured outputs for data flow, natural language for debate. This prevents the "telephone effect" where information degrades across agent exchanges.
- The configurable `max_debate_rounds` parameter — lets us control depth vs. latency vs. cost.

**What we don't want:**

- The data layer — they use yfinance and basic indicators. Our Financial Datasets + EdgarTools stack is substantially better for fundamental research.
- The trading execution pipeline. We're a research tool, not an executor.
- The full agent taxonomy — their 7 roles are oriented around trading firm operations. We need research-oriented roles.

### 2.3 pmxt-dev/pmxt (1.2K ★, MIT)

**Narrow but direct fit for Phase G (Polymarket).**

Unified TypeScript/Python SDK across Polymarket, Kalshi, Limitless, and three other prediction market platforms. Our addendum spec already has a Polymarket stub — pmxt replaces a hand-rolled single-API integration with a multi-platform library that's actively maintained (546 commits, 111 releases, v2.22.1 shipping March 2026). The cross-platform aggregation also means we can show consensus across prediction markets, not just Polymarket odds.

---

## 3. Phased Roadmap

### Phase 1: Thesis Debate Engine (Weeks 1–3)

**The highest-value change.** Replace the current single-pass PM synthesis with a multi-perspective evaluation that produces a materially better verdict.

### Phase 2: Data Layer Hardening (Weeks 4–5)

**Fork and adapt ai-hedge-fund's Financial Datasets wrapper and cache layer.** Replace our hand-rolled API calls with battle-tested code. Wire in the multi-provider LLM abstraction as a foundation for model flexibility.

### Phase 3: Prediction Market Upgrade (Week 6)

**Replace the Polymarket stub with pmxt.** Expand from single-platform to cross-platform prediction market signals. Low effort, additive value.

### Phase 4: Calibrated Confidence (Weeks 7–9)

**Close the loop.** Use debate history and prediction outcomes to calibrate the system's confidence over time.

---

## 4. Phase 1 — Thesis Debate Engine

### 4.1 Problem with Current Architecture

The current system runs 8 parallel data nodes, feeds everything into a deterministic probability engine, then hands the full state to a single Sonnet call (PM Synthesis) that writes the verdict. This is efficient but brittle in one specific way: the verdict paragraph reflects whatever the PM agent's single pass produces. There is no adversarial pressure on the growth thesis, no structured challenge to the assumptions, and no mechanism for the system to argue with itself about whether the price is justified.

The result: verdicts tend to be balanced and reasonable but lack the kind of sharp, opinionated assessment that a real senior analyst would produce after debating the thesis with a skeptical colleague.

### 4.2 What Changes

Insert a **Thesis Debate** step between the Probability Engine (Node 10) and PM Synthesis (Node 11). This step takes the assumption sheet, stress test results, valuation, and all data node outputs, and runs a structured bull-vs-bear debate before synthesis.

**New execution flow:**

```
Node 1 (Classifier)
  → Parallel: Nodes 2–9
    → Node 10 (Probability Engine + Stress Test)
      → Node 10.5 (Thesis Debate) ← NEW
        → Node 11 (PM Synthesis)
```

### 4.3 Thesis Debate Node (10.5) — Specification

**Three agents, one round of debate, one synthesis.**

| Agent | Role | Model | Max Tokens |
|-------|------|-------|------------|
| Bull Analyst | Argues the investment case succeeds at the target CAGR over the holding period | Sonnet | 800 |
| Bear Analyst | Argues the investment case fails — identifies the specific assumption that breaks | Sonnet | 800 |
| Debate Judge | Reads both arguments and produces a structured verdict input for PM Synthesis | Sonnet | 600 |

**Why Sonnet for all three, not Haiku:** The quality of the debate is the entire point. Haiku produces adequate summaries but weak arguments. The debate agents need to identify non-obvious failure modes and make genuinely persuasive cases. This is worth the additional ~15 seconds and ~$0.03/run.

**Bull Analyst prompt structure:**

```
You are a senior equity analyst who believes in this investment thesis.

Company: {ticker} ({segment})
Stated growth bet: {stated_bet}
Assumption sheet: {assumption_sheet}
Words-vs-numbers alignment: {words_vs_numbers_alignment}
Fair value range: ${fair_value_low} – ${fair_value_high} (base: ${fair_value_base})
Current price: ${current_price}
Target: {target_cagr}% CAGR over {holding_period} years
Probability at target: {prob_low}–{prob_high}%
Stress test verdict: {stress_verdict}

Make the strongest possible case that this investment achieves the target return.
Be specific: which assumptions are most robust? What evidence supports the growth
story? What does the market appear to be underpricing? Reference the actual numbers
from the assumption sheet and fundamentals.

Do not hedge. Do not caveat. Make the bull case as if your reputation depends on it.
If the case is genuinely weak, say so — a credible bull analyst doesn't argue
a losing position.

Output: 3–5 sentences. Plain English. No jargon.
```

**Bear Analyst prompt structure:**

```
You are a senior equity analyst who is skeptical of this investment thesis.

[Same data inputs as Bull]

Make the strongest possible case that this investment fails to achieve the target
return. Be specific: which assumption is the single most likely to break? What is
the market pricing in that management hasn't delivered? Where does the
words-vs-numbers alignment raise doubt?

Focus on the most likely failure mode, not the worst-case scenario. A good bear
case identifies the specific, plausible path to disappointing returns — not a
catastrophe fantasy.

Do not hedge. Do not acknowledge the bull case. Make the bear case as if your
reputation depends on it. If the bear case is genuinely weak, say so.

Output: 3–5 sentences. Plain English. No jargon.
```

**Debate Judge prompt structure:**

```
You are a portfolio manager reviewing a bull/bear debate on {ticker}.

Bull case: {bull_output}
Bear case: {bear_output}

Your job is NOT to pick a winner. Your job is to identify:

1. thesis_tension: One sentence naming the core disagreement between bull and bear.
2. strongest_bull_point: The single most compelling element of the bull case.
3. strongest_bear_point: The single most compelling element of the bear case.
4. unresolved_question: One specific, answerable question that would resolve the
   debate if answered. Must be tied to an observable metric or upcoming event.
5. verdict_lean: bull | bear | genuinely_uncertain
6. conviction_modifier: strengthens | weakens | unchanged — does this debate
   change the probability engine's output?

Output as JSON. No hedging in thesis_tension — name the actual tension.
```

### 4.4 How Debate Output Feeds PM Synthesis

The Debate Judge's structured output becomes a new input to Node 11. The PM Synthesis prompt is updated:

```
[Existing PM synthesis prompt, unchanged]

ADDITIONAL CONTEXT — Thesis Debate:
The investment thesis was debated by opposing analysts.
Core tension: {thesis_tension}
Strongest bull point: {strongest_bull_point}
Strongest bear point: {strongest_bear_point}
Unresolved question: {unresolved_question}
Debate lean: {verdict_lean}
Conviction modifier: {conviction_modifier}

If conviction_modifier is "weakens", your verdict paragraph MUST acknowledge the
specific bear point that weakened conviction. If "strengthens", acknowledge the
specific bull point. If "unchanged", you may reference either or neither.

The unresolved_question MUST appear in the verdict card as a one-line note below
the verdict paragraph: "Key question: {unresolved_question}"
```

### 4.5 State Schema Additions

New fields in LangGraph state (written by Node 10.5, read by Node 11):

```python
class ThesisDebateOutput(TypedDict):
    bull_case: str           # 3–5 sentence bull argument
    bear_case: str           # 3–5 sentence bear argument
    thesis_tension: str      # One sentence naming core disagreement
    strongest_bull_point: str
    strongest_bear_point: str
    unresolved_question: str
    verdict_lean: str        # "bull" | "bear" | "genuinely_uncertain"
    conviction_modifier: str # "strengthens" | "weakens" | "unchanged"
```

This is a serial node (runs after Node 10, before Node 11), so it may modify state in-place per the existing LangGraph rules in CLAUDE.md.

### 4.6 New API Response Fields

| Field | Location | Type | Notes |
|-------|----------|------|-------|
| `thesis_debate` | Top-level | object | Full debate output for the detail panel |
| `thesis_tension` | `thesis_debate` | string | Core disagreement — surfaces in verdict card |
| `unresolved_question` | `thesis_debate` | string | Surfaces below verdict paragraph |
| `verdict_lean` | `thesis_debate` | string | bull \| bear \| genuinely_uncertain |
| `conviction_modifier` | `thesis_debate` | string | strengthens \| weakens \| unchanged |
| `bull_case` | `thesis_debate` | string | Full bull argument — detail panel only |
| `bear_case` | `thesis_debate` | string | Full bear argument — detail panel only |

### 4.7 Frontend — Verdict Card Updates

Two additions to the VerdictCard component:

1. **Unresolved question line** — appears below the verdict paragraph, above the stress verdict badge. Styled as a subtle callout: "Key question: {unresolved_question}". Always present when thesis_debate is populated.

2. **Conviction modifier indicator** — small inline badge next to the confidence badge. Shows ↑ (strengthens), ↓ (weakens), or — (unchanged). Tooltip on hover shows `thesis_tension`.

### 4.8 Frontend — New Detail Panel

Add a new collapsible detail panel: **"The Debate"** — positioned between "The Bet & The Evidence" and "What Breaks It".

Contents:
- Bull case (3–5 sentences, displayed with a subtle green left border)
- Bear case (3–5 sentences, displayed with a subtle red left border)
- Thesis tension (bold, centered between the two)
- Verdict lean badge
- Unresolved question (highlighted)

### 4.9 Latency and Cost Impact

| Metric | Before | After | Delta |
|--------|--------|-------|-------|
| Wall-clock time | 30–90s | 45–105s | +15s (3 serial Sonnet calls) |
| Sonnet calls per run | 2 (assumption sheet + PM synthesis) | 5 (+bull, +bear, +judge) | +3 |
| Estimated cost per run | ~$0.04 | ~$0.07 | +$0.03 |

The 15-second increase pushes the upper bound past the master spec's 90-second target. Two mitigations:

1. **Run bull and bear agents in parallel** (they don't read each other's output). This cuts the debate from 3 serial calls to 2 serial stages (bull+bear parallel, then judge). Saves ~5 seconds, bringing the upper bound to ~100s.
2. **Update the master spec latency target** from 30–90s to 30–105s. The original target was set before the debate engine existed. A 15-second increase for materially better verdict quality is a defensible trade.

The existing SSE progress rail gets a new stage label: "Debating the thesis" — inserted between "Running stress scenarios" and "Writing verdict".

### 4.10 Configurable Debate Depth

Borrow TradingAgents' `max_debate_rounds` pattern. Default: 1 round (bull → bear → judge). Optional: 2 rounds (bull → bear → bull rebuttal → bear rebuttal → judge). The second round adds ~10 seconds and ~$0.02 but produces noticeably sharper arguments on complex theses. Expose as an internal config, not a user-facing option.

```python
# config.py
THESIS_DEBATE_ROUNDS = int(os.getenv("THESIS_DEBATE_ROUNDS", "1"))
```

For round 2, the rebuttal prompts receive the opposing analyst's first-round output and are instructed to directly address the strongest point made by the other side.

### 4.11 Debate Skip Conditions

Skip the debate node and pass directly to PM Synthesis when:

- `data_quality` = low (not enough data to argue about)
- `segment` = small_cap_high_vol and fewer than 3 assumptions in assumption_sheet
- `probability_engine.enabled` = false

When skipped, `thesis_debate` is null in the response. PM Synthesis prompt falls back to its current behavior without debate context.

### 4.11.1 Degraded Mode — Partial Assumption Sheet

If assumption_sheet has fewer than 3 items (e.g., addendum Phase B is partially complete or the ticker has limited filings), the debate still runs but with adjusted prompts. The bull/bear agents receive fundamentals + valuation data instead of the assumption sheet and argue about whether the price is justified by the numbers alone. The debate is less rich but still produces a thesis tension and unresolved question that improve the verdict.

**Minimum viable input for debate:** `current_price` + `fair_value_base` + `fundamentals.business_summary` + at least one of: `assumption_sheet`, `stress_test`, or `words_vs_numbers_alignment`. If none of these three exist, skip the debate.

### 4.12 Schema Registration

The following fields must be added to SPECS.md before implementation:

- `thesis_debate` (top-level response object)
- `thesis_debate.bull_case`, `thesis_debate.bear_case` (string)
- `thesis_debate.thesis_tension`, `thesis_debate.unresolved_question` (string)
- `thesis_debate.strongest_bull_point`, `thesis_debate.strongest_bear_point` (string)
- `thesis_debate.verdict_lean` (enum: bull | bear | genuinely_uncertain)
- `thesis_debate.conviction_modifier` (enum: strengthens | weakens | unchanged)

### 4.13 Master Spec Updates Required

When Phase 1 ships, update equity-research-spec-v5.md:

- §5.2: Update node count from 11 to 12. Add Node 10.5 to execution order diagram.
- §4.3.1: Add unresolved_question line and conviction modifier badge to Verdict Card spec.
- §4.3.2: Add "The Debate" panel to Supporting Detail Panels table.
- Latency target: Update from 30–90s to 30–105s with note explaining the debate engine trade-off.
- §10.2: Add DebatePanel component to frontend component table.

---

## 5. Phase 2 — Data Layer Hardening

### 5.1 Fork: Financial Datasets API Wrapper

**Source:** ai-hedge-fund `src/tools/api.py`

The current Price the Story codebase makes direct HTTP calls to Financial Datasets. ai-hedge-fund's wrapper handles authentication, rate limiting, pagination, and error recovery in a tested module that's been hammered by 49K+ users. Fork it, adapt it, and replace our hand-rolled calls.

**Adaptation required:**

- Strip trading-specific endpoints (we don't need the order or portfolio endpoints)
- Add our Alpha Vantage OVERVIEW fallback for market cap (one call, existing pattern)
- Add our Perplexity integration for analyst estimates (not in ai-hedge-fund)
- Wire into our existing node functions as a drop-in replacement for raw `requests` calls
- Maintain our existing fallback chain: Financial Datasets → yfinance → manual

**Files to fork:**
- `src/tools/api.py` → `backend/app/data/financial_datasets.py`
- `src/data/cache.py` → study pattern, adapt for our Redis layer (Phase H of addendum)
- `src/data/models.py` → cherry-pick `FinancialMetrics` and `Price` models, align with our Pydantic schemas

### 5.2 Fork: Multi-Provider LLM Abstraction

**Source:** ai-hedge-fund `src/llm/models.py`

Currently Price the Story hardcodes Anthropic SDK calls. ai-hedge-fund's factory pattern lets you configure the provider per call. We don't need this today (we're committed to Claude), but the abstraction costs nothing and gives us optionality if Anthropic pricing changes, if a specific node performs better on a different model, or if we want to test Haiku vs. Gemini Flash for summarization nodes.

**Adaptation:**
- Keep Anthropic as default provider
- Add configuration per node in `config.py`: `NODE_MODEL_MAP = {"classifier": "haiku", "pm_synthesis": "sonnet", ...}`
- Preserve our existing Sonnet/Haiku split but make it configurable

### 5.3 Cache Pattern Upgrade

**Source:** ai-hedge-fund `src/data/cache.py`

Their singleton cache with deduplication-by-unique-key is a clean pattern. We adapt it as the in-memory layer that sits in front of Redis (Phase H). The deduplication logic — using set-based O(1) lookups keyed by accession number, date, or filing ID — prevents re-embedding filings we've already processed in ChromaDB.

**New cache hierarchy:**
```
Request → In-memory dedup check → Redis TTL cache → API call → Write to both
```

---

## 6. Phase 3 — Prediction Market Upgrade

### 6.1 Replace Polymarket Stub with pmxt

**Current state:** Addendum Phase G spec calls for direct Polymarket API integration with a hand-maintained `polymarket_markets.json` mapping file.

**Upgrade:** Use pmxt's unified SDK instead. Benefits:

- One API across Polymarket, Kalshi, Limitless, and three other platforms
- Cross-platform consensus: when Polymarket says 62% recession probability and Kalshi says 58%, that convergence is a stronger signal than either alone
- Actively maintained (weekly releases), so we don't own the API compatibility burden
- Python SDK available via pip: `pip install pmxt`

### 6.2 Implementation Changes to Addendum Phase G

| Addendum G Spec | Updated Approach |
|-----------------|------------------|
| Source: Polymarket /markets API | Source: pmxt unified API (Polymarket + Kalshi primary) |
| Mapping: polymarket_markets.json | Mapping: same file, but add Kalshi market slugs alongside Polymarket |
| Liquidity filter: OI > $50K | Liquidity filter: OI > $50K per platform, aggregate cross-platform |
| Output: polymarket_signals array | Output: prediction_market_signals array (renamed to reflect multi-platform) |

### 6.3 Schema Changes

Rename `polymarket_signals` → `prediction_market_signals` across the API response and frontend. **This is a breaking API change.** The field is referenced in equity-research-spec-v5.md (§7.8) and the addendum (Phase G). All three documents and the frontend type definitions must be updated in a single coordinated change. Each signal object gains a `platform` field:

```python
class PredictionMarketSignal(BaseModel):
    market_name: str
    platform: str          # "polymarket" | "kalshi" | "limitless" | etc.
    implied_probability: float
    direction_for_ticker: str  # "positive" | "negative" | "neutral"
    notes: str
    cross_platform_consensus: float | None  # Average probability across platforms
```

### 6.4 Verdict Card Integration

When `cross_platform_consensus` is available for a macro signal relevant to the ticker, surface it in the MacroPanel as: "Prediction markets (Polymarket + Kalshi) imply {X}% probability of {event}."

---

## 7. Phase 4 — Calibrated Confidence

### 7.1 Debate-Informed Calibration

The thesis debate generates a `verdict_lean` and `conviction_modifier` on every run. Log both to the predictions table alongside the existing fields. Over time (50+ scored predictions), this enables a new calibration signal:

- When `verdict_lean` = bear and `conviction_modifier` = weakens, how often does the investment actually underperform?
- When the debate produces `genuinely_uncertain`, does widening the probability band improve calibration?

### 7.2 New Prediction Table Fields

```sql
ALTER TABLE predictions ADD COLUMN verdict_lean TEXT;
ALTER TABLE predictions ADD COLUMN conviction_modifier TEXT;
ALTER TABLE predictions ADD COLUMN thesis_tension TEXT;
ALTER TABLE predictions ADD COLUMN unresolved_question TEXT;
ALTER TABLE predictions ADD COLUMN debate_rounds INT DEFAULT 1;
```

### 7.3 Debate Quality Tracking

After 25+ scored predictions with debate data, run a signal correlation analysis:

- Does `conviction_modifier = "weakens"` predict worse 1-year outcomes?
- Does `verdict_lean` alignment with `confidence_verdict` correlate with accuracy?
- Does 2-round debate produce better-calibrated verdicts than 1-round?

If the debate consistently correlates with outcome accuracy, increase its weight in the probability engine. If it doesn't, keep it as a qualitative input to PM synthesis only — it still improves verdict paragraph quality even if it doesn't improve probability calibration.

### 7.4 Timeline Dependency

This phase depends on having scored predictions with debate data. Meaningful analysis requires 50+ outcomes, which at a pace of 3–5 analyses per week means roughly 3–4 months of data collection after Phase 1 ships. Phase 4 implementation should be built alongside Phase 1 (the logging), but the calibration analysis itself is a delayed output.

---

## 8. Implementation Priority Matrix

| Phase | Effort | Value | Risk | Dependency |
|-------|--------|-------|------|------------|
| 1 — Thesis Debate | 2–3 weeks | Very high — transforms verdict quality | Medium — Sonnet calls add latency and cost | Addendum Phases B+C (needs assumption_sheet populated). Can run in degraded mode with partial data — see §4.11.1 |
| 2 — Data Layer | 1–2 weeks | Medium — reliability and maintainability | Low — drop-in replacement | None — can start immediately |
| 3 — Prediction Markets | 3–4 days | Low-medium — enriches macro section | Low — isolated node change | Addendum Phase G stub must be wired |
| 4 — Calibrated Confidence | 1 week to build, 3–4 months to produce results | Long-term high — self-improving system | Low — logging is cheap | Phase 1 + 50 scored predictions |

**Recommended start order:** Phase 2 → Phase 1 → Phase 3 → Phase 4

Start with Phase 2 (data layer hardening) because it's low-risk, immediately useful, and gives you a cleaner foundation for everything else. Phase 1 (thesis debate) is the big analytical upgrade. It depends on having the assumption sheet populated (addendum Phases B+C), so the practical sequence is: **this spec's Phase 2 → addendum Phases A+B+C → this spec's Phase 1 → Phase 3 → Phase 4.** Phase 3 is independent and can slot in whenever Phase G of the addendum is in scope. Phase 4's logging should be wired during Phase 1 implementation; the calibration analysis runs months later.

**Coordination with addendum phases:** This spec's Phase 1 is not a replacement for addendum Phase B — it's an addition that runs *after* the assumption sheet exists. The addendum phases (A through H) remain the primary build sequence. This spec layers on top of them.

---

## 9. What We're Explicitly Not Doing

To keep scope honest:

- **Not adding philosophy-based agents.** ai-hedge-fund's Buffett/Graham/Damodaran agents are compelling demos but they're roleplaying investment philosophies, not doing fundamental research. Our assumption-sheet-driven approach is more rigorous for long-horizon assessment. The debate engine borrows the *pattern* (opposing perspectives → synthesis) without the specific personas.

- **Not adding trading signals.** Both repos produce buy/sell/hold outputs. We produce confidence assessments and suggested entry prices. That distinction is the product's identity.

- **Not adding a full multi-round debate loop.** TradingAgents supports N rounds of back-and-forth. For our use case, 1 round (with optional 2nd) is the right balance. More rounds increase latency without proportional insight gain on a research question — the marginal value of round 3 of a bull/bear argument about whether NVDA's data center revenue growth is sustainable is near zero.

- **Not forking the frontend from either repo.** Our verdict-first, panel-based UI is already more purpose-built than either project's interface.

- **Not adding real-time trading capabilities, position sizing, portfolio management, or account state.** The product boundary hasn't changed.

---

## 10. Open Questions

| # | Question | Blocks |
|---|----------|--------|
| 1 | Should the debate node run on every analysis, or only when `stress_verdict` = conditional or fragile? Running only on uncertain cases saves cost but loses the signal when a "robust" thesis has a strong bear case the system would otherwise miss. **Recommendation: run always, at least until we have calibration data.** | Phase 1 |
| 2 | Should the bull/bear agents have access to the full stress test output, or only the assumption sheet? Full stress test gives them more material but risks the arguments becoming mechanical recitations of shock scenarios rather than independent reasoning. **Recommendation: assumption sheet + fundamentals + valuation only. Let the agents find their own arguments.** | Phase 1 |
| 3 | pmxt Python SDK maturity — verify it handles Kalshi auth (API key required, unlike Polymarket). If Kalshi integration is unstable, fall back to Polymarket-only with pmxt. | Phase 3 |
| 4 | License compliance: ai-hedge-fund is MIT (no restrictions on forking). TradingAgents is Apache-2.0 (requires attribution in derivative works — add to NOTICE file). pmxt is MIT. | All phases |

---

*— End of Spec —*
