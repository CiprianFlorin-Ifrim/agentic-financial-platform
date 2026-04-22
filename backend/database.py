# backend/database.py
# SQLite database layer for the CSE Platform.
# Provides table initialisation and raw connection access.
# All tables are created with IF NOT EXISTS -- safe to call on every boot.

import os
import sqlite3
from typing import Any


# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

DB_PATH: str = os.getenv("DATABASE_PATH", "backend/cse_platform.db")


# -----------------------------------------------------------------------------
# Connection
# -----------------------------------------------------------------------------

def get_connection() -> sqlite3.Connection:
    """Return a new SQLite connection with row_factory set to Row."""
    conn             = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row          # Access columns by name
    conn.execute("PRAGMA journal_mode=WAL") # Better concurrent read performance
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# -----------------------------------------------------------------------------
# Initialisation
# -----------------------------------------------------------------------------

def init_db() -> None:
    """Create all required tables if they do not already exist."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    with get_connection() as conn:
        conn.executescript("""
            -- deals
            -- Stores the best scenario selected from each analysis run.
            -- Each row represents one saved deal with full engine outputs.
            CREATE TABLE IF NOT EXISTS deals (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id      TEXT    NOT NULL,
                scenario_id     TEXT    NOT NULL,
                loan_amount     REAL    NOT NULL,
                tenor_years     REAL    NOT NULL,
                interest_rate   REAL    NOT NULL,
                collateral_type TEXT    NOT NULL,
                client_rating   TEXT    NOT NULL,
                product_type    TEXT    NOT NULL,
                rwa_amount      REAL,
                capital_charge  REAL,
                nii             REAL,
                return_on_rwa   REAL,
                score           REAL,
                reasoning       TEXT,
                created_at      TEXT    DEFAULT (datetime('now'))
            );

            -- scenario_runs
            -- Audit log of every CSV uploaded and processed.
            CREATE TABLE IF NOT EXISTS scenario_runs (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id       TEXT    NOT NULL,
                file_name        TEXT,
                scenario_count   INTEGER,
                best_scenario_id TEXT,
                created_at       TEXT    DEFAULT (datetime('now'))
            );

            -- agent_sessions
            -- Persists ADK session state (events + metadata) across server restarts.
            -- state_json  : serialised session state dict
            -- events_json : serialised list of ADK event dicts
            CREATE TABLE IF NOT EXISTS agent_sessions (
                app_name    TEXT NOT NULL,
                user_id     TEXT NOT NULL,
                session_id  TEXT NOT NULL,
                state_json  TEXT NOT NULL DEFAULT '{}',
                events_json TEXT NOT NULL DEFAULT '[]',
                updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (app_name, user_id, session_id)
            );

            -- traces
            -- OpenTelemetry spans captured from ADK agent runs.
            CREATE TABLE IF NOT EXISTS traces (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                trace_id        TEXT,
                span_id         TEXT,
                parent_span_id  TEXT,
                name            TEXT,
                kind            TEXT,
                start_time      TEXT,
                end_time        TEXT,
                duration_ms     REAL,
                status          TEXT,
                attributes      TEXT,
                events          TEXT,
                resource        TEXT,
                recorded_at     TEXT DEFAULT (datetime('now'))
            );

            -- logs
            -- Python log records with optional OTel trace correlation.
            CREATE TABLE IF NOT EXISTS logs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   TEXT,
                level       TEXT,
                logger      TEXT,
                message     TEXT,
                trace_id    TEXT,
                span_id     TEXT,
                recorded_at TEXT DEFAULT (datetime('now'))
            );
        """)


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def save_deal(
    session_id      : str,
    scenario_id     : str,
    loan_amount     : float,
    tenor_years     : float,
    interest_rate   : float,
    collateral_type : str,
    client_rating   : str,
    product_type    : str,
    rwa_amount      : float,
    capital_charge  : float,
    nii             : float,
    return_on_rwa   : float,
    score           : float,
    reasoning       : str,
) -> int:
    """Insert a deal record and return its new row id."""
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO deals (
                session_id, scenario_id, loan_amount, tenor_years,
                interest_rate, collateral_type, client_rating, product_type,
                rwa_amount, capital_charge, nii, return_on_rwa, score, reasoning
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                session_id, scenario_id, loan_amount, tenor_years,
                interest_rate, collateral_type, client_rating, product_type,
                rwa_amount, capital_charge, nii, return_on_rwa, score, reasoning,
            ),
        )
        return cursor.lastrowid


def get_deals(session_id: str | None = None, limit: int = 20) -> list[dict]:
    """Return deals, optionally filtered by session, most recent first."""
    with get_connection() as conn:
        if session_id:
            rows = conn.execute(
                "SELECT * FROM deals WHERE session_id=? ORDER BY created_at DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM deals ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return [dict(r) for r in rows]


def get_deal_by_id(deal_id: int) -> dict | None:
    """Return a single deal by primary key, or None if not found."""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM deals WHERE id=?", (deal_id,)).fetchone()
    return dict(row) if row else None


# -----------------------------------------------------------------------------
# Agent session persistence  (used by SQLiteSessionService)
# -----------------------------------------------------------------------------

def upsert_agent_session(
    app_name    : str,
    user_id     : str,
    session_id  : str,
    state_json  : str,
    events_json : str,
) -> None:
    """Insert or update an agent session record."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO agent_sessions
                (app_name, user_id, session_id, state_json, events_json, updated_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT (app_name, user_id, session_id) DO UPDATE SET
                state_json  = excluded.state_json,
                events_json = excluded.events_json,
                updated_at  = excluded.updated_at
            """,
            (app_name, user_id, session_id, state_json, events_json),
        )


def load_agent_session(
    app_name   : str,
    user_id    : str,
    session_id : str,
) -> dict | None:
    """
    Return the stored state and events for a session, or None if not found.
    Returns a dict with keys: state_json, events_json.
    """
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT state_json, events_json
            FROM   agent_sessions
            WHERE  app_name=? AND user_id=? AND session_id=?
            """,
            (app_name, user_id, session_id),
        ).fetchone()
    return dict(row) if row else None
