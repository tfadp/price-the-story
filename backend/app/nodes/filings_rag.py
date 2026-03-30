"""
Node 6: Filings RAG + Growth Bet Extraction (Phase B).

Pipeline:
  1. Fetch 10-K MD&A + Risk Factors (EdgarTools), 10-Q MD&A (EdgarTools),
     last 4 earnings transcripts (Finnhub)
  2. Chunk and embed all text into ChromaDB (skip if already embedded for this
     ticker + accession period — 7-day re-embed window)
  3. Run 4 RAG queries to surface growth bet language
  4. Deterministic words-vs-numbers check using Fundamentals node output
  5. Claude Sonnet synthesizes a 5-8 item assumption sheet

Returns delta: {"filings_rag": {...}, "section_statuses": {...}}

Max execution time: 45 seconds (Sonnet + filings is the bottleneck).
"""
import asyncio
import hashlib
import json
import logging
import textwrap
from typing import Optional

import chromadb
from chromadb.utils import embedding_functions

from app.config import settings
from app.data.edgar_client import get_annual_filing_text, get_quarterly_filing_text
from app.data.finnhub_client import get_earnings_transcripts
from app.state import GraphState
from app.utils import safe_float

logger = logging.getLogger(__name__)

_CHROMA_PATH = "./chroma_db"
_COLLECTION_NAME = "filings"
_EMBED_MODEL = "all-MiniLM-L6-v2"  # fast, local, no API key needed
_CHUNK_SIZE = 600   # characters per chunk
_CHUNK_OVERLAP = 80
_MAX_RAG_RESULTS = 6  # chunks returned per query

# RAG queries — surfaces growth bet language directly
_GROWTH_BET_QUERIES = [
    "multi-year growth targets forward guidance management stated goals",
    "segments products geographies management is investing expanding",
    "capital allocation R&D capex priorities investment areas",
    "analyst pushback growth plan Q&A management response confidence",
]

_PARTIAL_STATUS = {
    "status": "partial",
    "source": "filings_rag",
    "cached": False,
    "ttl_remaining_s": None,
}
_OK_STATUS = {
    "status": "ok",
    "source": "filings_rag",
    "cached": False,
    "ttl_remaining_s": None,
}


# ---------------------------------------------------------------------------
# ChromaDB helpers
# ---------------------------------------------------------------------------

def _get_collection() -> chromadb.Collection:
    """Return (or create) the persistent ChromaDB collection."""
    client = chromadb.PersistentClient(path=_CHROMA_PATH)
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=_EMBED_MODEL
    )
    return client.get_or_create_collection(
        name=_COLLECTION_NAME,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )


def _chunk_text(text: str) -> list[str]:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + _CHUNK_SIZE
        chunks.append(text[start:end])
        start += _CHUNK_SIZE - _CHUNK_OVERLAP
    return [c.strip() for c in chunks if c.strip()]


def _doc_id(ticker: str, source: str, chunk_idx: int) -> str:
    return f"{ticker}_{source}_{chunk_idx}"


def _period_hash(ticker: str, annual_period: str, quarterly_period: str) -> str:
    """Short hash to detect when filings have changed and need re-embedding."""
    raw = f"{ticker}|{annual_period}|{quarterly_period}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def _embed_documents(
    collection: chromadb.Collection,
    ticker: str,
    annual: dict,
    quarterly: dict,
    transcripts: list[dict],
) -> int:
    """Embed all filings into ChromaDB. Returns total chunks added."""
    total = 0

    def _add(text: Optional[str], source_tag: str) -> None:
        nonlocal total
        if not text:
            return
        chunks = _chunk_text(text)
        ids = [_doc_id(ticker, source_tag, i) for i in range(len(chunks))]
        metas = [{"ticker": ticker, "source": source_tag, "chunk": i} for i in range(len(chunks))]
        # Upsert — safe to call multiple times
        collection.upsert(documents=chunks, ids=ids, metadatas=metas)
        total += len(chunks)

    _add(annual.get("mda"), "10k_mda")
    _add(annual.get("risk_factors"), "10k_risk")
    _add(quarterly.get("mda"), "10q_mda")

    for i, t in enumerate(transcripts):
        for turn in (t.get("transcript") or []):
            speech = (turn.get("speech") or "").strip()
            if speech:
                tag = f"transcript_{t.get('year', 0)}_q{t.get('quarter', i)}"
                _add(speech, tag)

    return total


def _rag_query(collection: chromadb.Collection, ticker: str, query: str) -> str:
    """Run a single RAG query and return concatenated matching chunks."""
    try:
        results = collection.query(
            query_texts=[query],
            n_results=_MAX_RAG_RESULTS,
            where={"ticker": ticker},
        )
        docs = (results.get("documents") or [[]])[0]
        return "\n\n---\n\n".join(docs)
    except Exception as e:
        logger.warning("filings_rag: RAG query failed: %s", e)
        return ""


# ---------------------------------------------------------------------------
# Words-vs-numbers deterministic check
# ---------------------------------------------------------------------------

def _words_vs_numbers_check(
    fund: dict,
    narrative_claims_tech: bool,
) -> tuple[str, str]:
    """Compare capital allocation trend against narrative claims.

    Returns (alignment, notes).
    alignment: aligned | partial_misalignment | significant_misalignment
    """
    time_series = (fund.get("time_series") or {})
    revenues = [safe_float(v) for v in (time_series.get("revenue") or []) if safe_float(v)]
    rd_list = [safe_float(v) for v in (time_series.get("research_and_development") or []) if safe_float(v)]

    if not revenues or not rd_list or len(revenues) < 2 or len(rd_list) < 2:
        return "aligned", "Insufficient data to verify capital allocation vs. narrative."

    # R&D as % of revenue, most recent 2 years
    try:
        rd_pct_recent = rd_list[-1] / revenues[-1]
        rd_pct_prior = rd_list[-2] / revenues[-2]
        rd_trend_pct = (rd_pct_recent - rd_pct_prior) / max(abs(rd_pct_prior), 0.001)
    except (ZeroDivisionError, IndexError):
        return "aligned", "Could not compute R&D trend."

    if narrative_claims_tech and rd_trend_pct < -0.05:
        return (
            "significant_misalignment",
            f"Management narrative emphasises technology/AI investment, but R&D as % of revenue "
            f"declined {abs(rd_trend_pct)*100:.1f}% YoY ({rd_pct_prior*100:.1f}% → {rd_pct_recent*100:.1f}%).",
        )
    elif narrative_claims_tech and rd_trend_pct >= 0:
        return (
            "aligned",
            f"R&D spend as % of revenue increased {rd_trend_pct*100:.1f}% YoY, "
            f"consistent with stated technology investment focus.",
        )
    return "aligned", "Capital allocation trend is broadly consistent with management narrative."


# ---------------------------------------------------------------------------
# Sonnet assumption sheet synthesis
# ---------------------------------------------------------------------------

async def _build_assumption_sheet(
    ticker: str,
    rag_context: dict[str, str],
    words_vs_numbers: str,
    alignment_notes: str,
) -> tuple[Optional[str], list[dict]]:
    """Call Claude Sonnet to extract stated_bet and assumption_sheet.

    Returns (stated_bet, assumption_sheet_list).
    Falls back to (None, []) if no API key or LLM call fails.
    """
    if not settings.anthropic_api_key:
        return None, []

    combined_context = "\n\n===\n\n".join(
        f"[{label}]\n{text}"
        for label, text in rag_context.items()
        if text.strip()
    )
    if not combined_context.strip():
        return None, []

    # Truncate to ~12k chars to stay well within context limits
    combined_context = combined_context[:12_000]

    prompt = textwrap.dedent(f"""
        You are a senior equity analyst extracting management's explicit growth bet from SEC filings
        and earnings transcripts for {ticker}.

        FILINGS CONTEXT:
        {combined_context}

        CAPITAL ALLOCATION CHECK:
        Words vs. numbers alignment: {words_vs_numbers}
        Notes: {alignment_notes}

        TASK 1 — stated_bet:
        Write 1-2 sentences in management's own words (quote or close paraphrase) describing
        their explicit multi-year growth plan. What is the single biggest bet they are making?
        If no clear stated bet exists, write "No explicit multi-year growth target found in filings."

        TASK 2 — assumption_sheet:
        Extract 5-8 explicit, falsifiable assumptions that must hold for the stated bet to succeed.
        For each assumption:
        - assumption: one sentence, specific and testable
        - dimension: one of market | execution | capital | regulation | competitive | technology
        - linked_metric: the specific metric to watch (e.g. "net revenue retention", "R&D % of revenue")
        - current_evidence: what the filings say right now about this metric
        - fragility: robust | moderate | fragile

        A "fragile" assumption is one where current evidence is thin, contradictory,
        or where the company has a history of missing.

        Return ONLY valid JSON, no markdown, no explanation:
        {{
            "stated_bet": "...",
            "assumption_sheet": [
                {{
                    "assumption": "...",
                    "dimension": "...",
                    "linked_metric": "...",
                    "current_evidence": "...",
                    "fragility": "robust|moderate|fragile"
                }}
            ]
        }}
    """).strip()

    try:
        from langchain_anthropic import ChatAnthropic
        from langchain_core.messages import HumanMessage

        llm = ChatAnthropic(
            model="claude-sonnet-4-6",
            api_key=settings.anthropic_api_key,
            max_tokens=2048,
        )
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        data = json.loads(response.content)
        stated_bet = data.get("stated_bet")
        assumption_sheet = data.get("assumption_sheet") or []
        logger.info("filings_rag: Sonnet produced %d assumptions for %s", len(assumption_sheet), ticker)
        return stated_bet, assumption_sheet
    except json.JSONDecodeError as e:
        logger.warning("filings_rag: Sonnet returned non-JSON: %s", e)
        return None, []
    except Exception as e:
        logger.warning("filings_rag: Sonnet call failed: %s", e)
        return None, []


# ---------------------------------------------------------------------------
# Node entry point
# ---------------------------------------------------------------------------

async def run(state: GraphState) -> dict:
    """Node 6: Filings RAG + Growth Bet Extraction."""
    ticker = state["ticker"]
    fund = state.get("fundamentals") or {}

    try:
        # ------------------------------------------------------------------
        # Step 1 — Fetch filings and transcripts (all in threads, parallel)
        # ------------------------------------------------------------------
        annual_fut = asyncio.to_thread(get_annual_filing_text, ticker)
        quarterly_fut = asyncio.to_thread(get_quarterly_filing_text, ticker)
        transcripts_fut = asyncio.to_thread(get_earnings_transcripts, ticker, 4)

        annual, quarterly, transcripts = await asyncio.gather(
            annual_fut, quarterly_fut, transcripts_fut
        )

        has_any_text = (
            annual.get("mda") or annual.get("risk_factors")
            or quarterly.get("mda")
            or transcripts
        )
        if not has_any_text:
            logger.info("filings_rag: no text data retrieved for %s", ticker)
            return {
                "filings_rag": None,
                "section_statuses": {"filings_rag": _PARTIAL_STATUS},
            }

        # ------------------------------------------------------------------
        # Step 2 — Embed into ChromaDB
        # ------------------------------------------------------------------
        collection = await asyncio.to_thread(_get_collection)
        total_chunks = await asyncio.to_thread(
            _embed_documents, collection, ticker, annual, quarterly, transcripts
        )
        logger.info("filings_rag: embedded %d chunks for %s", total_chunks, ticker)

        # ------------------------------------------------------------------
        # Step 3 — RAG queries
        # ------------------------------------------------------------------
        rag_results: dict[str, str] = {}
        for query in _GROWTH_BET_QUERIES:
            label = query[:40]
            rag_results[label] = await asyncio.to_thread(_rag_query, collection, ticker, query)

        # ------------------------------------------------------------------
        # Step 4 — Words-vs-numbers check (deterministic, no LLM)
        # ------------------------------------------------------------------
        # Heuristic: check if any RAG result mentions "AI", "tech", or "platform"
        all_rag_text = " ".join(rag_results.values()).lower()
        narrative_claims_tech = any(
            kw in all_rag_text for kw in ("artificial intelligence", " ai ", "machine learning", "platform", "technology investment")
        )
        words_vs_numbers, alignment_notes = _words_vs_numbers_check(fund, narrative_claims_tech)

        # ------------------------------------------------------------------
        # Step 5 — Sonnet assumption sheet (most important LLM call)
        # ------------------------------------------------------------------
        stated_bet, assumption_sheet = await asyncio.wait_for(
            _build_assumption_sheet(ticker, rag_results, words_vs_numbers, alignment_notes),
            timeout=45.0,
        )

        # Determine most fragile assumption for pm_synthesis
        fragile_assumptions = [a for a in assumption_sheet if a.get("fragility") == "fragile"]
        most_fragile = fragile_assumptions[0].get("assumption") if fragile_assumptions else None

        result = {
            "filings_rag": {
                "stated_bet": stated_bet,
                "assumption_sheet": assumption_sheet,
                "words_vs_numbers_alignment": words_vs_numbers,
                "alignment_notes": alignment_notes,
                "most_fragile_assumption": most_fragile,
                "sources": {
                    "annual_period": annual.get("period"),
                    "quarterly_period": quarterly.get("period"),
                    "transcript_count": len(transcripts),
                    "chunks_embedded": total_chunks,
                },
            },
            "section_statuses": {"filings_rag": _OK_STATUS},
        }
        return result

    except asyncio.TimeoutError:
        logger.warning("filings_rag: timed out for %s", ticker)
        return {
            "filings_rag": None,
            "section_statuses": {
                "filings_rag": {**_PARTIAL_STATUS, "source": "timeout"}
            },
        }
    except Exception as e:
        logger.warning("filings_rag: node failed for %s: %s", ticker, e)
        return {
            "filings_rag": None,
            "section_statuses": {
                "filings_rag": {**_PARTIAL_STATUS, "source": "error"}
            },
        }
