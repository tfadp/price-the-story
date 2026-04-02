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


# Phase C — Risk factor evolution, insider Form 4, institutional 13F

_RISK_SECTION_MAX = 6_000  # chars per year of risk text


def get_risk_factor_evolution(ticker: str) -> dict:
    """Compare current vs prior year risk factors to surface what changed.

    Fetches the two most recent 10-K filings and extracts the risk factors
    section from each.  Comparing the two lets downstream LLM nodes flag
    newly-added or removed risks without needing full diff tooling.

    Returns:
        {
            "current_risks_text": str,   # truncated to 6000 chars
            "prior_risks_text": str,     # truncated to 6000 chars (empty if only one filing)
            "available": bool
        }
    Returns {"available": False} if EdgarTools is unavailable or no 10-K found.
    """
    try:
        Company = _get_company_class()
        company = Company(ticker)
        filings = company.get_filings(form="10-K").latest(2)
        if not filings:
            logger.info("edgar: no 10-K found for risk evolution (%s)", ticker)
            return {"available": False}

        # EdgarTools may return a single filing object or a list-like object
        if not hasattr(filings, "__len__"):
            filings = [filings]

        current_obj = filings[0].obj()
        current_text = _truncate(_extract_section(current_obj, "risk_factors"), _RISK_SECTION_MAX) or ""

        prior_text = ""
        if len(filings) >= 2:
            prior_obj = filings[1].obj()
            prior_text = _truncate(_extract_section(prior_obj, "risk_factors"), _RISK_SECTION_MAX) or ""

        logger.info(
            "edgar: risk evolution retrieved for %s (current=%d chars, prior=%d chars)",
            ticker, len(current_text), len(prior_text),
        )
        return {
            "current_risks_text": current_text,
            "prior_risks_text": prior_text,
            "available": True,
        }

    except Exception as e:
        logger.warning("edgar: get_risk_factor_evolution failed for %s: %s", ticker, e)
        return {"available": False}


def get_insider_transactions(ticker: str, lookback_days: int = 90) -> list[dict]:
    """Fetch recent Form 4 insider transactions.

    We limit to the 20 most recent Form 4 filings and filter by date.
    Each dict represents one transaction with best-effort field extraction;
    filings with parse errors are silently skipped.

    Returns list of {filer_name, transaction_date, transaction_type, shares, value_usd}.
    Returns [] if EdgarTools is unavailable or no Form 4s are found.
    """
    try:
        from datetime import date, timedelta

        Company = _get_company_class()
        company = Company(ticker)
        filings = company.get_filings(form="4")
        if not filings:
            logger.info("edgar: no Form 4 filings found for %s", ticker)
            return []

        cutoff = date.today() - timedelta(days=lookback_days)
        transactions: list[dict] = []

        # latest(20) keeps network traffic low; Form 4s are frequent for large caps
        recent = filings.latest(20)
        if not hasattr(recent, "__iter__"):
            recent = [recent]

        for filing in recent:
            try:
                filing_date_raw = getattr(filing, "filing_date", None) or getattr(filing, "date", None)
                if filing_date_raw is None:
                    continue

                # Normalise to a date object regardless of string vs date type
                if isinstance(filing_date_raw, str):
                    from datetime import datetime as _dt
                    filing_date = _dt.strptime(filing_date_raw[:10], "%Y-%m-%d").date()
                else:
                    filing_date = filing_date_raw

                if filing_date < cutoff:
                    continue

                filer_name = str(getattr(filing, "filer", None) or "Unknown")
                obj = filing.obj()

                # Attempt to extract transaction details from the Form 4 object
                txn_type = "unknown"
                shares = None
                value_usd = None

                # EdgarTools Form4 objects expose different attributes by version
                for attr in ("transaction_type", "form_type"):
                    raw = getattr(obj, attr, None)
                    if raw:
                        raw_str = str(raw).strip().upper()
                        if raw_str in ("P", "BUY", "PURCHASE"):
                            txn_type = "buy"
                        elif raw_str in ("S", "SELL", "SALE"):
                            txn_type = "sell"
                        elif raw_str in ("A", "AWARD", "GRANT"):
                            txn_type = "grant"
                        break

                for attr in ("shares_transacted", "shares", "quantity"):
                    raw = getattr(obj, attr, None)
                    if raw is not None:
                        try:
                            shares = float(raw)
                        except (TypeError, ValueError):
                            pass
                        break

                for attr in ("value", "total_value", "transaction_value"):
                    raw = getattr(obj, attr, None)
                    if raw is not None:
                        try:
                            value_usd = float(raw)
                        except (TypeError, ValueError):
                            pass
                        break

                transactions.append({
                    "filer_name": filer_name,
                    "transaction_date": str(filing_date),
                    "transaction_type": txn_type,
                    "shares": shares,
                    "value_usd": value_usd,
                })
            except Exception as inner_e:
                # Skip individual filings that fail to parse — best-effort
                logger.debug("edgar: Form 4 parse skip (%s): %s", ticker, inner_e)
                continue

        transactions.sort(key=lambda t: t["transaction_date"], reverse=True)
        logger.info("edgar: %d insider transactions found for %s", len(transactions), ticker)
        return transactions

    except Exception as e:
        logger.warning("edgar: get_insider_transactions failed for %s: %s", ticker, e)
        return []


def get_institutional_holders(ticker: str) -> dict:
    """Fetch institutional 13F holder data — best-effort.

    13F support in EdgarTools is limited; any exception returns the
    unavailable sentinel immediately so callers never block.

    Returns:
        {
            "top_holders": [{"holder": str, "shares": int, "pct_outstanding": float}],
            "available": bool
        }
    Returns {"available": False} if data is unavailable.
    """
    try:
        Company = _get_company_class()
        company = Company(ticker)

        # 13F-HR filings are filed BY institutions, not by the company itself.
        # EdgarTools may not support querying by company for this form type.
        # We try and immediately fall back on any error.
        filings = company.get_filings(form="13F-HR")
        if not filings:
            return {"available": False}

        holders: list[dict] = []
        latest = filings.latest(1)
        if not hasattr(latest, "__iter__"):
            latest = [latest]

        for filing in latest:
            try:
                obj = filing.obj()
                # EdgarTools 13F object shape varies; try common attributes
                entries = getattr(obj, "holdings", None) or getattr(obj, "infotable", None)
                if not entries:
                    break
                for entry in list(entries)[:10]:
                    holder = str(getattr(entry, "name", None) or getattr(entry, "nameofissuer", "") or "")
                    shares_raw = getattr(entry, "shares", None) or getattr(entry, "sshprnamt", None)
                    pct_raw = getattr(entry, "pct_outstanding", None)
                    try:
                        shares = int(shares_raw) if shares_raw is not None else 0
                    except (TypeError, ValueError):
                        shares = 0
                    try:
                        pct = float(pct_raw) if pct_raw is not None else 0.0
                    except (TypeError, ValueError):
                        pct = 0.0
                    holders.append({"holder": holder, "shares": shares, "pct_outstanding": pct})
            except Exception as inner_e:
                logger.debug("edgar: 13F parse skip (%s): %s", ticker, inner_e)
                break

        if not holders:
            return {"available": False}

        logger.info("edgar: %d institutional holders found for %s", len(holders), ticker)
        return {"top_holders": holders, "available": True}

    except Exception as e:
        logger.warning("edgar: get_institutional_holders failed for %s: %s", ticker, e)
        return {"available": False}
