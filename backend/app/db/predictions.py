"""
SQLite prediction ledger.

Logs every completed analysis and supports the leaderboard + scoring endpoints.
DB file lives at backend/predictions.db (same directory as the server).

All functions are synchronous (SQLite is sync) — callers use asyncio.to_thread
to avoid blocking the event loop.
"""
import json
import logging
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Resolves to backend/predictions.db regardless of cwd
DB_PATH = Path(__file__).parent.parent.parent / "predictions.db"


def init_db() -> None:
    """Create the predictions table if it does not exist. Called once at startup."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                prediction_id       TEXT PRIMARY KEY,
                ticker              TEXT NOT NULL,
                run_at              TEXT NOT NULL,
                entry_price         REAL NOT NULL,
                target_cagr         REAL NOT NULL,
                holding_period_years INT NOT NULL,
                horizon_1yr_date    TEXT NOT NULL,
                prob_low            REAL,
                prob_high           REAL,
                confidence_verdict  TEXT,
                verdict_paragraph   TEXT,
                fair_value_base     REAL,
                macro_regime        TEXT,
                segment             TEXT,
                nodes_with_data     TEXT,
                outcome_1yr         TEXT,
                outcome_notes       TEXT,
                stated_bet          TEXT,
                words_vs_numbers    TEXT,
                efficiency_verdict  TEXT
            )
        """)
        conn.commit()
    logger.info("predictions.db ready at %s", DB_PATH)


def log_prediction(pred: dict) -> None:
    """Write one prediction record. Swallows all exceptions — never crashes the pipeline."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO predictions (
                    prediction_id, ticker, run_at, entry_price, target_cagr,
                    holding_period_years, horizon_1yr_date, prob_low, prob_high,
                    confidence_verdict, verdict_paragraph, fair_value_base,
                    macro_regime, segment, nodes_with_data,
                    outcome_1yr, outcome_notes, stated_bet, words_vs_numbers, efficiency_verdict
                ) VALUES (
                    :prediction_id, :ticker, :run_at, :entry_price, :target_cagr,
                    :holding_period_years, :horizon_1yr_date, :prob_low, :prob_high,
                    :confidence_verdict, :verdict_paragraph, :fair_value_base,
                    :macro_regime, :segment, :nodes_with_data,
                    :outcome_1yr, :outcome_notes, :stated_bet, :words_vs_numbers, :efficiency_verdict
                )
                """,
                pred,
            )
            conn.commit()
        logger.info("Logged prediction for %s (%s)", pred.get("ticker"), pred.get("prediction_id"))
    except Exception as e:
        logger.warning("log_prediction failed: %s", e)


def get_all_predictions(
    ticker: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> list[dict]:
    """Return all prediction rows, newest first. Optional ticker/date filters."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        query = "SELECT * FROM predictions WHERE 1=1"
        params: list = []
        if ticker:
            query += " AND ticker = ?"
            params.append(ticker.upper())
        if date_from:
            query += " AND run_at >= ?"
            params.append(date_from)
        if date_to:
            query += " AND run_at <= ?"
            params.append(date_to)
        query += " ORDER BY run_at DESC"
        rows = conn.execute(query, params).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_prediction(prediction_id: str) -> Optional[dict]:
    """Return a single prediction by ID, or None if not found."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM predictions WHERE prediction_id = ?", (prediction_id,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def score_prediction(
    prediction_id: str,
    realized_price: float,
    thesis_played_out: Optional[str],
    notes: Optional[str],
) -> Optional[dict]:
    """Record a scoring outcome. Returns the updated row, or None if not found."""
    row = get_prediction(prediction_id)
    if not row:
        return None

    entry_price = row["entry_price"]
    now = datetime.now(timezone.utc)
    # The ledger stores and surfaces an explicit 1-year grading horizon.
    realized_cagr = (realized_price / entry_price) - 1

    outcome = {
        "grade_date": now.isoformat(),
        "realized_price": realized_price,
        "realized_cagr": round(realized_cagr, 4),
        "thesis_played_out": thesis_played_out,
        "outcome": "hit" if realized_cagr >= row["target_cagr"] else "miss",
    }

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE predictions SET outcome_1yr = ?, outcome_notes = ? WHERE prediction_id = ?",
            (json.dumps(outcome), notes, prediction_id),
        )
        conn.commit()

    return get_prediction(prediction_id)


def get_due_predictions() -> list[dict]:
    """Return predictions due for grading (horizon within 14 days, not yet scored)."""
    cutoff = (date.today() + timedelta(days=14)).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT * FROM predictions
               WHERE horizon_1yr_date <= ? AND outcome_1yr IS NULL
               ORDER BY horizon_1yr_date ASC""",
            (cutoff,),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def _row_to_dict(row: sqlite3.Row) -> dict:
    """Convert a sqlite3.Row to a plain dict, deserializing JSON text fields."""
    if row is None:
        return {}
    d = dict(row)
    for key in ("nodes_with_data", "outcome_1yr"):
        if d.get(key) and isinstance(d[key], str):
            try:
                d[key] = json.loads(d[key])
            except (json.JSONDecodeError, TypeError):
                pass
    return d
