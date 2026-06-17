"""
Central configuration for the QA Report system.
"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# --- API Keys ---
# Store your keys in these files, one key per file (no quotes, just the raw key)
OPENAI_KEY_FILE   = BASE_DIR / "api_key.txt"
DEEPGRAM_KEY_FILE = BASE_DIR / "deepgram_key.txt"

def load_key(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(
            f"API key file not found: {path}\n"
            f"Create the file and paste your key inside it."
        )
    return path.read_text().strip()

# --- SQLite Database (no installation needed) ---
DB_PATH = BASE_DIR / "qa_reports.db"

# --- Paths ---
TRANSCRIPT_DIR = BASE_DIR / "output"   # folder with .txt transcript files
