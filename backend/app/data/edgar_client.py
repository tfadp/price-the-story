"""
EdgarTools client for 10-K and 10-Q filings.

Fetches MD&A and Risk Factors sections from the most recent annual (10-K)
and quarterly (10-Q) filings via the EDGAR HTTPS API.

All calls are synchronous — callers use asyncio.to_thread.
set_identity() is called once at import time using the configured email.
"""
import logging
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

# Max characters to keep from each section — keeps context window manageable
_MAX_SECTION_CHARS = 8_000


def _get_company_class():
    """Load edgartools lazily so missing optional deps do not break startup."""
    try:
        from edgar import Company, set_identity
    except ImportError as e:
        raise RuntimeError("edgartools not installed") from e

    set_identity(settings.edgar_identity)
    return Company


def _truncate(text: Optional[str], max_chars: int = _MAX_SECTION_CHARS) -> Optional[str]:
    if not text:
        return None
    return text[:max_chars] if len(text) > max_chars else text


def get_annual_filing_text(ticker: str) -> dict:
    """Return MD&A and Risk Factors from the most recent 10-K.

    Returns:
        {
            "mda": str | None,
            "risk_factors": str | None,
            "period": str | None,   # e.g. "2024-09-30"
            "source": "edgar_10k",
        }
    """
    try:
        Company = _get_company_class()
        company = Company(ticker)
        filings = company.get_filings(form="10-K")
        if not filings:
            logger.info("edgar: no 10-K found for %s", ticker)
            return _empty_filing("edgar_10k")

        filing = filings[0]  # most recent
        obj = filing.obj()

        mda = _truncate(_extract_section(obj, "mda"))
        risk_factors = _truncate(_extract_section(obj, "risk_factors"))
        period = str(getattr(filing, "period_of_report", None) or "")

        logger.info("edgar: 10-K retrieved for %s (period=%s)", ticker, period)
        return {
            "mda": mda,
            "risk_factors": risk_factors,
            "period": period,
            "source": "edgar_10k",
        }

    except Exception as e:
        logger.warning("edgar: get_annual_filing_text failed for %s: %s", ticker, e)
        return _empty_filing("edgar_10k")


def get_quarterly_filing_text(ticker: str) -> dict:
    """Return MD&A from the most recent 10-Q.

    Returns:
        {
            "mda": str | None,
            "period": str | None,
            "source": "edgar_10q",
        }
    """
    try:
        Company = _get_company_class()
        company = Company(ticker)
        filings = company.get_filings(form="10-Q")
        if not filings:
            logger.info("edgar: no 10-Q found for %s", ticker)
            return _empty_filing("edgar_10q")

        filing = filings[0]
        obj = filing.obj()
        mda = _truncate(_extract_section(obj, "mda"))
        period = str(getattr(filing, "period_of_report", None) or "")

        logger.info("edgar: 10-Q retrieved for %s (period=%s)", ticker, period)
        return {
            "mda": mda,
            "period": period,
            "source": "edgar_10q",
        }

    except Exception as e:
        logger.warning("edgar: get_quarterly_filing_text failed for %s: %s", ticker, e)
        return _empty_filing("edgar_10q")


def _extract_section(filing_obj, section: str) -> Optional[str]:
    """Try common attribute names for a section across edgartools versions."""
    # edgartools exposes sections as attributes on the filing object
    candidates = {
        "mda": [
            "management_discussion_and_analysis",
            "mda",
            "item_7",
            "item7",
        ],
        "risk_factors": [
            "risk_factors",
            "item_1a",
            "item1a",
        ],
    }
    for attr in candidates.get(section, []):
        val = getattr(filing_obj, attr, None)
        if val:
            # Some versions return a Section object; convert to string
            return str(val).strip() or None
    return None


def _empty_filing(source: str) -> dict:
    return {"mda": None, "risk_factors": None, "period": None, "source": source}
