"""
app.py — Process a single call (audio file) through the full pipeline:
    1. Transcribe audio via Deepgram
    2. Grade transcript via OpenAI
    3. Save results to SQLite

Usage:
    python app.py path/to/recording.wav --agent-id 505 --duration 320 \
                  --hangup Customer --transfer Mortgage_Dept --uuid my-call-id
"""
import argparse
import json

from db import get_connection, init_db, save_evaluation
from engine import QAEngine
from file_parser import parse_filename


def process_call(file_path: str, metadata: dict):
    """
    Full pipeline: audio → transcript → AI grade → database.
    """
    init_db()
    engine    = QAEngine()
    call_uuid = metadata.get("uuid", file_path)

    # Auto-fill missing metadata from filename
    parsed = parse_filename(file_path)
    if not metadata.get("agent_name"):
        metadata["agent_name"] = parsed.get("agent_name")
    if not metadata.get("lead_phone"):
        metadata["lead_phone"] = parsed.get("lead_phone")
    if not metadata.get("call_date"):
        metadata["call_date"] = parsed.get("call_date")

    print(f"Processing call: {call_uuid}")

    # Step 1 — Transcribe
    print("  Transcribing audio...")
    transcript = engine.transcribe_audio(file_path)
    print(f"  Transcript length: {len(transcript)} chars")

    # Step 2 — AI evaluation
    print("  Evaluating with AI...")
    analysis = engine.evaluate_call(transcript, metadata)
    print(f"  Score: {analysis.get('score')}/100 | Loan: {analysis.get('loan_type')}")

    # Use AI-detected agent name if still missing
    if not metadata.get("agent_name") and analysis.get("agent_name"):
        metadata["agent_name"] = analysis["agent_name"]

    # Step 3 — Save to database
    conn = get_connection()
    save_evaluation(conn, call_uuid, metadata, transcript, analysis)
    conn.close()
    print("  Saved to database.")

    return analysis


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process a single call recording.")
    parser.add_argument("file",          help="Path to the audio file (WAV/MP3)")
    parser.add_argument("--uuid",        default=None,  help="Unique call ID")
    parser.add_argument("--agent-id",    type=int, default=None)
    parser.add_argument("--agent-name",  default=None)
    parser.add_argument("--lead-phone",  default=None)
    parser.add_argument("--call-date",   default=None,  help="YYYY-MM-DD")
    parser.add_argument("--duration",    type=int, default=None, help="Seconds")
    parser.add_argument("--hangup",      default=None,  help="Agent|Customer|System")
    parser.add_argument("--transfer",    default=None,  help="Transfer destination")
    args = parser.parse_args()

    metadata = {
        "uuid":        args.uuid or args.file,
        "agent_id":    args.agent_id,
        "agent_name":  args.agent_name,
        "lead_phone":  args.lead_phone,
        "call_date":   args.call_date,
        "duration":    args.duration,
        "hangup":      args.hangup,
        "transfer_ext": args.transfer,
    }

    result = process_call(args.file, metadata)
    print("\nFull AI Result:")
    print(json.dumps(result, indent=2))
