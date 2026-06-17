"""
QAEngine — handles audio transcription (Deepgram) and AI evaluation (Ollama/local).
Compatible with deepgram-sdk v7+
Grading uses Ollama (free, local) via its OpenAI-compatible API.
"""
import json
from pathlib import Path

from deepgram import DeepgramClient
from openai import OpenAI

from config import load_key, DEEPGRAM_KEY_FILE


class QAEngine:
    def __init__(self):
        self.dg_client = DeepgramClient(api_key=load_key(DEEPGRAM_KEY_FILE))
        # Point to local Ollama — no API key needed
        self.ai_client = OpenAI(
            base_url="http://localhost:11434/v1",
            api_key="ollama",  # required by the client but not validated
        )

    # ------------------------------------------------------------------
    # Transcription
    # ------------------------------------------------------------------
    def transcribe_audio(self, file_path: str) -> str:
        """Transcribe a WAV/MP3 file using Deepgram nova-2 with diarization."""
        with open(file_path, "rb") as audio:
            audio_bytes = audio.read()

        response = self.dg_client.listen.v1.media.transcribe_file(
            request=audio_bytes,
            model="nova-2",
            smart_format=True,
            diarize=True,
        )
        return response.results.channels[0].alternatives[0].transcript

    # ------------------------------------------------------------------
    # AI Evaluation
    # ------------------------------------------------------------------
    def evaluate_call(self, transcript: str, metadata: dict) -> dict:
        """
        Grade a call transcript and return a structured JSON result.

        Expected metadata keys:
            duration (int)   — call length in seconds
            hangup   (str)   — who ended the call: 'Agent' | 'Customer' | 'System'
            transfer_ext (str) — transfer destination extension / department

        Returns dict with at minimum:
            loan_type, score (0-100), summary, areas_of_improvement,
            detected_issue, reasoning
        """
        known_agent = metadata.get("agent_name")
        agent_hint  = (
            f"The agent's name or username is known to be: {known_agent}."
            if known_agent
            else "The agent's name is unknown — try to identify it from the transcript (e.g. how they introduce themselves)."
        )

        prompt = f"""
You are a QA Auditor for a loan call center.

Evaluate the following call.

Metadata:
  - Duration: {metadata.get('duration', 'unknown')}s
  - Hangup source: {metadata.get('hangup', 'unknown')}
  - Transfer destination: {metadata.get('transfer_ext', 'none')}
  - {agent_hint}

Transcript:
{transcript[:6000]}

Tasks:
1. Identify the Loan Type (Mortgage, Personal, Auto, Student, or Unknown).
2. Identify the agent's full name or username from the transcript or metadata.
3. Verify whether the transfer destination matched the loan type.
4. Score the agent 0-100. Penalize if:
   - Agent hung up first without resolution.
   - Duration < 60s without a clear outcome.
   - Improper greeting or disclosure.
   - Poor objection handling.
5. Provide a brief summary and specific areas of improvement.

Return ONLY a JSON object with these keys:
  - "loan_type"            : string
  - "agent_name"           : string (full name or username, or null if unknown)
  - "score"                : integer (0-100)
  - "category"             : one of: referral, cold call, follow up, no evaluation
  - "summary"              : string
  - "areas_of_improvement" : string
  - "detected_issue"       : string (main compliance or quality issue, or "None")
  - "reasoning"            : string (brief explanation of the score)
"""
        response = self.ai_client.chat.completions.create(
            model="llama3.2",
            messages=[
                {"role": "system", "content": "You are a Call Center QA Manager. Always respond with valid JSON only, no extra text, no markdown."},
                {"role": "user",   "content": prompt},
            ],
            temperature=0,
        )
        raw = response.choices[0].message.content.strip()

        # Strip markdown code fences if present
        if "```" in raw:
            parts = raw.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                if part.startswith("{"):
                    raw = part
                    break

        # Find the outermost JSON object
        start = raw.find("{")
        end   = raw.rfind("}") + 1
        if start != -1 and end > start:
            raw = raw[start:end]

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # Last resort: use regex to extract key fields
            import re
            def extract(key):
                m = re.search(rf'"{key}"\s*:\s*"([^"]*)"', raw)
                return m.group(1) if m else None
            def extract_int(key):
                m = re.search(rf'"{key}"\s*:\s*(\d+)', raw)
                return int(m.group(1)) if m else None
            return {
                "loan_type":            extract("loan_type"),
                "agent_name":           extract("agent_name"),
                "score":                extract_int("score"),
                "category":             extract("category") or "no evaluation",
                "summary":              extract("summary"),
                "areas_of_improvement": extract("areas_of_improvement"),
                "detected_issue":       extract("detected_issue"),
                "reasoning":            extract("reasoning"),
            }

    # ------------------------------------------------------------------
    # Convenience: evaluate a plain-text transcript file
    # ------------------------------------------------------------------
    def evaluate_transcript_file(self, txt_path: str | Path, metadata: dict) -> dict:
        """Read a .txt transcript and evaluate it (no audio transcription needed)."""
        transcript = Path(txt_path).read_text(encoding="utf-8")
        return self.evaluate_call(transcript, metadata)
