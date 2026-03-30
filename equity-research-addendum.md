**ADDENDUM SPECIFICATION**

Equity Research Tool --- Phases A through H

Version 1.0 \| March 2026

Owner: Dan (Product)

Audience: Dev Team --- Delta from current working build

***This document specs only what does not yet exist.***

**1. What Is Already Built --- Do Not Re-Implement**

This section documents the working build so the addendum specs only the delta.

  ------------------------------------------------------------------------------------------------------------------
  **✅ LIVE ---** Classifier node: Financial Datasets primary, yfinance fallback. US equity confirmation, cap size.
  ------------------------------------------------------------------------------------------------------------------

  -------------------------------------------------------------------------------------------------------------------------
  **✅ LIVE ---** Fundamentals node: Financial Datasets (income statement, balance sheet, cash flow), yfinance fills gaps.
  -------------------------------------------------------------------------------------------------------------------------

  ----------------------------------------------------------------------------------------
  **✅ LIVE ---** Valuation node: DCF model, bear/base/bull fair value range, entry band.
  ----------------------------------------------------------------------------------------

  ----------------------------------------------------------------------------------------------------------------------
  **✅ LIVE ---** Analyst estimates node: yfinance buy/hold/sell counts and price targets. Perplexity writes narrative.
  ----------------------------------------------------------------------------------------------------------------------

  -------------------------------------------------------------------------------------------------------------
  **✅ LIVE ---** Macro node: regime classification, scenario impacts. Claude Haiku writes 2-sentence summary.
  -------------------------------------------------------------------------------------------------------------

  -------------------------------------------------------------------------------------------------------
  **✅ LIVE ---** Probability engine: deterministic math. Scenario-weighted probability at each horizon.
  -------------------------------------------------------------------------------------------------------

  ---------------------------------------------------------------
  **✅ LIVE ---** PM synthesis: Claude Sonnet verdict paragraph.
  ---------------------------------------------------------------

  --------------------------------------------------------------------------------------
  **✅ LIVE ---** Frontend: Next.js, SSE progress rail, verdict card + 5 detail panels.
  --------------------------------------------------------------------------------------

  --------------------------------------------------------------------------------------------------------------
  **✅ LIVE ---** API hardening: rate limiting, input validation, error sanitization, SSE cancel on disconnect.
  --------------------------------------------------------------------------------------------------------------

  ------------------------------------------------------
  **🔌 STUB ---** News sentiment: wired, not populated.
  ------------------------------------------------------

  ------------------------------------------------------------------------
  **🔌 STUB ---** Filings RAG: wired, ChromaDB integrated, not populated.
  ------------------------------------------------------------------------

  -----------------------------------------------------------
  **🔌 STUB ---** Themes / Polymarket: wired, not populated.
  -----------------------------------------------------------

+----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| **Data source deviation from original spec**                                                                                                                                                                                     |
|                                                                                                                                                                                                                                  |
| The original spec called for OpenBB. The build uses Financial Datasets + yfinance. This is the better choice for US equities. All addendum phases use Financial Datasets + yfinance as the established stack. OpenBB is dropped. |
+----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+

**2. Phase Order and Rationale**

Ordered by value to you personally, not by technical dependency. The prediction ledger is first because every run you do right now is a future data point you are not capturing. Start logging immediately --- this is the only thing in this addendum that cannot be recreated retroactively.

  ----------------------------- ----------------------------------------------------------------------------------- ------------------------------------------------------------------------------
  **Phase**                     **What it adds**                                                                    **Why this order**
  A --- Prediction Ledger       Logs every run. Leaderboard with live YTD tracking.                                 Start NOW. Every un-logged run is a lost training example.
  B --- Growth Bet Extraction   Assumption sheet from filings. Words-vs-numbers alignment. Suggested entry price.   Highest-value analytical addition. Makes the verdict materially more useful.
  C --- Filings RAG Full        EdgarTools 10-K/10-Q/transcripts + insider + institutional signals.                 Populates the stub already wired. Enriches Phase B.
  D --- News Sentiment          Finnhub news. VADER scoring. Populates news stub.                                   Adds recency signal. 1--2 days to wire.
  E --- Price Efficiency        Reverse DCF: what CAGR does this price imply? Inflated/Fair/Conservative verdict.   Most actionable single addition to the verdict card.
  F --- Analyst Tracking        Passive call ingestion. Auto-grading. Accuracy leaderboard.                         Data compounds over 6--12 months. Start accumulating now.
  G --- Polymarket              Crowd signals on macro events. Populates the stub.                                  Low effort. Nice texture on macro section.
  H --- Redis + Calibration     Per-section TTL cache. Brier score feedback on scored predictions.                  Infrastructure. Do last.
  ----------------------------- ----------------------------------------------------------------------------------- ------------------------------------------------------------------------------

**Phase A --- Prediction Ledger & Leaderboard**

+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| **Why this is first**                                                                                                                                                                                                                                                                     |
|                                                                                                                                                                                                                                                                                           |
| You are already running analyses. Every run before this is built is a future data point without a label. The Karpathy feedback loop --- figuring out when your process works --- depends on this dataset. Start logging on day one of Phase A even if the leaderboard UI isn\'t done yet. |
+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+

**A.1 What to Log**

After PM synthesis completes, write one record to the predictions table. Capture everything true at the moment of the run --- not just the output but the inputs that generated it.

  ------------------------ --------------------- ------------------------------------------------------------------------------------------------
  **Field**                **Type**              **Notes**
  prediction\_id           uuid                  Primary key. Auto-generated.
  ticker                   string                As submitted
  run\_at                  ISO datetime          Timestamp of run
  entry\_price             number                Live price at run time --- always fresh yfinance fetch
  target\_cagr             number                User\'s target. Default 0.10.
  holding\_period\_years   int                   User\'s holding period. Default 5.
  horizon\_1yr\_date       date                  run\_at + 1 year --- when the 1-year grade triggers
  prob\_low / prob\_high   number                Probability band at user\'s holding period horizon
  confidence\_verdict      enum                  high\_confidence \| moderate\_confidence \| low\_confidence \| insufficient\_data
  verdict\_paragraph       string                Full text snapshot at time of run
  fair\_value\_base        number                DCF base case at time of run
  macro\_regime            string                Macro regime at time of run
  segment                  enum                  large\_cap\_blue\_chip \| mid\_cap \| small\_cap\_high\_vol
  nodes\_with\_data        JSON array            Which nodes returned real data vs. stub/null --- critical for later signal analysis
  outcome\_1yr             JSON object \| null   Null until graded. {grade\_date, realized\_price, realized\_cagr, outcome: hit\|miss\|partial}
  outcome\_notes           string \| null        Brief human note at grading time
  ------------------------ --------------------- ------------------------------------------------------------------------------------------------

**A.2 Storage --- SQLite to Start**

SQLite runs locally alongside the existing app with zero infrastructure setup. Migrate to PostgreSQL if you move to a server or when analyst tracking volume (Phase F) outgrows it.

> CREATE TABLE predictions (
>
> prediction\_id TEXT PRIMARY KEY,
>
> ticker TEXT NOT NULL,
>
> run\_at TEXT NOT NULL,
>
> entry\_price REAL NOT NULL,
>
> target\_cagr REAL NOT NULL,
>
> holding\_period\_years INT NOT NULL,
>
> horizon\_1yr\_date TEXT NOT NULL,
>
> prob\_low REAL,
>
> prob\_high REAL,
>
> confidence\_verdict TEXT,
>
> verdict\_paragraph TEXT,
>
> fair\_value\_base REAL,
>
> macro\_regime TEXT,
>
> segment TEXT,
>
> nodes\_with\_data TEXT, \-- JSON array
>
> outcome\_1yr TEXT, \-- JSON object, null until graded
>
> outcome\_notes TEXT
>
> );

**A.3 New API Endpoints**

  ------------ -------------------------- ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  **Method**   **Path**                   **Description**
  GET          /predictions/leaderboard   All predictions with live YTD. Returns: ticker, entry\_price, target\_cagr, ytd\_growth (live yfinance), required\_by\_year\_end, confidence\_verdict, status, days\_remaining.
  GET          /predictions               All raw records. Filterable by ticker, status, date range.
  GET          /predictions/:id           Single record with full context snapshot.
  POST         /predictions/:id/score     User submits outcome. Body: {realized\_price, thesis\_played\_out, notes}. Computes realized\_cagr, sets outcome\_1yr.
  GET          /predictions/due           Predictions where horizon\_1yr\_date \<= today + 14 days and not yet scored.
  ------------ -------------------------- ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

**A.4 Leaderboard UI**

Add a second nav tab to the existing frontend: \'My Predictions\'. YTD growth fetched live from yfinance on every leaderboard load --- not cached.

  ---------------------- ----------------------------------------------------------------------------------------------
  **Column**             **Notes**
  Ticker                 Clickable --- re-runs analysis
  Entry Price            Price at time of run
  Target                 e.g. 10% / 5yr
  YTD Growth             Live. Green if ahead of required pace, red if behind.
  Required by Year-End   Price return still needed to hit 1yr pace. Shrinks as year progresses.
  Confidence             Badge from original run: High / Moderate / Low
  Status                 on\_track \| at\_risk \| off\_track \| hit \| miss. Auto-computed from YTD vs required pace.
  Days Left              Days until 1yr horizon
  Score                  Button shown when days\_remaining \<= 14 or past horizon. Opens scoring modal.
  ---------------------- ----------------------------------------------------------------------------------------------

+-------------------------------------------------------------------------------------------------------------------------------------------------------------+
| **Status logic**                                                                                                                                            |
|                                                                                                                                                             |
| on\_track: YTD \>= 80% of time-weighted required pace. at\_risk: 50--79%. off\_track: \< 50% or negative. hit/miss: horizon passed and outcome\_1yr is set. |
+-------------------------------------------------------------------------------------------------------------------------------------------------------------+

**A.5 Grading Modal**

When a user opens the leaderboard and a prediction\'s horizon is due, show a \'Score this\' prompt inline. Clicking opens a simple modal: current price (auto-fetched), realized return (computed), and two optional text fields: \'Did the thesis play out?\' and \'Notes.\' Manual grading only --- you want 60 seconds of reflection before you submit. That reflection is part of the value.

**Phase B --- Growth Bet Extraction**

The highest-value analytical addition. Makes the existing verdict materially better by extracting management\'s explicit growth plan from their own words, then testing whether capital allocation matches the narrative.

+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| **What this adds to the verdict card**                                                                                                                                                                                                                                                                     |
|                                                                                                                                                                                                                                                                                                            |
| The verdict paragraph can now say: \'Management\'s stated bet is \[X\]. Their capital allocation \[confirms / contradicts\] this. The current price implies \[Y\]% annual revenue growth --- \[above / below\] what management themselves have guided.\' That is a meaningfully better verdict than today. |
+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+

**B.1 Node 6 --- Filings RAG + Growth Bet (Replace Stub)**

  ------------------------- -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  **Property**              **Detail**
  Library                   EdgarTools (pip install edgartools). Free, no API key. Run set\_identity(\'name\@email.com\') once via env config for EDGAR rate limiting.
  Filings fetched           Most recent 10-K: MD&A + Risk Factors. Most recent 10-Q: MD&A. Last 4 earnings call transcripts via Finnhub /stock/transcripts (free API key). Fallback: EdgarTools 8-K exhibits.
  Embedding                 Chunk text → sentence-transformers (already in stack) → ChromaDB (already integrated). Key: ticker + accession number. Re-embed only when new filing detected.
  Growth bet RAG queries    \(1\) Exact language of any multi-year targets or forward guidance stated by management. Quote directly. (2) Which segments, products, or geographies is management explicitly leaning into? (3) What does Liquidity & Capital Resources say about capex and R&D priorities? (4) In Q&A, how did management respond when analysts pushed back on the growth plan?
  Words vs. numbers check   Deterministic Python, no LLM. Pull R&D % of revenue (3yr trend) and capex % of revenue (3yr trend) from existing Fundamentals node output. If narrative claims AI/tech focus but R&D is flat or declining YoY: significant\_misalignment. If spend matches narrative direction: aligned.
  Assumption sheet          Claude Sonnet call --- not Haiku. This is the most important LLM call in the system. Synthesize RAG output into 5--8 explicit, falsifiable assumptions. Format: \[{assumption, dimension: market\|execution\|capital\|regulation\|competitive\|technology, linked\_metric, current\_evidence, fragility: robust\|moderate\|fragile}\]
  Max execution time        45 seconds. Sonnet on transcript + filings context is the bottleneck. Worth it.
  ------------------------- -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

**B.2 New Response Fields**

  ------------------------------- --------------------- ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  **Field**                       **Location**          **Notes**
  stated\_bet                     thesis.growth\_bet    1--2 sentences in management\'s own words. Extracted, not paraphrased.
  assumption\_sheet               thesis.growth\_bet    Array of 5--8 assumptions with dimension, linked\_metric, current\_evidence, fragility.
  words\_vs\_numbers\_alignment   thesis.growth\_bet    aligned \| partial\_misalignment \| significant\_misalignment
  alignment\_notes                thesis.growth\_bet    One specific sentence. E.g. \'R&D spend declined 4% YoY while management emphasized AI investment in every earnings call.\'
  implied\_revenue\_cagr\_5yr     valuation             Reverse DCF: the revenue CAGR the current price requires over 5 years at the current multiple.
  implied\_vs\_guidance           valuation             above\_guidance \| at\_guidance \| below\_guidance \| no\_guidance\_available
  efficiency\_verdict             valuation             appears\_inflated \| fairly\_priced \| appears\_conservative \| insufficient\_data
  efficiency\_notes               valuation             Plain English explanation of the verdict. Specific numbers required.
  suggested\_entry\_price         probability\_engine   Back-solved entry point. Populated only when efficiency\_verdict = appears\_inflated OR prob at user\'s horizon \< 40%. Format: {price, prob\_low, prob\_high, note}. Null otherwise.
  ------------------------------- --------------------- ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

**B.3 Verdict Card Updates**

-   Add words-vs-numbers alignment badge below the confidence badge: \'Narrative & capital aligned ✓\' or \'Capital allocation contradicts narrative ⚠\'

-   Add suggested entry price line: shown only when relevant. Hidden when current price is already fair or conservative.

Update the PM synthesis Sonnet prompt with: \'If assumption\_sheet is populated, reference the single most fragile assumption in the verdict paragraph. If words\_vs\_numbers\_alignment is significant\_misalignment, note it explicitly. If suggested\_entry\_price is set, include it in the verdict.\'

**B.4 Prediction Table --- Add Phase B Fields**

> ALTER TABLE predictions ADD COLUMN stated\_bet TEXT;
>
> ALTER TABLE predictions ADD COLUMN words\_vs\_numbers TEXT;
>
> ALTER TABLE predictions ADD COLUMN efficiency\_verdict TEXT;

These enable later analysis: did efficiency\_verdict = appears\_inflated predict worse 1yr outcomes? Did significant\_misalignment correlate with underperformance? Log it now --- the answer arrives in 12--18 months.

**Phase C --- Filings RAG Full Population**

Phase B fetches filings for growth bet extraction. Phase C adds the risk evolution queries and insider + institutional signals using EdgarTools --- all from the same EDGAR connection already established.

**C.1 Additional RAG Queries**

  ------------------------------------------------------------------- ----------------------------------------------
  **Query**                                                           **Output field**
  What new risk factors were added or expanded vs. prior year?        filings\_risk\_evolution.notable\_new\_risks
  Have accounting policies or revenue recognition changed?            filings\_risk\_evolution.accounting\_changes
  How does management describe competitive dynamics vs. prior year?   filings\_risk\_evolution.competitive\_notes
  ------------------------------------------------------------------- ----------------------------------------------

**C.2 Insider Transactions --- Form 4 via EdgarTools**

> from edgar import Company
>
> form4s = Company(ticker).get\_filings(form=\'4\').head(20)
>
> \# Returns Ownership objects with structured transaction details

Aggregate net shares bought/sold by executives + directors over 90 days. Classify as: net\_buying \| net\_selling \| neutral \| minimal\_activity. Output to sentiment.insider\_summary with signal\_strength (high: CEO/CFO buying \> \$500K, medium: multiple insiders same direction, low: small or mixed).

**C.3 Institutional Holdings --- 13F via EdgarTools**

> from edgar import get\_filings
>
> holdings = get\_filings(form=\'13F-HR\')\[0\].obj().holdings

Top 10 institutional holders by position size. Flag position increases \> 10% QoQ or new positions from a manually maintained Tier 1 fund list (20 names, JSON file). Output to sentiment.institutional\_summary.

**Phase D --- News Sentiment (Populate the Stub)**

The stub is wired. This is purely data population. Finnhub in, VADER sentiment + Haiku narrative clusters out.

  ---------------------- --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  **Property**           **Detail**
  Primary source         Finnhub /company-news. Free tier, 60 req/min. pip install finnhub-python. Set FINNHUB\_API\_KEY env var.
  Fallback               yfinance .news --- already in stack.
  Lookback               30 days.
  Sentiment              VADER (pip install vaderSentiment) on each headline + snippet. Average → news\_sentiment\_score (0--1, 0.5 neutral). No LLM.
  Narrative clustering   Claude Haiku. Input: top 20 items with VADER scores. Output: top\_narratives \[{label, sentiment, supporting\_examples}\] and recent\_catalysts \[{date, type, description, market\_reaction}\].
  Max execution time     15 seconds.
  ---------------------- --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

**Phase E --- Price Efficiency Completion**

Phases B already adds implied\_revenue\_cagr\_5yr and efficiency\_verdict. Phase E adds the sentiment premium flag --- the signal that a stock\'s price has run ahead of its actual business delivery.

**E.1 Sentiment Premium Flag --- Deterministic Python, No LLM**

-   trailing\_12m\_price\_return = (current\_price − price\_1yr\_ago) / price\_1yr\_ago

-   trailing\_12m\_eps\_growth = (ttm\_eps − prior\_year\_eps) / abs(prior\_year\_eps)

-   sentiment\_premium\_flag = trailing\_12m\_price\_return \> 2 × trailing\_12m\_eps\_growth

Both inputs already exist in the Fundamentals node output. When flagged, add sentiment\_premium\_notes: \'Stock has returned \[X\]% in 12 months while EPS grew \[Y\]%. The gap suggests price has been driven by narrative momentum, not fundamental delivery.\'

+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| **The practical signal**                                                                                                                                                                                                                                     |
|                                                                                                                                                                                                                                                              |
| This is the pattern where a company is genuinely great but the stock has run far ahead of the business. The flag makes that gap explicit rather than leaving you to notice it manually. It belongs in the verdict card as a one-line warning when triggered. |
+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+

**E.2 Historical Analog --- Optional**

A Sonnet call that identifies 1--2 comparable companies from the same sector that traded at similar valuations with similar growth profiles, and notes what happened over the following 3--5 years. Sources from Fundamentals historical data, not web search. Consider gating behind a \'Show historical analog\' UI toggle rather than running by default --- adds \~10 seconds and one Sonnet call.

**Phase F --- Analyst Tracking & Grading**

Logs every analyst call on every ticker you run, passively and automatically. Grades calls when outcomes arrive. Builds an accuracy leaderboard over time. The value compounds --- start accumulating data now even though meaningful accuracy stats won\'t exist for 6--12 months.

+----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| **The long game on analyst data**                                                                                                                                                                                                                                                                                                                                                      |
|                                                                                                                                                                                                                                                                                                                                                                                        |
| In 12 months you will know which analysts covering your names have actually been right, and which are systematically too bullish or too bearish. An analyst who has hit 70% of price targets in the semiconductor sector over 3 years is a meaningfully different signal than one at 35%. Right now the \'What the Street Says\' panel treats both identically. This phase fixes that. |
+----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+

**F.1 Analyst Call Ingestion --- Background Job**

  -------------- ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  **Property**   **Detail**
  Sources        FMP /analyst-stock-recommendations + /price-target (free tier, \~1000 req/day). Finnhub /stock/recommendation as deduplication check. Same analyst + firm + date = skip.
  Polling        Every 6 hours per tracked ticker. Tracked = all tickers ever run through the main analysis.
  What to log    analyst\_id (normalized: firm:analyst\_name lowercase), firm, ticker, call\_date, rating (normalized: buy\|outperform\|hold\|underperform\|sell), price\_target, price\_at\_call (live yfinance at ingest time), eps\_estimate if available.
  Backfill       On first ingest of a new ticker: pull last 3 years from FMP and Finnhub.
  Storage        New tables in the existing SQLite database (schema below).
  -------------- ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

> CREATE TABLE analyst\_calls (
>
> call\_id TEXT PRIMARY KEY,
>
> analyst\_id TEXT NOT NULL,
>
> firm TEXT NOT NULL,
>
> ticker TEXT NOT NULL,
>
> call\_date TEXT NOT NULL,
>
> rating TEXT NOT NULL,
>
> price\_target REAL,
>
> price\_at\_call REAL NOT NULL,
>
> eps\_estimate REAL,
>
> horizon\_1yr\_date TEXT NOT NULL,
>
> grade\_outcome TEXT,
>
> grade\_date TEXT,
>
> grade\_source TEXT
>
> );
>
> CREATE TABLE analyst\_records (
>
> analyst\_id TEXT PRIMARY KEY,
>
> firm TEXT,
>
> analyst\_name TEXT,
>
> total\_graded\_calls INT DEFAULT 0,
>
> price\_target\_hit\_rate REAL,
>
> directional\_accuracy REAL,
>
> eps\_accuracy REAL,
>
> bias\_score REAL,
>
> recency\_score REAL,
>
> last\_updated TEXT
>
> );

**F.2 Automatic Grading**

  ----------------------------------------------------------------------- -------------------------------------------------------------------------------------------------
  **Trigger**                                                             **Grade computed**
  Daily job --- 1yr horizon reached. Fetch current price from yfinance.   Price target: hit (within 10%), partial (within 20%), miss. Directional: correct/wrong/neutral.
  EdgarTools 8-K detection for earnings. Fetch actual EPS from filing.    EPS: hit (within 5%), partial (within 15%), miss.
  8-K M&A or delisting detected. Close all open calls for ticker.         Terminal: price\_at\_acquisition vs. price\_at\_call vs. price\_target.
  ----------------------------------------------------------------------- -------------------------------------------------------------------------------------------------

**F.3 Frontend --- Analyst Leaderboard Tab**

Add third nav tab: \'Analyst Track Record\'. Global table: Analyst/Firm \| Graded Calls (min 5 to appear) \| Target Hit Rate \| Directional Accuracy \| EPS Accuracy \| Bias badge \| Recency Score. Filterable by sector or ticker.

In the existing \'What the Street Says\' panel: show each tracked analyst\'s current call alongside their accuracy\_score badge. Compute weighted\_target\_price (weighted by recency\_score) and show it next to the raw avg\_target\_price with the delta flagged if \> 5%.

**Phase G --- Polymarket Signals (Populate the Stub)**

Stub is wired. Low effort --- the Polymarket API is public with no auth required. Primary work is creating and maintaining the polymarket\_markets.json mapping file.

  ------------------ ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  **Property**       **Detail**
  Source             Polymarket /markets API. Public, no auth.
  Mapping file       polymarket\_markets.json --- manually curated. Maps market slugs to (1) macro themes, (2) affected sectors. Seed with 15--20 markets: US recession, Fed funds rate, US CPI threshold, oil price range, China GDP. 30 minutes of work.
  Market selection   For a given ticker: use its sector + current macro\_regime to select the 3--5 most relevant markets from the mapping file.
  Liquidity filter   Only markets with open interest \> \$50K. Skip thin markets.
  Output             macro\_and\_crowd.polymarket\_signals: \[{market\_name, implied\_probability, direction\_for\_ticker, notes}\]. Haiku writes 1-sentence note per signal.
  Cache TTL          15 minutes.
  On failure         Return polymarket\_signals: \[\]. Do not fail the main analysis.
  ------------------ ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

**Phase H --- Redis Cache + Calibration Feedback**

Infrastructure. Do last. Nothing in Phases A--G requires it, but both make the system faster and smarter over time.

**H.1 Redis Caching**

Add Redis in front of all data node outputs. Cache key: ticker + node\_name + date bucket. Check cache before running any node. Write on completion. Add force\_refresh=true to request schema to bypass all reads.

  ---------------------------- --------------
  **Section**                  **TTL**
  current\_price               Never cached
  fundamentals                 24 hours
  valuation                    24 hours
  analyst\_estimates           6 hours
  news\_sentiment              30 minutes
  filings\_rag + growth\_bet   7 days
  insider\_transactions        24 hours
  institutional\_holdings      7 days
  macro                        1 hour
  polymarket                   15 minutes
  probability\_engine          1 hour
  ---------------------------- --------------

**H.2 Calibration Feedback**

Background job. Requires \>= 10 scored predictions per segment + macro\_regime combination before it activates. Heuristic weights are used until then. Meaningful calibration won\'t exist for 6--12 months --- do not fake precision before the data is there.

  ---------------------- -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  **Property**           **Detail**
  Trigger                Daily job. Runs when \>= 10 new scored outcomes exist for any segment/regime combo since last calibration.
  Brier score            (predicted\_probability − outcome\_binary)\^2 per prediction. Lower is better. Compute per segment, per regime, per horizon.
  Weight adjustment      If predictions are systematically overconfident, decrease bull weight, increase bear proportionally. Max ±5pp per run --- prevents overfitting on small samples.
  Signal correlation     At \>= 25 scored predictions: compute accuracy rate when each node had data vs. null (using nodes\_with\_data). Flag any node where presence correlates with \< 45% accuracy. Output to calibration\_report.json for your review.
  Output                 calibration\_overrides.json: {segment: {macro\_regime: {bull\_weight, base\_weight, bear\_weight, n\_predictions, brier\_score}}}. Probability engine reads this on startup.
  Minimum sample guard   Never apply overrides with fewer than 10 scored predictions. Always log sample size in calibration\_notes.
  ---------------------- -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| **What calibration tells you eventually**                                                                                                                                                                                                                                                                                                                        |
|                                                                                                                                                                                                                                                                                                                                                                  |
| The signal correlation report will show which of the 11 nodes actually correlates with accurate predictions versus which feel rigorous but don\'t move the needle. That finding --- in 12--18 months of scored data --- is the most valuable output of the entire system. It tells you which parts of your research process are real signal and which are noise. |
+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+

**Open Questions --- Resolve Before Starting**

  -------- --------------------------------------------------------------------------------------------------------------------------------------------------------- ------------
  **\#**   **Question**                                                                                                                                              **Blocks**
  1        EdgarTools: run set\_identity(\'name\@email.com\') as a one-time env config before Phase B/C.                                                             Phase B
  2        Finnhub: sign up for a free API key at finnhub.io. Set FINNHUB\_API\_KEY env var. 60 req/min is sufficient for single-user use.                           Phase D
  3        FMP: confirm the existing key covers /analyst-stock-recommendations and /price-target. These are on the free plan --- verify access.                      Phase F
  4        SQLite vs. PostgreSQL: SQLite is fine locally. Migrate before Phase F if moving to a server --- analyst tracking volume will eventually outgrow SQLite.   Phase A/F
  5        Polymarket mapping file: create polymarket\_markets.json manually before Phase G. 30 minutes of work.                                                     Phase G
  6        Redis: brew install redis locally. If deploying to a server, Redis Cloud free tier (30MB) is sufficient.                                                  Phase H
  -------- --------------------------------------------------------------------------------------------------------------------------------------------------------- ------------

**Summary --- What to Build Next**

+--------------------------------------------------------------------------------------------------------------------------------------------------+
| **The one non-negotiable**                                                                                                                       |
|                                                                                                                                                  |
| Start Phase A before anything else. Log every run from this point forward. The dataset is the only thing that cannot be recreated retroactively. |
+--------------------------------------------------------------------------------------------------------------------------------------------------+

  ----------------------------- ------------ --------------------------------------------------------------
  **Phase**                     **Effort**   **Value**
  A --- Prediction Ledger       1--2 days    Immediate --- every run is now a logged data point
  B --- Growth Bet Extraction   3--5 days    High --- materially better verdict
  C --- Filings RAG Full        2--3 days    Medium-high --- enriches Phase B, adds insider/institutional
  D --- News Sentiment          1--2 days    Medium --- recency signal, populates existing stub
  E --- Price Efficiency        1 day        High --- most actionable single verdict card addition
  F --- Analyst Tracking        4--6 days    Long-term high --- compounds over 6--12 months
  G --- Polymarket              1 day        Low-medium --- texture on macro section
  H --- Redis + Calibration     2--3 days    Infrastructure --- do last
  ----------------------------- ------------ --------------------------------------------------------------

*--- End of Addendum ---*
