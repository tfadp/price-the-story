**PRODUCT SPECIFICATION**

Long-Horizon Equity Research Assistant

Version 1.0 \| March 2026

Owner: Dan (Product)

Audience: Backend Dev Team, Quant/ML, Frontend Dev

**Status: Ready for Implementation**

**1. Executive Summary**

This tool answers one question: given a stock, a target annual return, and a holding period --- how confident should I be, and if the current price makes that return unlikely, what price would change the answer?

It is a buy-and-hold research tool for a single investor targeting long-duration positions, typically 5--10 years, with a 10% annual return as the default hurdle. It is not a trading tool, a portfolio manager, or a decision engine. It is a confidence assessment --- built on rigorous data, honest about uncertainty, and designed to treat the user as an intelligent adult who wants a clear verdict with the evidence behind it.

+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| **The core question this tool answers**                                                                                                                                                                            |
|                                                                                                                                                                                                                    |
| \"I am interested in \[TICKER\]. I want \[X%\] annually over \[N\] years. If I buy at today\'s price, how likely am I to get there? And if the answer is: not very --- what price should I be targeting instead?\" |
+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+

  --------------------- -----------------------------------------------------------------------------------------------------------------------------
  **Dimension**         **Decision**
  Latency target        30--90 seconds --- synchronous with SSE progress feedback
  Caching strategy      Per-section TTL: fundamentals/filings 24h, news/price 30 min. Always refresh current\_price. force\_refresh flag available.
  Access model          Single-user personal tool --- no auth required in v1
  Primary data          OpenBB (free tier) + yfinance. FMP free tier as analyst estimate fallback.
  Node failure policy   Return partial result; null failing section; log to dead-letter queue for retry
  Probability engine    Structured heuristic with scenario trees in v1; calibrated statistical model in v2
  Ticker universe       US equities only in v1. International tickers return a graceful unsupported message.
  Frontend              Verdict-first dashboard --- one-page narrative card as the hero, supporting detail panels secondary
  Default target CAGR   10% --- user can override. Reflects long-run equity market return as a reasonable hurdle.
  --------------------- -----------------------------------------------------------------------------------------------------------------------------

+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| **Explicit scope boundaries**                                                                                                                                                                                                                                                                                                |
|                                                                                                                                                                                                                                                                                                                              |
| This tool is NOT: a portfolio manager, a position-sizing tool, a trading signal generator, or an account-based service with persistent holdings. It answers a single question per ticker run. There are no accounts, no stored positions, no exit recommendations, and no portfolio-level analysis. Each run is independent. |
+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+

**2. Problem Statement**

Individual investors doing serious long-horizon research face a fragmented, time-consuming process. Forming a defensible view on a single stock requires reading filings, tracking analyst revisions, stress-testing management\'s growth claims, and comparing the current price against what the thesis actually requires. Most do some of this. Almost none do all of it systematically.

The bigger problem is that even investors who do the work often can\'t answer the one question that actually drives the decision: at today\'s price, with my target return and holding period, what are the realistic odds this works? Not a vague \'it looks cheap\' --- a structured, evidence-based confidence assessment against a specific numeric hurdle. And if the odds are poor, what price would change the answer?

This tool makes that question answerable in under 90 seconds. It compresses the research workflow, forces the growth narrative to be specific and testable, challenges the market\'s embedded assumptions, and produces a one-page verdict a disciplined investor can act on.

**3. User Stories**

  -------- ------------------------------------------ ---------------------------------------------------------------------- -----------------------------------------------------------------------------------
  **\#**   **As a buy-and-hold investor...**          **I want to...**                                                       **So that...**
  1        Evaluating a stock I\'ve heard about       Enter the ticker, my target return, and my holding period              I get a clear confidence assessment in under 90 seconds --- not a data dump
  2        Looking at a stock that seems expensive    See what return the current price actually implies                     I know whether the market has already priced in everything that needs to go right
  3        Interested but unsure about entry price    Get a specific suggested buy price if current price is unfavorable     I know what to pay, not just that the stock is \'overvalued\'
  4        Trying to understand the growth story      See management\'s stated bet tested against their capital allocation   I know whether the narrative and the numbers agree
  5        Worried about what could go wrong          See explicit stress tests on the key assumptions                       I understand which risks kill the thesis and which ones it survives
  6        Wanting to track my conviction over time   See my past analyses in a leaderboard with live return tracking        I know whether my confidence assessments have been accurate
  -------- ------------------------------------------ ---------------------------------------------------------------------- -----------------------------------------------------------------------------------

**4. User Experience Flow**

**4.1 Input**

Three fields. That is all the user sees. Ticker, target return, and optionally a specific entry price. Everything else is internal. The system never asks the user to configure a model, choose a data source, or set options. The default target CAGR is 10% --- reasonable for a long-hold investor --- and can be overridden.

  ------------------------ ------------------ -------------- ---------------------
  **Field**                **Type**           **Required**   **Default**
  ticker                   String             Yes            ---
  target\_cagr             Number (decimal)   No             0.10 (10%)
  entry\_price             Number (USD)       No             Current close price
  holding\_period\_years   Integer            No             5
  force\_refresh           Boolean            No             false
  ------------------------ ------------------ -------------- ---------------------

**4.2 Progress Feedback**

Upon submission the frontend connects to an SSE stream. Progress events arrive as each node completes. The user sees human-readable stages --- not technical node names.

+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| **Progress labels (user-facing)**                                                                                                                                         |
|                                                                                                                                                                           |
| \'Pulling financials\' → \'Reading filings & transcripts\' → \'Analyzing the growth story\' → \'Checking the price\' → \'Running stress scenarios\' → \'Writing verdict\' |
+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------+

**4.3 Output --- Verdict-First Layout**

The hero output is a single verdict card --- one page, narrative-first. It answers the core question in plain English, cites the key evidence, and tells the investor what the system thinks. Supporting detail panels sit below and are collapsible --- they are the evidence for the verdict, not the main event.

+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| **UI hierarchy principle**                                                                                                                                                                     |
|                                                                                                                                                                                                |
| The verdict card is what a trusted analyst would say to you on the phone. The detail panels are what they\'d hand you if you said \'show me your work.\' Conclusion first, evidence on demand. |
+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+

**4.3.1 Verdict Card --- The Hero (always visible, never collapsed)**

  ------------------------ -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- -------------------------------------------------------------
  **Element**              **Content**                                                                                                                                                                                                                                  **Source field**
  Confidence badge         High Confidence \| Moderate Confidence \| Low Confidence \| Insufficient Data                                                                                                                                                                probability\_engine.confidence\_tier + stress\_verdict
  Probability statement    \'We estimate a \[LOW\]--\[HIGH\]% probability of reaching your 10% annual target over 5 years at today\'s price of \$X.\' Ranges always, never point estimates.                                                                             probability\_engine.horizons\[5yr\]
  Suggested entry price    Only shown when price appears inflated or probability \< 40%: \'At \$\[PRICE\], probability rises to \[LOW\]--\[HIGH\]%.\' This is the back-solved entry point.                                                                              probability\_engine.suggested\_entry\_price
  Price efficiency badge   Inflated \| Fairly Priced \| Conservative --- one word, color coded. One line below: implied growth rate vs. management guidance.                                                                                                            valuation.price\_efficiency\_assessment.efficiency\_verdict
  Verdict paragraph        3--5 sentences written by the PM synthesis agent targeting this exact format: what is the bet, how credible is it, what is the price saying, and what would have to break badly for this to fail. No jargon. No hedging without substance.   pm\_synthesis.verdict\_paragraph
  Stress verdict badge     Robust \| Conditional \| Fragile --- color coded. One sentence naming the load-bearing assumption.                                                                                                                                           stress\_test.stress\_verdict
  Top 2 risks              The two highest-impact failure modes, each in one line.                                                                                                                                                                                      red\_flags\_and\_failure\_modes\[0:2\]
  Calibration note         Small, always present: \'Probability based on \[N\] scored predictions for this stock type.\' Counts toward credibility.                                                                                                                     probability\_engine.calibration\_notes
  ------------------------ -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- -------------------------------------------------------------

**4.3.2 Supporting Detail Panels --- Evidence, Not Story**

  ------------------------------- --------------------------------------------------------------------------------------
  **Panel label (user-facing)**   **Content**
  The Bet & The Evidence          Stated bet, assumption sheet, words-vs-numbers alignment, leading indicators
  What Breaks It                  Assumption shocks, mild vs. severe scenarios, balance sheet check under stress
  The Price                       Fair value band, implied growth rate vs. guidance, entry band, relative multiples
  What the Street Says            Tracked analysts with accuracy scores, weighted vs. raw consensus, revision trend
  What\'s Happening Now           News narratives, catalysts, insider activity, institutional holdings
  The Environment                 Macro regime, scenario impacts, Polymarket signals
  The Numbers in Detail           Full probability table by horizon, entry dependence, downside risk, scenario weights
  ------------------------------- --------------------------------------------------------------------------------------

**4.4 What the User Never Sees**

-   Raw API responses, node names, model names, or LangGraph details

-   Intermediate JSON, error stack traces, or backend infrastructure

-   Portfolio context, position sizing, exit recommendations, or account state

-   Configuration options --- the tool makes all technical decisions internally

**5. Technical Architecture**

**5.1 System Overview**

The system has four runtime layers: an intake layer (FastAPI + SSE), an orchestration layer (LangGraph), a data layer (OpenBB / yfinance / FMP / EDGAR / Polymarket), and a synthesis layer (tiered LLM strategy). Each layer is independently testable.

  ------------------- ---------------------------------------------- -------------------------------------------------------------- -----------------
  **Layer**           **Technology**                                 **Purpose**                                                    **Owner**
  Intake              FastAPI + SSE                                  Accept request, stream progress, return final JSON             Backend
  Orchestration       LangGraph (Python)                             Route execution across 11 nodes in parallel/series             Backend
  Data                OpenBB + yfinance + FMP + EDGAR + Polymarket   Fetch fundamentals, estimates, filings, macro, crowd signals   Backend / Quant
  RAG Store           ChromaDB (local)                               Embed + retrieve SEC filings and news chunks                   Backend / ML
  Summarization LLM   Claude Haiku or GPT-4o-mini                    Per-node text summarization (fast, cheap)                      Backend
  Synthesis LLM       Claude Sonnet (best available)                 Final PM-grade synthesis across all node outputs               Backend
  Cache               Redis (local or managed)                       Per-section TTL cache; dead-letter queue                       Backend
  Frontend            React + Next.js (App Router)                   Render output, SSE progress, input form                        Frontend
  ------------------- ---------------------------------------------- -------------------------------------------------------------- -----------------

**5.2 LangGraph Orchestration**

The orchestrator is a directed acyclic graph (DAG) of 11 nodes. Nodes 2--9 run in parallel after node 1 completes. Nodes 10 and 11 run sequentially after all parallel nodes complete. This parallel-first design is what makes 30--90 second latency achievable.

+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| **Execution order**                                                                                                                                                                            |
|                                                                                                                                                                                                |
| Node 1 (Classifier) → Parallel fan-out: Nodes 2--9 → Node 10 (Probability Engine) → Node 11 (PM Synthesis). Total wall-clock time is dominated by the slowest parallel node plus PM synthesis. |
+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+

  ---------- -------------------- ------------------------------------ --------------------------------------------------------- --------------------------
  **Node**   **Name**             **Inputs**                           **Outputs**                                               **Runs**
  1          Ticker Classifier    ticker, metadata                     segment, segment\_confidence, data\_quality               First (gates all others)
  2          Fundamentals         ticker, segment                      business\_summary, time series, factor scores             Parallel
  3          Valuation            fundamentals output, current price   fair value band, entry bands, method summary              Parallel
  4          Analyst Estimates    ticker                               consensus path, revision trend, rating summary            Parallel
  5          News & Sentiment     ticker                               narrative clusters, sentiment score, catalysts            Parallel
  6          Filings RAG          ticker                               risk evolution, new risks, accounting changes             Parallel
  7          Themes / Graph       ticker, sector                       long-term thematic mapping, exposure strengths            Parallel
  8          Macro                macro indicators                     regime classification, scenario impacts                   Parallel
  9          Polymarket           ticker, macro regime                 crowd probability signals, liquidity flags                Parallel
  10         Probability Engine   nodes 1--9 outputs                   CAGR probability bands, entry dependence, downside risk   After parallel fan-out
  11         PM Synthesis         all node outputs                     Final structured JSON (full response schema)              Last
  ---------- -------------------- ------------------------------------ --------------------------------------------------------- --------------------------

**6. Data Sources & Fallback Strategy**

**6.1 Source Priority Map**

Every data category has a primary source and at least one fallback. The system logs which source was used for each section and surfaces this in the debug payload. Users never see source attribution --- only the data\_quality field reflects any degradation.

  ------------------------------- ---------------------------------------------------- -------------------------------------------- --------------------------------------- ----------------------------------------------------------
  **Data category**               **Primary**                                          **Fallback 1**                               **Fallback 2**                          **On total failure**
  Price / metadata                yfinance                                             OpenBB market data                           ---                                     Fail request entirely --- price is required
  Fundamentals (10yr)             OpenBB                                               yfinance financials                          FMP /financial-statements               Return section null; downgrade data\_quality
  Analyst estimates               FMP /analyst-estimates (free)                        OpenBB AnalystEstimates                      yfinance info.recommendations           Return coverage\_level: low; omit consensus path
  News & sentiment                Finnhub /company-news (free)                         OpenBB news endpoint                         yfinance .news                          Return section null; note in disclaimers
  Earnings call transcripts       Finnhub /stock/transcripts (free)                    EarningsCall.biz API (low paid tier)         FMP /earning\_call\_transcript (paid)   Omit transcript layer; note in filings\_risk\_evolution
  SEC filings (10-K/10-Q)         EdgarTools Python lib (free, no key)                 EDGAR full-text search API direct            ---                                     Return section null; flag in filings\_risk\_evolution
  Insider transactions (Form 4)   EdgarTools Company.get\_filings(form=\'4\') (free)   Finnhub /stock/insider-transactions (free)   ---                                     Omit insider signals; note in sentiment section
  Institutional holdings (13F)    EdgarTools get\_filings(form=\'13F-HR\') (free)      ---                                          ---                                     Omit institutional signals; note in sentiment section
  Options market data             yfinance .option\_chain() (free)                     ---                                          ---                                     Omit options IV input to probability engine; widen bands
  Macro indicators                OpenBB FRED connector                                yfinance proxies (TLT, DXY, GLD, VIX)        ---                                     Return macro\_regime: unknown; disable scenario impacts
  Polymarket signals              Polymarket /markets API                              ---                                          ---                                     Return polymarket\_signals: \[\]; note in disclaimers
  ------------------------------- ---------------------------------------------------- -------------------------------------------- --------------------------------------- ----------------------------------------------------------

+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| **yfinance reliability note**                                                                                                                                                                                                                                                                                         |
|                                                                                                                                                                                                                                                                                                                       |
| yfinance is technically a scraper of Yahoo Finance with no official API or SLA. It breaks periodically, especially after Yahoo HTML changes. All yfinance calls must have a 10-second timeout and be wrapped in try/except with immediate fallback. Never use yfinance as the sole source for any critical data path. |
+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+

**6.3 New Sources Added --- Reference & Cost**

Three source additions were identified after initial spec review. All are free or low-cost and materially improve output quality in the sections that matter most for long-horizon research: management tone, insider behavior, and institutional conviction.

  --------------------------- ----------------------------------------------------------------------------------------------------------------------------------------- ------------------------------------------------------------- ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  **Source**                  **What it provides**                                                                                                                      **Cost**                                                      **Integration notes**
  Finnhub (free tier)         Company news, earnings call transcripts, insider sentiment, ESG scores. 60 req/min free.                                                  Free                                                          pip install finnhub-python. Use for news sentiment (node 5) and transcripts (node 6). Single API key, no card required for free tier.
  EdgarTools (open source)    Structured Python objects for ALL EDGAR form types: 10-K, 10-Q, Form 4 insider trades, 13F institutional holdings. No API key required.   Free / open source                                            pip install edgartools. Replaces raw EDGAR HTTP calls in node 6. Add Form 4 + 13F parsing to filings RAG node with \~20 lines of code.
  EarningsCall.biz API        Purpose-built transcript API: speaker-segmented, Q&A split from prepared remarks, 5yr history, 5,000+ companies. Python + JS SDKs.        \~\$10--25/mo est. (verify at earningscall.biz/api-pricing)   Use only if Finnhub transcript coverage proves insufficient for target tickers. Speaker segmentation enables better LLM prompting --- CEO vs CFO vs analyst Q&A are distinct signals.
  yfinance .option\_chain()   Options chain: strikes, IV, volume, open interest, put/call ratio. Already a dependency.                                                  Free (already in stack)                                       Wire implied volatility surface into node 10 probability engine as an optional calibration sanity check. If market IV \> scenario tree band, widen output bands accordingly.
  --------------------------- ----------------------------------------------------------------------------------------------------------------------------------------- ------------------------------------------------------------- ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

**6.2 Caching Strategy**

The cache is Redis-backed with per-section TTLs. The cache key is built from ticker + section name. On cache hit, the system skips the corresponding node and injects the cached value directly into the graph state. A force\_refresh=true flag on the request bypasses all cache reads for that run but still writes fresh values on completion.

  ------------------------- ------------------ -----------------------------------------------------------------------------------------------------------------------------------
  **Section**               **TTL**            **Rationale**
  current\_price            0 (never cached)   Price must always be live --- it gates entry band and probability calculations
  fundamentals              24 hours           Revenue/EPS history changes only at earnings; daily refresh is sufficient
  valuation                 24 hours           Derived from fundamentals; changes only when fundamentals do
  analyst\_estimates        6 hours            Revisions can happen intraday; 6h is a reasonable middle ground
  news\_sentiment           30 minutes         News cycle moves fast; stale sentiment is misleading
  filings\_rag              7 days             10-K/10-Q filings are quarterly; weekly refresh is safe. Transcripts cached per accession number --- re-embed only on new filing.
  insider\_transactions     24 hours           Form 4 filings are event-driven; daily refresh catches new transactions promptly
  institutional\_holdings   7 days             13F filings are quarterly; weekly refresh is sufficient
  themes\_graph             7 days             Thematic mapping is structural, not event-driven
  macro                     1 hour             Macro regime classification should track intraday moves
  polymarket                15 minutes         Prediction market odds move continuously around events
  probability\_engine       1 hour             Derived from above; should refresh when macro or price refresh
  ------------------------- ------------------ -----------------------------------------------------------------------------------------------------------------------------------

**7. API Specification**

**7.1 Endpoints**

  ------------ ----------------------------------------- -----------------------------------------------------------------------------------------------------------------
  **Method**   **Path**                                  **Description**
  POST         /analyze-ticker                           Submit a ticker for full analysis. Returns final JSON on completion.
  GET          /analyze-ticker/stream?ticker=AAPL&\...   SSE stream for real-time progress events during analysis.
  GET          /health                                   Health check. Returns {status: ok, version: string}.
  GET          /cache/status?ticker=AAPL                 Returns cache hit/miss status and TTLs for each section of a given ticker.
  POST         /cache/invalidate                         Force-invalidates cache for a given ticker and optional section list.
  GET          /analysts/leaderboard                     Global analyst leaderboard by accuracy score. Filterable by sector, firm, ticker.
  GET          /analysts/:analyst\_id                    Full analyst record with call history and graded outcomes.
  GET          /analysts/:analyst\_id/calls              Paginated call history. Filterable by ticker, grade status.
  GET          /analysts/pending-grades                  Open calls where grading trigger has fired. Admin/debug view.
  GET          /analysts/grades/recent                   Most recently graded calls across all analysts and tickers.
  GET          /predictions/leaderboard                  Returns leaderboard: all active predictions with ticker, 1yr target, YTD growth, status, and on-track flag.
  POST         /predictions/log                          Auto-called after every analysis run. Logs prediction with full context snapshot and review horizon timestamps.
  GET          /predictions/review                       Returns predictions due for scoring in the next 30 days, sorted by horizon date.
  POST         /predictions/score                        User submits outcome scores for matured predictions. Triggers calibration recalculation.
  GET          /predictions/calibration                  Returns calibration curve: predicted probability vs. realized frequency, by segment and horizon.
  GET          /predictions/:id                          Returns full prediction record including context snapshot and any scored outcomes.
  ------------ ----------------------------------------- -----------------------------------------------------------------------------------------------------------------

**7.2 Request Schema --- POST /analyze-ticker**

> {
>
> \"ticker\": \"AAPL\", // required; US exchange symbol
>
> \"target\_cagr\": 0.10, // optional; decimal. Default: 0.10
>
> \"entry\_price\": 180.0, // optional; USD. Default: current close
>
> \"horizons\": \[1, 3, 5, 10\], // optional; years. Default: \[1,3,5,10\]
>
> \"preferences\": {
>
> \"risk\_focus\": \"balanced\", // \"conservative\"\|\"balanced\"\|\"aggressive\"
>
> \"theme\_depth\": \"standard\", // \"standard\"\|\"deep\"
>
> \"language\": \"en-US\"
>
> },
>
> \"force\_refresh\": false, // bypass cache reads for this run
>
> \"debug\": false // include raw factor scores & model versions
>
> }

**7.3 Response Schema (Top Level)**

  --------------------------------- ------------------- ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  **Field**                         **Type**            **Notes**
  ticker                            string              As submitted
  as\_of                            ISO 8601 datetime   Timestamp of analysis completion
  segment                           enum                large\_cap\_blue\_chip \| mid\_cap \| small\_cap\_high\_vol \| other
  segment\_confidence               enum                high \| medium \| low
  data\_quality                     enum                high \| medium \| low --- reflects worst section data quality
  verdict\_paragraph                string              HERO OUTPUT. 3--5 sentences: what is the bet, how credible, what does the price say, what would break it badly. Written in plain English by PM synthesis agent. No jargon.
  confidence\_verdict               enum                high\_confidence \| moderate\_confidence \| low\_confidence \| insufficient\_data --- drives the verdict card badge
  thesis                            object              See §7.4 --- includes growth\_bet sub-object
  valuation                         object              See §7.5 --- includes price\_efficiency\_assessment
  analysts                          object              See §7.6 --- includes tracked\_analysts with accuracy scores
  sentiment                         object              See §7.7
  macro\_and\_crowd                 object              See §7.8
  probability\_engine               object              See §7.9 --- includes suggested\_entry\_price
  stress\_test                      object              See §7.11
  red\_flags\_and\_failure\_modes   array\<object\>     See §7.10. Sorted by impact + likelihood descending. First two surface in verdict card.
  section\_statuses                 object              Map of section → {status, ttl\_used, source\_used, cached}
  hallucination\_check              object              {validated\_at, numbers\_checked, numbers\_matched, numbers\_flagged, overall\_status: clean\|warnings\|blocked}
  disclaimers                       array\<string\>     Static + dynamic legal/coverage disclaimers
  debug                             object \| null      Populated only when debug=true
  --------------------------------- ------------------- ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------

**7.4 thesis object**

  ----------------------------- ----------------- -------------------------------------------------------------------------------
  **Field**                     **Type**          **Notes**
  business\_summary             string            2--3 sentence description of business model and revenue/earnings mix
  long\_term\_themes            array\<object\>   {name, strength: high\|medium\|low, horizon: 0-3y\|3-5y\|5-10y, notes}
  five\_to\_ten\_year\_thesis   string            Narrative view of the investment case over the full horizon
  key\_drivers                  array\<object\>   {driver, direction: positive\|negative\|mixed, importance: high\|medium\|low}
  ai\_and\_disruption\_notes    string            Specific commentary: beneficiary, threatened, or neutral
  growth\_bet                   object            See below --- extracted from management\'s own words and capital allocation
  ----------------------------- ----------------- -------------------------------------------------------------------------------

**7.4.1 growth\_bet sub-object**

This is the core forward-looking section. It extracts management\'s explicit growth plan from their own disclosures, then tests it against what they are actually funding. A growth story where the narrative and the capital allocation disagree is a red flag, not a thesis.

  ------------------------------- ----------------- ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  **Field**                       **Type**          **Notes**
  stated\_bet                     string            1--3 sentence summary of the specific forward claim management is making. Extracted from MD&A, investor day, and earnings call prepared remarks. Written in their words, not analyst interpretation.
  bet\_category                   enum              TAM\_expansion \| market\_share\_gain \| new\_product \| geographic\_expansion \| cost\_structure \| regulatory\_catalyst \| sector\_tailwind \| platform\_network\_effect
  assumption\_sheet               array\<object\>   See §7.4.2 --- the 5--10 explicit assumptions that must be true for the bet to pay off
  words\_vs\_numbers\_alignment   enum              aligned \| partial\_misalignment \| significant\_misalignment --- does capital allocation match the stated narrative?
  alignment\_notes                string            Specific evidence of alignment or contradiction between narrative and resource allocation. E.g., \'Company claims AI focus but R&D spend flat YoY while SG&A grew 22%.\'
  leading\_indicators             array\<object\>   {indicator, description, current\_reading, direction: improving\|deteriorating\|stable, source} --- sector/company-specific signals that precede earnings
  bet\_credibility\_score         enum              high \| medium \| low --- assessed from capital consistency, early contract evidence, competitive dynamics, management track record
  credibility\_notes              string            Plain-English explanation of credibility rating
  implied\_growth\_in\_price      number            Revenue CAGR that current valuation multiple implies. If above management guidance, market has already priced the bet. If below, there may be upside.
  ------------------------------- ----------------- ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

**7.4.2 assumption\_sheet items**

Each item in assumption\_sheet is a specific, falsifiable condition extracted from MD&A and earnings call language. This is the investment\'s load-bearing wall --- if these assumptions break, the growth story breaks.

  ------------------- ---------- ----------------------------------------------------------------------------------------------------------------------
  **Field**           **Type**   **Notes**
  assumption          string     Plain-English statement: what must be true? E.g., \'Data center power demand grows \>20% annually through 2028.\'
  dimension           enum       market \| company\_execution \| capital \| external\_cost \| regulation \| competitive \| technology
  linked\_metric      string     The observable metric that tests this assumption. E.g., \'EIA grid capacity data; hyperscaler capex announcements.\'
  current\_evidence   string     What the data currently shows about this assumption --- confirming, neutral, or challenging.
  fragility           enum       robust \| moderate \| fragile --- how much does the overall thesis degrade if this assumption breaks?
  tracking\_source    string     Where to monitor this assumption going forward. Must be a real, accessible data source.
  ------------------- ---------- ----------------------------------------------------------------------------------------------------------------------

**7.4.3 stress\_test object --- §7.11**

The stress test section applies deliberate shocks to each assumption in the assumption\_sheet and re-runs the forward model. See §7.11 for full schema.

**7.5 valuation object**

  -------------------------------- ---------- ---------------------------------------------------------------------------
  **Field**                        **Type**   **Notes**
  current\_price                   number     Always live --- never cached
  currency                         string     USD for v1 (US equities only)
  fair\_value\_low / base / high   number     DCF + multiples blended range
  valuation\_method\_summary       string     Human-readable explanation of methodology used
  relative\_valuation              object     {sector\_median\_pe, company\_forward\_pe, percentile\_vs\_sector}
  suggested\_entry\_band           object     {accumulate\_below, strong\_buy\_below, notes}
  price\_efficiency\_assessment    object     See §7.5.1 --- is the current price justified, inflated, or conservative?
  -------------------------------- ---------- ---------------------------------------------------------------------------

**7.5.1 price\_efficiency\_assessment sub-object**

Rather than treating the current price as a neutral input, this section asks: what growth rate is baked into this price, and is that growth rate achievable? This is where the system pushes back on inflated prices and confirms conservative ones. The goal is not to call the stock cheap or expensive --- it is to make the market\'s embedded assumption explicit and then test it.

  ----------------------------------- ---------- -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  **Field**                           **Type**   **Notes**
  implied\_revenue\_cagr\_5yr         number     The revenue CAGR that must be achieved over 5 years to justify the current price at the current multiple. Derived from reverse DCF using current EV and terminal multiple assumptions.
  implied\_vs\_management\_guidance   enum       above\_guidance \| at\_guidance \| below\_guidance \| no\_guidance\_available --- is the market pricing above or below what management said?
  implied\_vs\_stress\_base           enum       above\_base \| at\_base \| below\_base --- is the market pricing above the base case in the stress test? If so, the stock requires everything to go right.
  implied\_vs\_stress\_bear           enum       above\_bear \| at\_bear \| below\_bear --- is the market pricing above even the bear case? If so, the stock is pricing perfection.
  efficiency\_verdict                 enum       appears\_inflated \| fairly\_priced \| appears\_conservative \| insufficient\_data
  efficiency\_notes                   string     Plain-English explanation. E.g.: \'Current price implies 24% revenue CAGR over 5 years. Management guided mid-teens. Even the bull scenario in the stress test only reaches 21%. The price is pricing above the bull case --- any miss creates meaningful downside.\'
  sentiment\_premium\_flag            boolean    True if the stock\'s trailing 12-month return significantly exceeds its earnings growth --- suggests price is driven by narrative momentum rather than fundamental delivery. Threshold: price return \> 2x earnings growth.
  sentiment\_premium\_notes           string     Populated when sentiment\_premium\_flag is true. Notes the divergence magnitude and how long it has persisted.
  historical\_analog                  string     Optional: LLM identifies 1--2 comparable companies that traded at similar valuations with similar growth profiles, and notes what happened to them over the following 3--5 years. Sourced from fundamentals history. Used as a sanity check, not a prediction.
  ----------------------------------- ---------- -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

**7.6 analysts object**

  --------------------------- ----------------- -----------------------------------------------------------------------------------------------------------------------------------
  **Field**                   **Type**          **Notes**
  coverage\_level             enum              high \| medium \| low
  consensus\_growth\_path     object            {years: \[{year, eps\_estimate, revenue\_estimate}\]}
  revision\_trend             enum              up \| flat \| down
  surprise\_history           array\<object\>   \[{quarter, eps\_surprise\_pct, revenue\_surprise\_pct}\]
  rating\_summary             object            Raw counts: {buy: int, hold: int, sell: int}. Note: treat as low-signal without track record weighting --- see tracked\_analysts.
  avg\_target\_price          number            Unweighted consensus. Compare against weighted\_target\_price from tracked\_analysts for signal quality.
  weighted\_target\_price     number \| null    Consensus price target weighted by each analyst\'s historical accuracy score. Null if insufficient track record data.
  analyst\_sentiment\_notes   string            LLM-written summary of street sentiment. Cites source node.
  tracked\_analysts           array\<object\>   See §7.6.1 --- individual analyst records with track records
  --------------------------- ----------------- -----------------------------------------------------------------------------------------------------------------------------------

**7.6.1 tracked\_analysts items**

Each analyst who has made a call on this ticker is tracked individually. Their historical accuracy --- on price targets, EPS estimates, and directional calls --- is the lens through which their current rating should be read. An analyst who has been right 70% of the time on this sector in the past 3 years is a different signal from one who has been right 35% of the time.

  ------------------------------ ----------------- ----------------------------------------------------------------------------------------------------------
  **Field**                      **Type**          **Notes**
  analyst\_id                    string            Unique ID: firm\_name:analyst\_name normalized
  analyst\_name                  string            
  firm                           string            
  current\_rating                enum              buy \| outperform \| hold \| underperform \| sell
  current\_price\_target         number            
  target\_date                   date              When target was set
  accuracy\_score                number \| null    0--1. Null if fewer than 5 graded calls. Computed from graded\_calls history.
  sector\_accuracy\_score        number \| null    Accuracy score specific to this sector --- an analyst may be sharp on semiconductors and poor on retail.
  directional\_accuracy\_pct     number \| null    \% of past calls where buy/sell direction was correct at 1yr.
  price\_target\_accuracy\_pct   number \| null    \% of past price targets hit within 10% of stated target.
  eps\_accuracy\_pct             number \| null    \% of past EPS estimates within 5% of actual reported.
  graded\_calls\_count           int               Number of fully graded calls in history
  recent\_calls                  array\<object\>   Last 5 calls: \[{date, rating, price\_target, price\_at\_call, grade: hit\|miss\|partial\|pending}\]
  ------------------------------ ----------------- ----------------------------------------------------------------------------------------------------------

**7.7 sentiment object**

  -------------------------- ----------------- ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  **Field**                  **Type**          **Notes**
  news\_sentiment\_score     number            Normalized 0--1. 0.5 = neutral.
  news\_lookback\_days       int               Number of days of news ingested
  top\_narratives            array\<object\>   \[{label, sentiment: positive\|negative\|mixed, supporting\_examples: \[string\]}\]
  recent\_catalysts          array\<object\>   \[{date, type: earnings\|guidance\|product\|regulatory\|macro, description, market\_reaction: {one\_day\_return\_pct}}\]
  filings\_risk\_evolution   object            {summary, notable\_new\_risks: \[string\], risks\_downgraded\_or\_removed: \[string\]}
  insider\_summary           object            {net\_activity: net\_buying\|net\_selling\|neutral\|minimal\_activity, lookback\_days: 90, notable\_transactions: \[{name, role, shares, type: buy\|sell, date}\], signal\_strength: high\|medium\|low}
  institutional\_summary     object            {top\_holders: \[{name, pct\_held, qoq\_change\_pct}\], notable\_changes: \[string\], tier1\_activity: increasing\|decreasing\|stable\|unknown}
  -------------------------- ----------------- ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

**7.8 macro\_and\_crowd object**

  --------------------------- ----------------- -------------------------------------------------------------------------------------------------------------------------
  **Field**                   **Type**          **Notes**
  macro\_regime               string            Controlled vocab: disinflation \| sticky\_inflation \| higher\_for\_longer\_rates \| recession \| goldilocks \| unknown
  macro\_regime\_confidence   enum              high \| medium \| low
  scenario\_impacts           array\<object\>   \[{scenario, impact\_on\_business: string, impact\_direction: positive\|negative\|neutral}\]
  polymarket\_signals         array\<object\>   \[{market\_name, implied\_probability, direction\_for\_ticker: positive\|negative\|neutral, notes}\]
  --------------------------- ----------------- -------------------------------------------------------------------------------------------------------------------------

**7.9 probability\_engine object**

  ------------------------- ----------------- ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  **Field**                 **Type**          **Notes**
  enabled                   boolean           False for low-confidence small caps
  reason\_disabled          string \| null    Plain-text explanation when enabled=false
  confidence\_tier          enum              high \| medium \| low
  horizons                  array\<object\>   \[{years, prob\_ge\_target\_low, prob\_ge\_target\_high}\] --- band narrows for blue chips
  suggested\_entry\_price   object \| null    The back-solved answer to \'what should I pay?\' {price, prob\_ge\_target\_low, prob\_ge\_target\_high, note}. Populated when efficiency\_verdict = appears\_inflated OR prob at current price \< 40% at the user\'s holding\_period\_years horizon. Null otherwise.
  entry\_dependence         array\<object\>   \[{entry\_price, years, prob\_ge\_target\_low, prob\_ge\_target\_high}\]
  downside\_risk            array\<object\>   \[{years, prob\_le\_zero\_cagr\_low, prob\_le\_zero\_cagr\_high}\]
  calibration\_notes        string            Explains scenario weights, calibration source, and sample size. Shown in verdict card as small text.
  ------------------------- ----------------- ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

**7.10 red\_flags\_and\_failure\_modes**

  ------------- ---------- ----------------------------------------------------------------------------------------------
  **Field**     **Type**   **Notes**
  category      enum       execution \| balance\_sheet \| competitive \| regulatory \| macro \| valuation \| governance
  description   string     Plain-English explanation of how this failure mode plays out
  likelihood    enum       low \| medium \| high
  impact        enum       low \| medium \| high
  ------------- ---------- ----------------------------------------------------------------------------------------------

**7.11 stress\_test object**

Applies deliberate shocks to the assumption\_sheet and re-runs the forward model under each scenario. Each shock is tied to a specific assumption from §7.4.2. The output shows which assumptions are fragile vs. robust, and whether the investment case survives realistic stress.

  ------------------------ ----------------- --------------------------------------------------------------------------------------------------------
  **Field**                **Type**          **Notes**
  base\_case\_summary      string            Management/consensus forward model: revenue CAGR, margin path, implied EPS and FCF at 3yr and 5yr.
  shocks                   array\<object\>   See below --- one shock object per key assumption tested
  fragile\_assumptions     array\<string\>   Assumptions where even mild shock causes thesis failure --- extracted automatically from shock results
  robust\_assumptions      array\<string\>   Assumptions where severe shock still leaves acceptable returns
  stress\_verdict          enum              robust \| conditional \| fragile --- overall thesis resilience rating
  stress\_verdict\_notes   string            Plain-English summary: what kills this investment vs. what survives?
  ------------------------ ----------------- --------------------------------------------------------------------------------------------------------

**7.11.1 shock items**

  ----------------------- ---------- ----------------------------------------------------------------------------------------------------
  **Field**               **Type**   **Notes**
  assumption\_tested      string     Which assumption from assumption\_sheet this shock targets
  variable                string     The specific variable being shocked. E.g., \'sector revenue growth rate\'
  mild\_shock             object     {description, delta: string, revenue\_impact\_pct, margin\_impact\_bps, thesis\_survives: boolean}
  severe\_shock           object     {description, delta: string, revenue\_impact\_pct, margin\_impact\_bps, thesis\_survives: boolean}
  balance\_sheet\_check   string     Can the company fund the plan under severe shock without distress? Based on net debt / FCF stress.
  return\_under\_mild     string     Approximate CAGR achievable if mild shock materializes, at current entry price.
  return\_under\_severe   string     Approximate CAGR achievable if severe shock materializes, at current entry price.
  ----------------------- ---------- ----------------------------------------------------------------------------------------------------

**8. LangGraph Node Specifications**

**8.1 Node 1 --- Ticker Classifier**

The first node to execute. Its output gates all downstream nodes, so it must be fast. Failure here fails the entire request --- there is no fallback.

  ---------------------- ----------------------------------------------------------------------------------------------------------------------------------------------------------------
  **Property**           **Detail**
  Data sources           yfinance .info (market cap, history, volume, volatility); OpenBB metadata
  Outputs                segment ∈ {large\_cap\_blue\_chip, mid\_cap, small\_cap\_high\_vol, other}; segment\_confidence; data\_quality; is\_us\_equity (bool)
  Classification logic   large\_cap\_blue\_chip: market cap \>\$50B + 10yr history + daily vol \>\$500M. mid\_cap: \$2--50B cap. small\_cap\_high\_vol: \<\$2B or annualized vol \>60%.
  Non-US tickers         Return HTTP 422 with {error: \'unsupported\_ticker\', message: \'International tickers are not supported in v1.\'}
  Max execution time     5 seconds
  ---------------------- ----------------------------------------------------------------------------------------------------------------------------------------------------------------

**8.2 Node 2 --- Fundamentals**

Fetches and structures a 10+ year time series of financial history. Output feeds both Valuation (node 3) and the Probability Engine (node 10).

  -------------------- ----------------------------------------------------------------------------------------------------------------------------------
  **Property**         **Detail**
  Primary source       OpenBB obb.equity.fundamental.\* endpoints
  Fallback 1           yfinance .financials, .balance\_sheet, .cashflow
  Fallback 2           FMP /financial-statements endpoints
  Time series fields   revenue, gross\_margin, operating\_margin, net\_income, EPS, free\_cash\_flow, net\_debt, ROIC --- annual, 10yr where available
  Factor scores        value (P/E + P/FCF vs sector median), quality (ROIC + margin stability), growth (5yr revenue + EPS CAGR) --- all normalized 0--1
  LLM task             Haiku/mini summarizes time series into business\_summary string (2--3 sentences, no model hallucination on numbers)
  Max execution time   15 seconds
  -------------------- ----------------------------------------------------------------------------------------------------------------------------------

**8.3 Node 3 --- Valuation**

Computes fair value using a blended DCF and forward multiples approach. Does not call an LLM --- all computation is deterministic Python.

  -------------------- ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  **Property**         **Detail**
  Inputs               Node 2 fundamentals output; current price (always live from yfinance)
  DCF parameters       Base case: analyst consensus revenue growth (3yr), then mean revert to 3% terminal. Discount rate: risk-free (FRED 10yr) + equity risk premium (4.5% default). Terminal multiple: sector median EV/EBITDA.
  Multiples approach   Forward P/E and EV/EBITDA vs sector median (OpenBB screen or FMP). Blended 50/50 with DCF for base case.
  Output bands         low = bear case (-20% growth vs base, +1pp discount rate); base = central case; high = bull case (+20% growth, -1pp rate)
  Entry band logic     accumulate\_below = fair\_value\_base \* 0.90; strong\_buy\_below = fair\_value\_low \* 0.95
  LLM task             None --- valuation\_method\_summary is template-filled from parameter values, not LLM-generated
  Max execution time   10 seconds
  -------------------- ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

**8.4 Node 4 --- Analyst Estimates**

  -------------------- ----------------------------------------------------------------------------------------------------------------------------------------------
  **Property**         **Detail**
  Primary source       FMP /analyst-estimates and /price-target endpoints (free tier)
  Fallback 1           OpenBB obb.equity.estimates.consensus
  Fallback 2           yfinance .recommendations + .earnings\_forecasts
  On total failure     Return coverage\_level: low; omit consensus\_growth\_path; analyst\_sentiment\_notes: \'Analyst estimate data unavailable for this ticker.\'
  LLM task             Haiku/mini generates analyst\_sentiment\_notes (2 sentences) from rating counts + revision trend + surprise history
  Max execution time   10 seconds
  -------------------- ----------------------------------------------------------------------------------------------------------------------------------------------

**8.5 Node 5 --- News & Sentiment**

Fetches recent news, embeds chunks into ChromaDB, and uses RAG + LLM to extract narrative clusters and sentiment score.

  ---------------------- -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  **Property**           **Detail**
  Primary source         Finnhub /company-news endpoint (free tier, 60 req/min). Broader coverage and more reliable than OpenBB news for US equities.
  Fallback 1             OpenBB obb.news.company endpoint
  Fallback 2             yfinance .news
  Lookback window        30 days default
  Processing             Chunk headlines + snippets → embed (OpenAI text-embedding-3-small or local sentence-transformers) → store in ChromaDB → LLM clusters into top\_narratives
  Sentiment scoring      VADER or FinBERT on each headline; average normalized score → news\_sentiment\_score
  Insider signal (new)   Finnhub /stock/insider-transactions as supplementary signal: net insider buying/selling over 90 days → feeds insider\_sentiment field in sentiment object. Backed by EdgarTools Form 4 as primary (see node 6).
  LLM task               Haiku/mini takes top 20 news chunks + VADER scores → identifies top\_narratives, recent\_catalysts, sentiment label, and insider\_sentiment summary
  Max execution time     20 seconds (network + embedding)
  ---------------------- -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

**8.6 Node 6 --- Filings RAG + Growth Bet Extraction**

This node does two distinct jobs: (1) the existing filings risk extraction, and (2) the growth bet extraction --- pulling management\'s explicit forward claims and testing them against capital allocation data. The second job is what generates the assumption\_sheet and the words\_vs\_numbers\_alignment assessment.

  --------------------------------- ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  **Property**                      **Detail**
  Primary EDGAR client              EdgarTools Python lib. Parses 10-K, 10-Q, Form 4, 13F, and 8-K (investor day exhibits) into structured Python objects.
  Filings scope                     Most recent 10-K + most recent 10-Q (MD&A, Risk Factors, Liquidity & Capital Resources, Outlook sections). Last 4 earnings call transcripts (Finnhub primary, EarningsCall.biz fallback). Most recent 8-K investor day exhibit if available. Form 4 last 90 days. Most recent 13F-HR.
  Growth bet RAG queries            \(1\) What explicit forward guidance or multi-year targets did management state? Quote the language. (2) What segments, geographies, or products is management explicitly leaning into? (3) What does the Liquidity & Capital Resources section say about capex and R&D priorities? (4) What does the capex/R&D spend trend show vs. the stated narrative? (5) In earnings call Q&A, how did management respond when analysts pushed back on the growth plan?
  Risk / assumption extraction      \(6\) What new or expanded risk factors could derail the stated plan? (7) What does management treat as an implicit assumption --- stated as \'we expect\' or \'assuming\' in MD&A?
  Words vs. numbers check           Pull R&D % of revenue (3yr trend) and capex % of revenue (3yr trend) from fundamentals node. If company claims AI/cloud bet but R&D is flat or declining, flag as significant\_misalignment. If language matches spend trajectory, flag as aligned. Deterministic rule --- no LLM.
  Assumption sheet generation       LLM task (Sonnet, not Haiku --- this is the highest-leverage extraction in the system): synthesize RAG results into 5--10 explicit assumptions with dimension, linked metric, fragility estimate, and tracking source. Each assumption must be falsifiable.
  Leading indicators                LLM maps each assumption to 1--2 observable leading indicators that precede earnings impact. Source must be real and accessible (e.g., EIA data, FCC filings, App Store rank, patent database). Flag any assumption where no leading indicator can be identified --- that assumption is untrackable.
  Insider + institutional signals   EdgarTools Form 4 → 90-day net insider activity. EdgarTools 13F → top 10 holders with QoQ change. Classified and summarized as before.
  Embedding store                   ChromaDB keyed by ticker + accession number. Growth bet extraction results cached with filings\_rag TTL (7 days). Re-run only when new filing detected.
  Max execution time                45 seconds (Sonnet for assumption sheet is the bottleneck --- worth it)
  --------------------------------- ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

**8.7 Node 7 --- Themes / Graph**

Maps the company to a set of long-term structural themes using a lightweight in-memory graph. No external API call --- runs from a maintained theme taxonomy file.

  -------------------- -------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  **Property**         **Detail**
  Theme taxonomy       Maintained as themes.json: {theme\_name, keywords, sectors, example\_tickers}. Dev team seeds with 20--30 themes; updated manually as needed.
  Mapping logic        Score ticker against each theme using: SIC/sector match, keyword overlap in business\_summary (node 2), and analyst estimate notes. Threshold: score \> 0.3 to include.
  Output               long\_term\_themes array with name, strength (score band → low/medium/high), and horizon estimate
  LLM task             Haiku/mini writes a 1-sentence note per theme if theme\_depth = deep
  Max execution time   5 seconds (no network)
  -------------------- -------------------------------------------------------------------------------------------------------------------------------------------------------------------------

**8.8 Node 8 --- Macro**

  ----------------------- ----------------------------------------------------------------------------------------------------------------------------------------------------------------------
  **Property**            **Detail**
  Primary source          OpenBB FRED connector: 10yr yield, Fed funds rate, CPI, ISM, unemployment
  Fallback                yfinance proxies: TLT (rates), DXY (dollar), GLD (inflation), VIX (risk)
  Regime classification   Rule-based: map current yield curve + CPI trend + ISM reading → macro\_regime enum. No LLM.
  Scenario impacts        Pre-built scenario impact matrix per sector (sectors.json): maps {scenario, sector} → impact\_direction + template description. LLM fills in ticker-specific detail.
  LLM task                Haiku/mini personalizes scenario\_impacts descriptions for the specific company using business\_summary
  Max execution time      12 seconds
  ----------------------- ----------------------------------------------------------------------------------------------------------------------------------------------------------------------

**8.9 Node 9 --- Polymarket**

  -------------------- ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  **Property**         **Detail**
  Source               Polymarket /markets API (public, no auth)
  Ticker mapping       Maintained mapping file: polymarket\_markets.json maps market slugs to (1) macro themes, (2) affected sectors. Ticker\'s sector + macro\_regime used to select relevant markets. No dynamic LLM mapping in v1.
  Liquidity filter     Only include markets with open interest \> \$50K to avoid noise
  LLM task             Haiku/mini writes 1-sentence notes on direction\_for\_ticker for each signal
  On API failure       Return polymarket\_signals: \[\]; add disclaimer: \'Polymarket signals unavailable at time of analysis.\'
  Max execution time   8 seconds
  -------------------- ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

**8.10 Node 10 --- Probability Engine + Stress Test**

v1 uses a structured heuristic / scenario tree. Critically, scenario weights are now driven by the assumption\_sheet from node 6 --- not generic macro regime alone. A thesis with 3 fragile assumptions gets different scenario weights than one with 3 robust assumptions. This is the Karpathy feedback: as predictions mature and are scored, calibration\_overrides.json adjusts these weights based on historical accuracy.

+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| **v1 Design Decision --- Assumption-Driven Scenarios**                                                                                                                                                                                                                                                                                                                                                                                                      |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| Scenario weights are no longer generic (bull/base/bear at fixed ratios). They are modulated by: (1) fragility count in assumption\_sheet, (2) words\_vs\_numbers\_alignment, (3) bet\_credibility\_score, and (4) macro\_regime. A company with 4 fragile assumptions, significant capital misalignment, and a high-rate macro regime gets a bear weight of 35%, not 20%. This makes the probability output meaningfully different from generic DCF ranges. |
+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+

  ---------------------------- ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  **Property**                 **Detail**
  Inputs                       segment, fair\_value band, factor scores, assumption\_sheet (fragility counts), words\_vs\_numbers\_alignment, bet\_credibility\_score, analyst consensus path, revenue growth trajectory, macro regime, Polymarket signals, options IV (optional)
  Scenario weight derivation   Base weights: bull 35%, base 45%, bear 20%. Adjustments: each fragile assumption shifts +3pp to bear. significant\_misalignment shifts +8pp to bear. bet\_credibility low adds +5pp to bear. macro\_regime higher\_for\_longer adds +5pp to bear. All adjustments cap at bear weight of 50%.
  Stress test execution        For each assumption in assumption\_sheet: apply mild and severe shock parameters (defined by LLM in node 6), re-run 3yr and 5yr forward model, compute revenue/margin/EPS impact, flag thesis\_survives boolean. Output populates stress\_test object (§7.11).
  Price path model             For each scenario: apply revenue CAGR consistent with assumption\_sheet base case → margin path from fundamentals trend → terminal multiple from relative valuation → implied price vs entry\_price \* (1 + target\_cagr)\^years.
  Options IV calibration       Fetch 1yr ATM IV from yfinance. If market IV \> scenario tree implied vol by \>15pp, widen output bands by one tier. Add iv\_vs\_model\_delta to calibration\_notes.
  Band width by segment        large\_cap\_blue\_chip: ±4--6pp (±7--9pp if IV override). mid\_cap: ±8--12pp. small\_cap\_high\_vol: disabled.
  Calibration override         On startup, load calibration\_overrides.json (written by offline calibration node). If sufficient scored predictions exist for this segment/regime combo, use calibrated weights instead of heuristic weights. Log which was used in calibration\_notes.
  signals\_present map         Log which of nodes 2--9 returned real data vs. null for this run. Stored in prediction record for later correlation analysis --- identifies which nodes contribute real signal vs. noise over time.
  Max execution time           8 seconds (stress test adds computation but no network)
  ---------------------------- ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

**8.11 Node 11 --- PM Synthesis Agent**

The final node and the most important. verdict\_paragraph and confidence\_verdict are the primary outputs --- everything else is supporting JSON. The prompt is designed to produce the kind of clear, honest, intelligent assessment a trusted senior analyst would give you verbally. Not a research note. Not a disclaimer-laden hedge. A verdict.

  ------------------------------- ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  **Property**                    **Detail**
  Model                           Claude Sonnet (or current best long-context model). Never use the summarizer model here.
  Primary output                  verdict\_paragraph (string) and confidence\_verdict (enum). These two fields are what the user actually reads. The rest of the JSON is supporting evidence for the detail panels.
  Verdict paragraph prompt        Write 3--5 sentences. Answer this question directly: at today\'s price of \$\[X\], targeting \[CAGR\]% annually over \[N\] years, how confident should this investor be --- and why? Be specific about the growth bet. Be honest about what the price is implying. Be plain about the primary risk. Write like a trusted friend with deep expertise. No jargon. No boilerplate. No hedging without substance. No buy/sell language. Treat the reader as intelligent.
  Confidence verdict derivation   high\_confidence: probability \> 50% at target horizon AND stress\_verdict = robust. moderate\_confidence: probability 35--50% OR stress\_verdict = conditional. low\_confidence: probability \< 35% OR stress\_verdict = fragile. insufficient\_data: probability engine disabled or data\_quality = low.
  Number grounding rules          \(1\) Only use numbers from the number\_registry provided --- never generate, estimate, or extrapolate independently. (2) Tag every quantitative claim with \[source:node\_name\]. (3) If a number is not in the registry, write \'data unavailable.\' (4) The verdict\_paragraph must not contain a number that cannot be traced to a node output.
  Post-synthesis validation       Deterministic Python: extract all numbers from output via regex, cross-reference against number\_registry within 2% tolerance. Mismatches \> 2 trigger retry with stricter prompt. Still failing: return with hallucination\_check.overall\_status: blocked. hallucination\_check is always populated --- clean or not.
  Input format                    All node outputs as structured JSON + number\_registry flat list. LLM instructed explicitly: only use numbers from this registry.
  Output format                   Strict JSON. verdict\_paragraph and confidence\_verdict are top-level string fields. PM agent must not add or remove schema fields.
  Red flags                       PM agent generates red\_flags\_and\_failure\_modes from synthesis across all nodes. Sort by impact + likelihood. First two surface in verdict card automatically.
  Max execution time              35 seconds including post-synthesis validation
  On failure                      Retry once with simplified prompt. If second failure: verdict\_paragraph = \'Synthesis unavailable --- full data available in detail panels below.\' confidence\_verdict = insufficient\_data. All data node outputs returned in full.
  ------------------------------- ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

**9. Error Handling & Dead-Letter Queue**

**9.1 Node Failure Policy**

Individual node failures do not fail the request. Each node follows the fallback chain defined in §6.1. If all fallbacks are exhausted, the node returns a null section with a status code and feeds that status into section\_statuses in the response.

  ------------------------------ -------------------------------------------------------------------------------------------------
  **Node type**                  **On failure behavior**
  Node 1 (Classifier)            Hard fail --- return HTTP 500 with error details. No partial result.
  Nodes 2--9 (data nodes)        Return null for that section. Log to dead-letter queue. Continue with remaining nodes.
  Node 10 (Probability Engine)   Disable probability engine (enabled=false). Explain in reason\_disabled. Continue to synthesis.
  Node 11 (PM Synthesis)         Retry once. If still failing, return all data node outputs raw with synthesis\_status: failed.
  ------------------------------ -------------------------------------------------------------------------------------------------

**9.2 Dead-Letter Queue**

Every failed node execution is written to a Redis list (dlq:failed\_nodes) with the following payload. A background worker processes the DLQ independently --- it does not block the response. Results from DLQ retries are written to cache for the next request.

> {
>
> \"ticker\": \"AAPL\",
>
> \"node\": \"news\_sentiment\",
>
> \"failed\_at\": \"2026-03-14T20:08:00Z\",
>
> \"error\": \"OpenBB news endpoint timeout after 20s\",
>
> \"fallbacks\_attempted\": \[\"openbb\_news\", \"yfinance\_news\"\],
>
> \"retry\_after\": \"2026-03-14T20:38:00Z\" // 30 min
>
> }

**9.3 section\_statuses Response Field**

Every response includes a section\_statuses object so the frontend can render appropriate UI states (loading spinner, partial data warning, unavailable badge).

> \"section\_statuses\": {
>
> \"fundamentals\": {\"status\": \"ok\", \"source\": \"openbb\", \"cached\": true, \"ttl\_remaining\_s\": 72400},
>
> \"news\_sentiment\": {\"status\": \"partial\", \"source\": \"yfinance\", \"cached\": false, \"ttl\_remaining\_s\": null},
>
> \"polymarket\": {\"status\": \"failed\", \"source\": null, \"cached\": false, \"ttl\_remaining\_s\": null}
>
> }

**10. Frontend Specification (React / Next.js)**

**10.1 Tech Stack**

  --------------- ------------------------------ ----------------------------------------------------------------------------------
  **Component**   **Choice**                     **Notes**
  Framework       Next.js 14 (App Router)        Server components for SEO-irrelevant parts; client components for interactive UI
  Language        TypeScript                     Strict mode. All API response types must be typed against the JSON schema.
  Styling         Tailwind CSS                   No external component library in v1 --- keep the dependency surface minimal
  Charts          Recharts                       Valuation band visualization and probability horizon chart
  SSE client      Native EventSource API         No polling --- use the /stream endpoint for progress feedback
  State           React useState + useReducer    No Redux. Local state is sufficient for a single-page tool.
  Build           Vercel or Node.js standalone   Deploy wherever appropriate for single-user use
  --------------- ------------------------------ ----------------------------------------------------------------------------------

**10.2 Page Structure**

Single page. Two views accessible from a minimal top nav: Analysis (default) and Leaderboards. No routing beyond that. The analysis view is verdict-first --- the verdict card is always visible and fully rendered before any detail panel. Detail panels are collapsed by default and labeled as evidence, not as sections.

  -------------------------- --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  **Component**              **Description**
  InputForm                  Three fields: ticker, target return (default 10%), holding period (default 5yr). Optional entry price override. One button. No other controls visible.
  ProgressRail               Human-readable stage tracker: \'Pulling financials → Reading filings → Analyzing growth story → Checking the price → Running stress scenarios → Writing verdict.\' Hidden until request is in flight.
  VerdictCard                THE HERO --- always visible, never collapsed. Contains: confidence badge (color-coded), probability statement with range, suggested entry price (shown only when relevant), price efficiency badge + one-line implied growth note, verdict paragraph (3--5 sentences), stress verdict badge + one-sentence load-bearing assumption, top 2 risk lines, calibration note in small text at bottom. This is the product. Everything else is supporting evidence.
  DetailPanels (container)   Sits below VerdictCard. Contains all supporting panels in collapsed state by default. Header reads: \'See the evidence behind this verdict.\' Each panel has a user-facing label matching §4.3.2.
  GrowthBetPanel             Label: \'The Bet & The Evidence\'. Stated bet (quoted from filings), assumption sheet as a table with fragility indicators, words-vs-numbers alignment badge, leading indicators list.
  StressTestPanel            Label: \'What Breaks It\'. Base case summary, shock table per assumption (mild/severe columns, thesis\_survives color), fragile vs. robust lists, stress verdict with notes.
  ValuationPanel             Label: \'The Price\'. Fair value band chart, implied growth rate vs. guidance vs. stress base, entry band, relative multiples. Sentiment premium flag shown if triggered.
  AnalystPanel               Label: \'What the Street Says\'. Tracked analysts sorted by sector accuracy score --- each shows current call, accuracy badge, recent call history. Weighted consensus vs. raw consensus shown with delta. Revision trend.
  SentimentPanel             Label: \'What\'s Happening Now\'. News narratives, recent catalysts, insider activity badge, institutional holdings summary.
  MacroPanel                 Label: \'The Environment\'. Macro regime badge, scenario impacts, Polymarket signals.
  ProbabilityPanel           Label: \'The Numbers in Detail\'. Full horizon table, entry dependence, downside risk, scenario weights, calibration source note.
  AnalystLeaderboard         Second nav view. Global analyst leaderboard: Rank \| Analyst/Firm \| Sector \| Graded Calls \| Target Hit Rate \| Directional Accuracy \| EPS Accuracy \| Bias \| Recency Score. Filterable by sector or ticker.
  PredictionLeaderboard      Part of Leaderboards view. Table: Ticker \| Entry Price \| 1-Yr Target \| YTD Growth \| Required \| Stated Bet \| Stress Verdict \| Status \| Days Left.
  PredictionScoringModal     Triggered at horizon dates. Brief prompt: did thesis play out, which assumptions broke, any surprises. Submits to /predictions/score.
  DisclaimersFooter          Always visible. Two lines maximum. Static legal disclaimer + dynamic data coverage note.
  -------------------------- --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

**10.3 SSE Progress Flow**

On submit, the frontend first opens an EventSource to /analyze-ticker/stream with query params. The ProgressRail updates as events arrive. When the stream closes, the frontend fires the POST to /analyze-ticker (which reads from cache --- the run is already complete) and renders results.

+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| **Implementation note**                                                                                                                                                                                                                                            |
|                                                                                                                                                                                                                                                                    |
| The /stream endpoint runs the full LangGraph graph and writes each node result to cache as it completes. The subsequent POST /analyze-ticker returns immediately from cache. This avoids duplicate computation and gives clean SSE semantics without long-polling. |
+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+

**10.4 Probability Panel --- Visualization Detail**

The probability panel deserves explicit spec because the data is unfamiliar to most users. Implementation requirements:

-   Display probability bands as ranges (low--high), never as point estimates. A single number implies false precision.

-   Label the confidence tier (high/medium/low) prominently --- this is the most important context for reading the numbers.

-   Entry dependence table: rows are entry prices (current, -10%, -20%), columns are horizons. Color-coded: green \>50%, yellow 30--50%, red \<30%.

-   When enabled=false, show a clear card: \'Probability engine disabled for this ticker --- insufficient data confidence for meaningful probability bands.\'

-   Include calibration\_notes as a collapsible \'How is this calculated?\' tooltip --- not buried, but not in the way.

**11. Analyst Tracking, Grading & Leaderboard**

Wall Street analysts make thousands of calls per year. Almost none of them are systematically graded. This section defines the infrastructure that logs every analyst call passively and automatically, scores it when outcomes arrive, and surfaces a ranked leaderboard of analyst accuracy. The result is a track-record-weighted view of analyst consensus --- not just head counts of buy/hold/sell ratings, but a quality-adjusted signal.

+----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| **Design principle**                                                                                                                                                                                                                                                 |
|                                                                                                                                                                                                                                                                      |
| An analyst at a major firm who has been right on semiconductor price targets 68% of the time in the past 3 years is a very different signal from one who has been right 31% of the time. The current consensus system treats both identically. This system does not. |
+----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+

**11.1 Analyst Call Ingestion (Passive & Automatic)**

Every time a new analyst rating or price target is published for any tracked ticker, the system logs it automatically. No user action required. Sources are polled on a schedule. The ingestion runs as a background job independent of the real-time analysis graph.

  ------------------ -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  **Property**       **Detail**
  Primary source     FMP /analyst-stock-recommendations and /price-target endpoints. Polled every 6 hours per tracked ticker.
  Secondary source   Finnhub /stock/recommendation. Polled as a deduplication check --- if same analyst/firm/date exists in FMP, skip. If new, ingest.
  Tertiary source    OpenBB obb.equity.estimates.analyst\_estimates. Used to backfill historical calls on first ingest of a new ticker.
  What is logged     Analyst name, firm, ticker, call date, rating (normalized to buy\|outperform\|hold\|underperform\|sell), price target (if stated), price at time of call (live yfinance fetch at ingest time), EPS estimate if included, 1yr and 2yr horizon flags.
  Deduplication      Composite key: analyst\_id + ticker + call\_date. Prevents double-logging if same call appears in multiple sources.
  Ticker scope       All tickers ever analyzed by the system. Analyst tracking activates automatically when a ticker is first run through the main analysis graph.
  Backfill depth     On first ingest: pull last 3 years of historical calls. FMP and Finnhub both support this.
  ------------------ -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

**11.2 Automatic Grading Triggers**

Grading runs automatically on a schedule and on specific event triggers. No user action required. When a grade is computed, the prediction record is updated and the analyst\'s accuracy scores are recomputed.

  --------------------------------------------------- -------------------------------------------------------------------------------------------------------------------------------------------------------- ------------------------------------------------------------------------------------------------------------------------------------------
  **Trigger**                                         **What runs**                                                                                                                                            **Grade computed**
  Earnings reported (8-K filed)                       EdgarTools detects new 8-K for tracked ticker. Fetch actual EPS and revenue from filing. Compare against any open EPS estimates from tracked analysts.   EPS grade: hit (within 5%), partial (within 15%), miss (\>15% off). Revenue grade same thresholds.
  Price target horizon reached (1yr from call date)   Daily job checks all calls where call\_date + 365 days \<= today and grade is pending. Fetch current price from yfinance.                                Price target grade: hit (price within 10% of target), partial (within 20%), miss (\>20% off or wrong direction).
  Directional grade (1yr)                             Same daily job. Compare current price vs. price\_at\_call.                                                                                               Directional grade: correct (buy and price up \>5%, or sell and price down \>5%), wrong (opposite), neutral (within 5% either direction).
  Earnings surprise check                             When EPS is reported, compute analyst\'s estimate vs. actual. Log surprise magnitude.                                                                    EPS surprise grade: surprise magnitude in %, direction (beat/miss), analyst\'s prior call vs. consensus.
  Early termination (M&A, delisting)                  8-K detection for acquisition or delisting events. All open calls for that ticker are graded as closed with a terminal\_event flag.                      Grade method: price\_at\_acquisition vs. price\_at\_call vs. price\_target. Direction and magnitude computed.
  --------------------------------------------------- -------------------------------------------------------------------------------------------------------------------------------------------------------- ------------------------------------------------------------------------------------------------------------------------------------------

**11.3 Analyst Record Schema**

Each analyst has a persistent record across all tickers they cover. Accuracy scores are computed rolling --- the most recent 3 years of graded calls are weighted more heavily than older ones.

  -------------------------------- ----------------- ---------------------------------------------------------------------------------------------------------------------------------------------------------------
  **Field**                        **Type**          **Notes**
  analyst\_id                      string            firm\_name:analyst\_name normalized (lowercase, underscores)
  analyst\_name                    string            
  firm                             string            
  tickers\_covered                 array\<string\>   All tickers this analyst has made calls on
  sectors\_covered                 array\<string\>   Derived from ticker universe
  total\_graded\_calls             int               All-time graded call count
  overall\_accuracy\_score         number            0--1. Weighted average across price target, directional, and EPS accuracy. Null if \< 5 graded calls.
  accuracy\_by\_sector             object            {sector: accuracy\_score} --- identifies where analyst is strong vs. weak
  price\_target\_hit\_rate         number            \% of price targets hit within 10% at 1yr horizon
  directional\_accuracy            number            \% of buy/sell calls correct in direction at 1yr
  eps\_accuracy                    number            \% of EPS estimates within 5% of actual
  avg\_price\_target\_error\_pct   number            Mean absolute % error on price targets --- magnitude of miss regardless of direction
  bias\_score                      number            -1 to +1. Positive = systematically bullish vs. outcome. Negative = systematically bearish. Computed from (predicted direction - realized direction) average.
  recency\_weighted\_score         number            Same as accuracy\_score but last 12 months only. More predictive for current calls.
  call\_history                    array\<object\>   All logged calls with grade status. Paginated in API response.
  -------------------------------- ----------------- ---------------------------------------------------------------------------------------------------------------------------------------------------------------

**11.4 Analyst Leaderboard Endpoints**

  ------------ ----------------------------------- -------------------------------------------------------------------------------------------------------------------------------------------
  **Method**   **Path**                            **Description**
  GET          /analysts/leaderboard               Global analyst leaderboard sorted by overall\_accuracy\_score. Filterable by sector, firm, min\_graded\_calls. Returns top 50 by default.
  GET          /analysts/leaderboard?ticker=AAPL   Analyst leaderboard filtered to analysts who cover AAPL, sorted by sector\_accuracy for AAPL\'s sector.
  GET          /analysts/:analyst\_id              Full analyst record with complete call history and graded outcomes.
  GET          /analysts/:analyst\_id/calls        Paginated call history for a specific analyst. Filterable by ticker, sector, grade status.
  GET          /analysts/pending-grades            All open calls where grade trigger has fired but grade not yet computed. Admin/debug view.
  GET          /analysts/grades/recent             Most recently graded calls across all analysts and tickers. Useful for monitoring grading pipeline health.
  ------------ ----------------------------------- -------------------------------------------------------------------------------------------------------------------------------------------

**11.5 Analyst Leaderboard UI**

The analyst leaderboard is a standalone view, accessible from the main nav. It is also embedded contextually in the AnalystPanel of any ticker analysis --- showing the tracked\_analysts for that ticker ranked by their sector accuracy score, with their current call and track record side by side.

  -------------------------------- -------------------------------------------------------------------------------------------
  **Column**                       **Notes**
  Rank                             By overall\_accuracy\_score (minimum 10 graded calls to appear)
  Analyst / Firm                   Name and firm. Clickable to full analyst record.
  Sector                           Primary sector coverage
  Graded Calls                     Total count --- filters out analysts with too few calls to be meaningful
  Price Target Hit Rate            \% of targets hit within 10% at 1yr
  Directional Accuracy             \% of buy/sell calls right in direction
  EPS Accuracy                     \% of EPS estimates within 5% of actual
  Bias                             Bull / Bear / Neutral badge --- derived from bias\_score
  Current Call (ticker-specific)   Shown when filtered to a ticker. Rating + price target + date set + days until 1yr grade.
  Recency Score                    Last 12 months only --- most predictive for weighting current calls
  -------------------------------- -------------------------------------------------------------------------------------------

+----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| **Weighted consensus**                                                                                                                                                                                                                                                                                                                                                                             |
|                                                                                                                                                                                                                                                                                                                                                                                                    |
| When viewing a ticker\'s analyst panel, the system computes a weighted\_target\_price: the price target consensus weighted by each analyst\'s recency\_weighted\_score. An analyst with a 0.70 accuracy score contributes 2x the weight of one with a 0.35 score. This is surfaced alongside the raw avg\_target\_price so the user can see whether high-accuracy analysts diverge from the crowd. |
+----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+

**12. Prediction Ledger, Leaderboard & Calibration Feedback**

Every analysis run produces a prediction. The prediction ledger logs it with full context. The leaderboard surfaces it. The calibration feedback loop scores it when outcomes arrive and feeds the results back into the probability engine\'s scenario weights. This is the Karpathy feedback loop: the system learns from its own track record.

**11.1 Prediction Leaderboard**

The leaderboard is the top-of-page summary view: one row per active prediction, showing whether the 1-year growth target is on track in real time. It is not a ranking of winners and losers --- it is a live accuracy dashboard.

  ---------------------- -------------------- ---------------------------------------------------------------------------------------------------------------
  **Column**             **Type**             **Notes**
  Ticker                 string               Stock symbol. Clickable --- opens full analysis.
  Entry Price            number               Price at time of analysis run. Always the live price at logging time.
  1-Yr CAGR Target       number               The target\_cagr input for that run. Shown as % (e.g., 10%).
  YTD Growth             number               Price return from entry date to today. Updated live via yfinance on every leaderboard load. Shown as %.
  Required by Year-End   number               Price growth still needed to hit the 1yr target, annualized from today. Shrinks as the year progresses.
  Stated Bet             string (truncated)   First sentence of growth\_bet.stated\_bet. Hover for full text.
  Stress Verdict         enum badge           robust \| conditional \| fragile --- from stress\_test.stress\_verdict. Color coded: green / yellow / red.
  Status                 enum badge           on\_track \| at\_risk \| off\_track \| completed\_hit \| completed\_miss. Computed from YTD vs required pace.
  Days Remaining         int                  Days until 1-year horizon date.
  Prediction Date        date                 When the analysis was run.
  ---------------------- -------------------- ---------------------------------------------------------------------------------------------------------------

+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| **Status logic**                                                                                                                                                                                                                           |
|                                                                                                                                                                                                                                            |
| on\_track: YTD growth is \>= 80% of the time-weighted required pace. at\_risk: YTD is 50--80% of required pace. off\_track: YTD is below 50% of required pace or price is negative. completed\_hit / completed\_miss: horizon date passed. |
+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+

**11.2 Prediction Record Schema**

Every prediction is logged automatically after each analysis run. The record captures the full context snapshot at prediction time --- not just the output but every input signal. This is critical for the calibration feedback loop: you need to know not just what you predicted, but what you believed when you predicted it.

  ------------------------------- ----------------- --------------------------------------------------------------------
  **Field**                       **Type**          **Notes**
  prediction\_id                  uuid              Primary key
  ticker                          string            
  run\_at                         ISO datetime      When analysis was run
  entry\_price                    number            Live price at run time --- always fresh
  target\_cagr                    number            User-specified hurdle
  horizon\_dates                  object            {yr1, yr3, yr5, yr10} --- review trigger dates
  prob\_ge\_target\_at\_1yr       object            {low, high} --- probability band at 1yr from probability engine
  confidence\_tier                enum              high \| medium \| low
  stress\_verdict                 enum              robust \| conditional \| fragile
  stated\_bet\_snapshot           string            Full growth\_bet.stated\_bet at time of run
  assumption\_count               int               Total assumptions in assumption\_sheet
  fragile\_assumption\_count      int               Assumptions rated fragile
  words\_vs\_numbers\_alignment   enum              Captured at run time
  macro\_regime                   string            Macro regime at run time
  signals\_present                object            Map of node name → boolean (true = returned real data)
  scenario\_weights\_used         object            {bull, base, bear} --- actual weights after assumption adjustments
  calibration\_source             enum              heuristic \| calibrated --- which weight source was used
  outcomes                        array\<object\>   Populated as horizons mature --- see §11.3
  ------------------------------- ----------------- --------------------------------------------------------------------

**11.3 Outcome Scoring Schema**

At each horizon date, the system auto-fetches the current price and computes the outcome score. Thesis and component scoring require brief human input --- a 2-minute review prompted by the system. Being right for the wrong reasons is a calibration signal as important as being wrong.

  ---------------------------- ------------------------- ------------------------------------------------------------------------------------------------------------------------
  **Field**                    **Type**                  **Notes**
  horizon\_years               int                       1 \| 3 \| 5 \| 10
  score\_date                  ISO datetime              When scored
  realized\_price              number                    Actual price at horizon
  realized\_cagr               number                    Actual annualized return from entry price
  outcome\_score               enum                      hit \| miss \| partial --- did price clear the target CAGR?
  thesis\_played\_out          enum \| null              yes \| no \| partial \| too\_early --- human input at review. Did the stated bet actually happen?
  which\_assumptions\_broke    array\<string\> \| null   Human input: which assumption\_sheet items failed? Drives component-level calibration.
  surprise\_factor             string \| null            Human input: did something outside the assumption\_sheet drive the outcome? What?
  component\_signals\_review   object \| null            Optional: human rates which signals (insider, transcript tone, macro, etc.) were useful vs. noise for this prediction.
  ---------------------------- ------------------------- ------------------------------------------------------------------------------------------------------------------------

**11.4 Calibration Feedback Node (Offline)**

Runs as a background job, not in the real-time graph. After every 10 scored predictions for a given segment + macro\_regime combination, recomputes scenario weights using Brier score minimization. Writes updated weights to calibration\_overrides.json. Node 10 reads this file on startup. The probability engine is now learning from its own track record.

  --------------------------------- --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  **Property**                      **Detail**
  Trigger                           Scheduled daily job. Runs when \>= 10 new scored outcomes exist for any segment/regime combination since last calibration run.
  Brier score calculation           For each prediction: Brier score = (predicted\_probability - outcome\_binary)\^2. Lower is better. Compute per segment, per regime, per horizon.
  Weight adjustment                 If predictions at bull scenario weight W\_bull are systematically overconfident (realized frequency \< predicted), decrease W\_bull and increase W\_bear proportionally. Max adjustment per run: ±5pp to prevent overfitting on small samples.
  Signal correlation analysis       When \>= 25 scored predictions available: compute accuracy rate when each node was present vs. absent (using signals\_present map). Flag any node where presence correlates with \< 45% accuracy --- that node may be adding noise. Output to calibration\_report.json for product review.
  Assumption fragility validation   When \>= 15 predictions with scored outcomes: compute accuracy rate by fragile\_assumption\_count (0--2, 3--5, 5+). If high fragility count correlates with worse outcomes as expected, fragility ratings are validated. If not, adjust fragility scoring rubric.
  Output                            calibration\_overrides.json: {segment: {macro\_regime: {bull\_weight, base\_weight, bear\_weight, n\_predictions, brier\_score, last\_updated}}}
  Minimum sample guard              Never apply calibration overrides with fewer than 10 scored predictions for that segment/regime combo. Log sample size in calibration\_notes on every probability output.
  --------------------------------- --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

+----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| **The Karpathy Principle**                                                                                                                                                                                                                                                                                                                                                                                                                                     |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| Every prediction is a training example without a label yet. The prediction ledger is the dataset. The calibration node is the training run. The probability engine is the model. The system gets measurably smarter with each scored horizon --- not from theory, but from its own track record. Start logging predictions from day one of production, even before the calibration logic is built. The dataset is the most valuable thing you will accumulate. |
+----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+

**13. Build Phases**

  --------------------------------------------------------------------------- -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  **Phase**                                                                   **Scope**                                                                                                                                                                                                                                                **Exit Criteria**
  Phase 1 --- Spine & Data (Weeks 1--3)                                       FastAPI skeleton + SSE. LangGraph graph wired (nodes 1--4). OpenBB + yfinance + FMP integration. Fundamentals, Valuation, Analyst nodes functional. Basic Redis cache.                                                                                   POST /analyze-ticker returns valid partial response for AAPL with thesis.business\_summary, valuation, and analysts populated. SSE emits at least 4 progress events.
  Phase 2 --- RAG & Growth Bet (Weeks 4--7)                                   EdgarTools integration. Finnhub news + transcripts. ChromaDB setup. Node 5 (News & Sentiment) and Node 6 (Filings RAG + Growth Bet Extraction) functional. Assumption sheet generation with Sonnet. Node 7 (Themes). Words-vs-numbers alignment check.   growth\_bet.assumption\_sheet populated with ≥5 assumptions for AAPL and MSFT. words\_vs\_numbers\_alignment correctly flags a known misalignment case. Insider and institutional signals populated.
  Phase 3 --- Macro, Crowd & Stress Test (Weeks 8--10)                        Node 8 (Macro) with FRED. Node 9 (Polymarket). Stress test execution in Node 10 using assumption\_sheet from Node 6. stress\_test object in response.                                                                                                    stress\_test.shocks populated for all fragile assumptions on 3 test tickers. stress\_verdict correctly rated robust/conditional/fragile. Polymarket signals appear for mapped tickers.
  Phase 4 --- Probability Engine with Assumption Weights (Weeks 11--12)       Assumption-driven scenario weight derivation. Calibration override file structure. signals\_present logging. Entry dependence and downside risk calculations. Options IV input.                                                                          Scenario weights visibly differ between a fragile-assumption ticker and a robust one. signals\_present map populated for every run. calibration\_overrides.json exists even if empty.
  Phase 5 --- Analyst Tracking & Grading (Weeks 13--15)                       Analyst call ingestion background job. FMP + Finnhub polling. Deduplication. Analyst record schema. EdgarTools 8-K trigger for earnings grading. Daily price-target grading job. Analyst leaderboard endpoint and UI.                                    Analyst calls ingesting automatically for 5 test tickers. At least 1 call graded via earnings trigger. Leaderboard renders with accuracy scores for analysts with 5+ graded calls.
  Phase 6 --- Prediction Ledger & Leaderboard (Weeks 16--17)                  Prediction auto-logging on every analysis run. /predictions/\* endpoints. Leaderboard with live YTD growth from yfinance. Status computation. Outcome scoring UI.                                                                                        Every analysis run creates a prediction record. Leaderboard renders with correct status badges. Scoring flow works end-to-end on a test prediction.
  Phase 6 --- Prediction Ledger & Leaderboard (Weeks 16--17)                  Prediction auto-logging on every analysis run. /predictions/\* endpoints. Leaderboard with live YTD growth from yfinance. Status computation. Outcome scoring UI.                                                                                        Every analysis run creates a prediction record. Leaderboard renders with correct status badges. Scoring flow works end-to-end on a test prediction.
  Phase 7 --- PM Synthesis, Price Efficiency & Full Frontend (Weeks 18--20)   PM synthesis with full anti-hallucination architecture (number registry, post-synthesis validation, hallucination\_check object). Price efficiency assessment in valuation node. Words-vs-numbers alignment. React/Next.js frontend with all panels.     hallucination\_check returns clean on 10 test tickers. price\_efficiency\_assessment correctly flags a known inflated ticker. All frontend panels render without errors. End-to-end latency under 90 seconds for AAPL.
  Phase 8 --- Calibration Feedback & Hardening (Week 21)                      Calibration feedback background job. DLQ worker. All fallback chains tested. Brier score computation on any available scored predictions.                                                                                                                Calibration job runs without error. DLQ retries work correctly. No uncaught exceptions in any simulated failure scenario.
  --------------------------------------------------------------------------- -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

**14. Tools, Models & Ownership Summary**

  ---------------------------------- ----------------- --------------------------------------------------------------------------------------------------------------- ------------------------------------------------------------
  **Component**                      **Owner**         **Technology / Tool**                                                                                           **Model**
  Orchestrator                       Backend           Python 3.11+, LangGraph                                                                                         ---
  FastAPI + SSE                      Backend           FastAPI, uvicorn, sse-starlette                                                                                 ---
  Cache + DLQ                        Backend           Redis (redis-py)                                                                                                ---
  Ticker Classifier                  Backend           yfinance, OpenBB                                                                                                ---
  Fundamentals                       Backend / Quant   OpenBB, yfinance, FMP                                                                                           Haiku / GPT-4o-mini (summary)
  Valuation                          Backend / Quant   Pure Python (deterministic)                                                                                     ---
  Analyst Estimates                  Backend           FMP, OpenBB, yfinance                                                                                           Haiku / GPT-4o-mini
  News & Sentiment                   Backend / ML      Finnhub (primary), OpenBB, yfinance, VADER/FinBERT, ChromaDB                                                    Haiku / GPT-4o-mini
  Filings RAG + Growth Bet           Backend / ML      EdgarTools, Finnhub transcripts, EarningsCall.biz (fallback), ChromaDB, sentence-transformers                   Sonnet (assumption sheet) + Haiku (risk/insider summaries)
  Themes / Graph                     Backend           In-memory graph, themes.json taxonomy                                                                           Haiku (deep mode only)
  Macro                              Backend / Quant   OpenBB FRED, yfinance proxies                                                                                   Haiku / GPT-4o-mini
  Polymarket                         Backend           Polymarket /markets API, polymarket\_markets.json                                                               Haiku
  Probability Engine + Stress Test   Quant             Pure Python; assumption-driven scenario weights; yfinance options IV; calibration\_overrides.json               ---
  PM Synthesis                       Backend / ML      LLM call with structured JSON input                                                                             Claude Sonnet (or best available)
  Analyst Tracking & Grading         Backend / Quant   FMP, Finnhub, OpenBB (ingestion); EdgarTools 8-K detection (grading triggers); yfinance (price at grade time)   ---
  Analyst Leaderboard                Backend           PostgreSQL analyst\_calls + analyst\_records tables; background grading job                                     ---
  Calibration Feedback               Quant / Backend   Background job; Brier score; calibration\_overrides.json; signal correlation analysis                           ---
  Frontend                           Frontend          React, Next.js 14, TypeScript, Tailwind, Recharts                                                               ---
  ---------------------------------- ----------------- --------------------------------------------------------------------------------------------------------------- ------------------------------------------------------------

**15. Open Questions Before Implementation Begins**

  -------- ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- ------------------- ------------
  **\#**   **Question**                                                                                                                                                                                                        **Owner**           **Blocks**
  1        FMP free tier covers \~1,000 requests/day. If daily usage exceeds this, which section degrades first --- analyst estimates fall back to OpenBB/yfinance? Confirm priority.                                          Product             Phase 1
  2        OpenBB free tier may require a platform key for some endpoints. Confirm which OpenBB endpoints require authentication and provision any needed API keys before Phase 1.                                             Backend             Phase 1
  3        EdgarTools requires setting an identity (name + email) via set\_identity() for EDGAR rate limiting. Confirm who sets this and where it lives in the environment (env var recommended).                              Backend             Phase 2
  4        ChromaDB local persistence path: confirm deployment environment. If serverless, evaluate Pinecone free or Weaviate free instead.                                                                                    Backend / Infra     Phase 2
  5        Node 6 uses Sonnet (not Haiku) for assumption sheet generation --- this is the highest-cost LLM call in the system. Estimate: \~\$0.10--0.30 per run. Acceptable? Or cap at Haiku with quality trade-off?           Product             Phase 2
  6        Finnhub free tier includes earnings call transcripts. Evaluate coverage for the 20 tickers most likely to be run. If coverage gaps exist, evaluate EarningsCall.biz paid tier (\~\$10--25/mo).                      Product             Phase 2
  7        Polymarket mapping file (polymarket\_markets.json) needs seeding before Phase 3. Identify 15--20 macro markets relevant to US equities.                                                                             Product / Quant     Phase 3
  8        PM synthesis system prompt for growth\_bet and stress\_test sections is the highest-leverage prompt in the system. Product to draft before Phase 6; quant to review for numerical accuracy.                         Product             Phase 6
  9        Prediction ledger storage: PostgreSQL vs. DynamoDB. PostgreSQL preferred for calibration queries (Brier score aggregation, signal correlation). Confirm environment.                                                Backend / Infra     Phase 5
  10       Calibration feedback requires scored outcomes. Minimum 10 per segment/regime combo. Set expectation with user: calibration overrides will not activate until \~6 months of logged predictions. This is by design.   Product             Phase 7
  11       Deployment environment: local Python server + Next.js dev server is sufficient for single-user. Confirm before Phase 6.                                                                                             Product / Backend   Phase 6
  -------- ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- ------------------- ------------

**16. Success Metrics (MVP)**

  ---------------------------------------------- ---------------------------------------------------------------------------------------------- ----------------------------------------------------------
  **Metric**                                     **Target**                                                                                     **How to Measure**
  End-to-end latency (blue chip ticker)          \< 90 seconds P95                                                                              Log timestamp from POST receipt to final JSON returned
  Section coverage                               \>= 5 of 7 sections populated for any S&P 500 ticker                                           section\_statuses ok count in response
  Hallucination check pass rate                  \> 95% of synthesis runs return hallucination\_check.overall\_status = clean                   hallucination\_check field in every response
  Price efficiency assessment coverage           efficiency\_verdict populated for all large-cap tickers                                        Non-null rate on efficiency\_verdict field
  Analyst call ingestion rate                    New calls ingested within 6 hours of publication for tracked tickers                           Timestamp of FMP call\_date vs. ingestion timestamp
  Analyst grading automation rate                \> 85% of eligible calls graded automatically without human intervention                       Graded calls with grade\_source: auto vs. manual
  Weighted vs. unweighted consensus divergence   weighted\_target\_price differs from avg\_target\_price by \> 5% for at least 30% of tickers   Confirms accuracy-weighting is adding signal, not noise
  Growth bet extraction quality                  assumption\_sheet contains \>= 5 falsifiable assumptions for any S&P 500 ticker                Manual audit: are assumptions specific and testable?
  Stress test coverage                           All fragile assumptions have both mild and severe shock scenarios populated                    stress\_test.shocks count \>= fragile\_assumption\_count
  Prediction logging rate                        100% of analysis runs create a prediction record                                               Prediction count vs. analysis run count in database
  Cache hit rate (repeat tickers)                \> 70% for fundamentals and filings sections                                                   Redis hit/miss counter per section
  ---------------------------------------------- ---------------------------------------------------------------------------------------------- ----------------------------------------------------------

*--- End of Specification ---*
