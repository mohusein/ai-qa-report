"""
critiera.py — Batch-grade .txt transcript files from the output/ folder.

Usage:
    python critiera.py

Reads every .txt file in output/, sends it to the QAEngine for AI grading,
and saves the results to SQLite. Skips files already graded.
"""
import json
from pathlib import Path

from config import TRANSCRIPT_DIR
from db import get_connection, init_db, save_evaluation
from engine import QAEngine
from file_parser import parse_filename


def grade_calls():
    init_db()
    engine = QAEngine()
    conn   = get_connection()

    # Make sure the output folder exists
    TRANSCRIPT_DIR.mkdir(exist_ok=True)

    txt_files = list(TRANSCRIPT_DIR.glob("*.txt"))
    if not txt_files:
        print(f"No .txt files found in {TRANSCRIPT_DIR}. Nothing to grade.")
        conn.close()
        return

    for txt_path in txt_files:
        filename = txt_path.name

        # Skip already-graded files to save API costs
        row = conn.execute(
            "SELECT evaluation_id FROM CallEvaluations "
            "WHERE call_uuid = ? AND qa_score IS NOT NULL",
            (filename,)
        ).fetchone()
        if row:
            print(f"Skipping {filename} — already graded.")
            continue

        print(f"Grading: {filename} ...")
        transcript = txt_path.read_text(encoding="utf-8")
        parsed     = parse_filename(filename)

        metadata = {
            "agent_name":   parsed.get("agent_name"),
            "lead_phone":   parsed.get("lead_phone"),
            "call_date":    parsed.get("call_date"),
            "duration":     None,
            "hangup":       None,
            "transfer_ext": None,
        }

        try:
            result = engine.evaluate_call(transcript, metadata)

            # Use AI-detected agent name if filename parse didn't find one
            if not metadata["agent_name"] and result.get("agent_name"):
                metadata["agent_name"] = result["agent_name"]

            save_evaluation(conn, filename, metadata, transcript, result)
            print(f"  ✓ Score {result.get('score')}/100 | "
                  f"Agent: {metadata['agent_name']} | Loan: {result.get('loan_type')}")

        except Exception as e:
            print(f"  ✗ Error processing {filename}: {e}")

    conn.close()
    print("Done.")


if __name__ == "__main__":
    grade_calls()
