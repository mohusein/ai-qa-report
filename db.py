"""
db.py — SQLite database helpers shared across the project.
SQLite is built into Python — no installation or server needed.
The database file (qa_reports.db) is created automatically on first run.
"""
import sqlite3
from config import DB_PATH


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row   # lets you access columns by name
    conn.execute("PRAGMA journal_mode=WAL")  # safe for concurrent reads
    return conn


def init_db():
    """Create tables if they don't exist yet."""
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS Agents (
            agent_id   INTEGER PRIMARY KEY,
            full_name  TEXT,
            department TEXT
        );

        CREATE TABLE IF NOT EXISTS CallEvaluations (
            evaluation_id        INTEGER PRIMARY KEY AUTOINCREMENT,
            call_uuid            TEXT UNIQUE,
            agent_name           TEXT,
            agent_id             INTEGER DEFAULT NULL,
            lead_phone           TEXT,
            call_date            TEXT,
            call_timestamp       TEXT DEFAULT (datetime('now')),
            duration_seconds     INTEGER DEFAULT NULL,
            hangup_source        TEXT DEFAULT NULL,
            transfer_destination TEXT DEFAULT NULL,
            detected_loan_type   TEXT DEFAULT NULL,
            category             TEXT DEFAULT NULL,
            transcription_text   TEXT,
            qa_score             INTEGER DEFAULT NULL,
            qa_feedback          TEXT,
            qa_summary           TEXT,
            grading_json         TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_agent_score ON CallEvaluations(agent_name, qa_score);
        CREATE INDEX IF NOT EXISTS idx_call_date   ON CallEvaluations(call_date);
    """)
    conn.commit()
    conn.close()


def save_evaluation(conn: sqlite3.Connection, call_uuid: str, metadata: dict,
                    transcript: str, analysis: dict):
    import json
    sql = """
        INSERT INTO CallEvaluations
            (call_uuid, agent_name, agent_id, lead_phone, call_date,
             duration_seconds, hangup_source, transfer_destination,
             detected_loan_type, category,
             transcription_text, qa_score, qa_feedback, qa_summary,
             grading_json)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(call_uuid) DO UPDATE SET
            agent_name         = excluded.agent_name,
            agent_id           = excluded.agent_id,
            lead_phone         = excluded.lead_phone,
            call_date          = excluded.call_date,
            duration_seconds   = excluded.duration_seconds,
            hangup_source      = excluded.hangup_source,
            transfer_destination = excluded.transfer_destination,
            detected_loan_type = excluded.detected_loan_type,
            category           = excluded.category,
            qa_score           = excluded.qa_score,
            qa_feedback        = excluded.qa_feedback,
            qa_summary         = excluded.qa_summary,
            transcription_text = excluded.transcription_text,
            grading_json       = excluded.grading_json
    """
    # Prefer metadata agent_name, fall back to AI-detected agent_name from analysis
    agent_name = metadata.get("agent_name") or analysis.get("agent_name")

    conn.execute(sql, (
        call_uuid,
        agent_name,
        metadata.get("agent_id"),
        metadata.get("lead_phone"),
        metadata.get("call_date"),
        metadata.get("duration"),
        metadata.get("hangup"),
        metadata.get("transfer_ext"),
        analysis.get("loan_type"),
        analysis.get("category", "no evaluation"),
        transcript,
        analysis.get("score"),
        analysis.get("areas_of_improvement"),
        analysis.get("summary"),
        json.dumps(analysis),
    ))
    conn.commit()
