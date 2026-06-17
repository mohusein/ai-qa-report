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


def parse_filename(filename: str) -> dict:
    """
    Return a dict with keys: agent_name, lead_phone, call_date (YYYY-MM-DD).
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
        r"_[A-Z]+"            # state/code
        r"_.+"                # another ID block
        r"_([a-zA-Z]+)"       # agent username: tpenninger
        r"(?:-\w+)?$",        # optional suffix: -all
        stem
    )
    if m:
        raw_date, phone, agent_user = m.group(1), m.group(2), m.group(3)
        try:
            call_date = datetime.strptime(raw_date, "%Y%m%d").strftime("%Y-%m-%d")
        except ValueError:
            call_date = None
        return {
            "agent_name": agent_user.capitalize(),
            "lead_phone": phone,
            "call_date":  call_date,
        }

    # --- Format 2: transcript export ---
    # John_Doe-5551234567-2026-05-28
    parts = stem.split("-")
    if len(parts) >= 4:
        return {
            "agent_name": parts[0].replace("_", " "),
            "lead_phone": parts[1],
            "call_date":  "-".join(parts[2:5]),
        }

    # --- Fallback ---
    return {
        "agent_name": None,
        "lead_phone": None,
        "call_date":  None,
    }
