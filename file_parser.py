"""
file_parser.py — Extract metadata from audio/transcript filenames.

Supports multiple filename formats:

  Dialer format:
    20260615-120636_2012298_7576049254_VA_V6151206220002012298_tpenninger-all.mp3
    └─ date: 20260615  agent: tpenninger  phone: 7576049254

  Transcript format:
    John_Doe-5551234567-2026-05-28.txt
    └─ agent: John Doe  phone: 5551234567  date: 2026-05-28
"""
import re
from pathlib import Path
from datetime import datetime


def normalize_loan_hint(value: str | None) -> str | None:
    """Map filename/dialer codes to the loan types used by the QA engine."""
    if not value:
        return None

    value = value.strip().lower()
    if value in {"va", "veteran", "veterans"}:
        return "VA"
    if value in {"debt", "dt", "d", "credit", "cc"}:
        return "Debt"
    if value in {"mortgage", "mtg", "mort", "home", "fha", "refi", "refinance"}:
        return "Mortgage"
    return None


def parse_filename(filename: str) -> dict:
    """
    Return a dict with keys: agent_name, agent_username, lead_phone,
    call_date (YYYY-MM-DD).
    Falls back to safe defaults if nothing matches.
    """
    stem = Path(filename).stem

    # --- Format 1: dialer export ---
    # 20260615-120636_2012298_7576049254_VA_V6151206220002012298_tpenninger-all
    m = re.match(
        r"^(\d{8})"           # date block: 20260615
        r"-\d{6}"             # time block: 120636
        r"_\d+"               # some ID
        r"_(\d{7,15})"        # phone number
        r"_([A-Z]+)"          # loan/state code, e.g. VA
        r"_.+"                # another ID block
        r"_([a-zA-Z]+)"       # agent username: tpenninger
        r"(?:-\w+)?$",        # optional suffix: -all
        stem
    )
    if m:
        raw_date, phone, loan_code, agent_user = (
            m.group(1),
            m.group(2),
            m.group(3),
            m.group(4),
        )
        try:
            call_date = datetime.strptime(raw_date, "%Y%m%d").strftime("%Y-%m-%d")
        except ValueError:
            call_date = None
        return {
            # Dialer exports usually contain a username, not a spoken/full name.
            # Keep it separate so AI transcript extraction can find the real name.
            "agent_name": None,
            "agent_username": agent_user,
            "loan_hint": normalize_loan_hint(loan_code),
            "lead_phone": phone,
            "call_date":  call_date,
        }

    # --- Format 2: transcript export ---
    # John_Doe-5551234567-2026-05-28
    parts = stem.split("-")
    if len(parts) >= 4:
        return {
            "agent_name": parts[0].replace("_", " "),
            "agent_username": None,
            "loan_hint": None,
            "lead_phone": parts[1],
            "call_date":  "-".join(parts[2:5]),
        }

    # --- Fallback ---
    return {
        "agent_name": None,
        "agent_username": None,
        "loan_hint": None,
        "lead_phone": None,
        "call_date":  None,
    }
