import json
import re

from deepgram import DeepgramClient
from openai import OpenAI

from config import DEEPGRAM_KEY_FILE, load_key

QA_MODEL = "llama3.2"
LOCAL_AI_BASE_URL = "http://localhost:11434/v1"


# Clients are loaded lazily so importing this file does not immediately read
# API key files. Tests can also monkeypatch these globals.
dg_client = None
ai_client = None


def get_deepgram_client():
    global dg_client
    if dg_client is None:
        dg_client = DeepgramClient(api_key=load_key(DEEPGRAM_KEY_FILE))
    return dg_client


def get_openai_client():
    global ai_client
    if ai_client is None:
        # Use local Ollama's OpenAI-compatible endpoint. This avoids failing when
        # the OpenAI account has no available quota.
        ai_client = OpenAI(base_url=LOCAL_AI_BASE_URL, api_key="ollama")
    return ai_client


class QAEngine:
    LOAN_TYPE_PATTERNS = {
        "VA": [
            r"\bVA\b",
            r"\bV\.A\.\b",
            r"\bveteran(?:s)?\b",
            r"\bmilitary\b",
            r"\bservice member(?:s)?\b",
            r"\bVA loan(?:s)?\b",
            r"\bVA mortgage\b",
            r"\bveterans affairs\b",
        ],
        "Debt": [
            r"\bdebt\b",
            r"\bdebt relief\b",
            r"\bdebt consolidation\b",
            r"\bcredit card(?:s)?\b",
            r"\bunsecured debt\b",
            r"\bcollections?\b",
            r"\bsettlement\b",
            r"\bloan consolidation\b",
            r"\bpersonal loan\b",
        ],
        "Mortgage": [
            r"\bmortgage\b",
            r"\bhome loan\b",
            r"\brefinance\b",
            r"\brefi\b",
            r"\bcash[- ]?out\b",
            r"\bFHA\b",
            r"\bconventional loan\b",
            r"\bpurchase loan\b",
            r"\bhome equity\b",
            r"\bHELOC\b",
        ],
    }

    LOAN_TYPE_TRANSFER_HINTS = {
        "VA": ["va", "veteran", "military"],
        "Debt": ["debt", "credit", "settlement", "consolidation", "personal"],
        "Mortgage": ["mortgage", "home", "refi", "refinance", "fha", "heloc"],
    }

    def detect_loan_type(self, transcript, metadata=None):
        """
        Deterministic loan-type detection used to support/correct the local LLM.
        Returns a label plus the keyword evidence that caused the decision.
        """
        metadata = metadata or {}
        loan_hint = metadata.get("loan_hint")
        if loan_hint in {"VA", "Debt", "Mortgage"}:
            return {
                "loan_type": loan_hint,
                "confidence": 99,
                "evidence": f"filename/dialer loan_hint={loan_hint}",
                "scores": {
                    "VA": 1 if loan_hint == "VA" else 0,
                    "Debt": 1 if loan_hint == "Debt" else 0,
                    "Mortgage": 1 if loan_hint == "Mortgage" else 0,
                },
            }

        text = f"{metadata.get('transfer_ext') or ''}\n{metadata.get('loan_hint') or ''}\n{transcript or ''}"
        scores = {}
        evidence = {}

        for loan_type, patterns in self.LOAN_TYPE_PATTERNS.items():
            matches = []
            for pattern in patterns:
                found = re.findall(pattern, text, flags=re.IGNORECASE)
                if found:
                    matches.extend(
                        [item if isinstance(item, str) else " ".join(item) for item in found]
                    )
            scores[loan_type] = len(matches)
            evidence[loan_type] = matches[:5]

        transfer = str(metadata.get("transfer_ext") or "").lower()
        for loan_type, hints in self.LOAN_TYPE_TRANSFER_HINTS.items():
            if any(hint in transfer for hint in hints):
                scores[loan_type] += 2
                evidence[loan_type].append(f"transfer_ext={metadata.get('transfer_ext')}")

        best_type = max(scores, key=scores.get)
        if scores[best_type] == 0:
            return {
                "loan_type": "Unknown",
                "confidence": 0,
                "evidence": "",
                "scores": scores,
            }

        sorted_scores = sorted(scores.values(), reverse=True)
        margin = sorted_scores[0] - (sorted_scores[1] if len(sorted_scores) > 1 else 0)
        confidence = min(95, 55 + (scores[best_type] * 10) + (margin * 10))

        return {
            "loan_type": best_type,
            "confidence": confidence,
            "evidence": ", ".join(dict.fromkeys(evidence[best_type])),
            "scores": scores,
        }

    def _response_to_dict(self, response):
        """Deepgram SDK responses may be dict-like or model objects."""
        if isinstance(response, dict):
            return response
        if hasattr(response, "to_dict"):
            return response.to_dict()
        if hasattr(response, "dict"):
            return response.dict()
        return response

    def _speaker_labeled_transcript(self, alternative):
        """
        Convert Deepgram diarized words into readable speaker turns.
        Falls back to the flat transcript when word-level speaker data is absent.
        """
        words = alternative.get("words") or []
        if not words:
            return alternative.get("transcript", "")

        lines = []
        current_speaker = None
        current_words = []

        for word in words:
            speaker = word.get("speaker", "Unknown")
            text = word.get("punctuated_word") or word.get("word") or ""
            text = text.strip()
            if not text:
                continue

            if speaker != current_speaker:
                if current_words:
                    lines.append(
                        f"Speaker {current_speaker}: {' '.join(current_words)}"
                    )
                current_speaker = speaker
                current_words = [text]
            else:
                current_words.append(text)

        if current_words:
            lines.append(f"Speaker {current_speaker}: {' '.join(current_words)}")

        return "\n".join(lines)

    def transcribe_audio(self, file_path):
        with open(file_path, "rb") as audio:
            audio_bytes = audio.read()

            response = get_deepgram_client().listen.v1.media.transcribe_file(
                request=audio_bytes,
                model="nova-2",
                smart_format=True,
                diarize=True,
                punctuate=True,
            )
            response = self._response_to_dict(response)
            alternative = response["results"]["channels"][0]["alternatives"][0]
            return self._speaker_labeled_transcript(alternative)

    def _parse_llm_json(self, raw: str) -> dict:
        """Robustly parse JSON from an LLM response, stripping markdown fences."""
        raw = raw.strip()
        # Strip markdown code fences
        if "```" in raw:
            parts = raw.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                if part.startswith("{"):
                    raw = part
                    break
        # Find outermost JSON object
        start = raw.find("{")
        end   = raw.rfind("}") + 1
        if start != -1 and end > start:
            raw = raw[start:end]
        return json.loads(raw)

    def extract_agent_name(self, transcript, metadata=None):
        metadata = metadata or {}
        username = metadata.get("agent_username") or metadata.get("agent_name")
        username_hint = (
            f"The agent's username from the dialer/filename is: {username}. Use this as a fallback if no spoken name is found."
            if username
            else "No username is available from metadata."
        )

        prompt = f"""
Identify the call center agent's name from this transcript.

Rules:
- Prefer a spoken self-introduction from the agent, such as "this is Sarah",
  "my name is John", or "you're speaking with Mike".
- A customer repeating the agent's name is supporting evidence.
- {username_hint}
- Do not guess. If the name is not clear, return null.

Transcript:
{transcript[:4000]}

Return ONLY a JSON object with these exact keys:
  "agent_name": string or null
  "confidence": integer 0-100
  "evidence": string
"""

        response = get_openai_client().chat.completions.create(
            model=QA_MODEL,
            messages=[
                {"role": "system", "content": "You extract agent names from call transcripts. Return only valid JSON, no markdown."},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )

        try:
            result = self._parse_llm_json(response.choices[0].message.content)
        except Exception:
            # Fall back to username from filename if AI parsing fails
            return {
                "agent_name": username.capitalize() if username else None,
                "confidence": 30 if username else 0,
                "evidence": f"Fallback to filename username: {username}",
            }

        agent_name = result.get("agent_name")
        if isinstance(agent_name, str):
            agent_name = agent_name.strip()
            if agent_name.lower() in {"", "none", "null", "unknown", "n/a"}:
                agent_name = None
        else:
            agent_name = None

        # If AI found nothing, fall back to the username from the filename
        if not agent_name and username:
            agent_name = username.capitalize()
            result["confidence"] = min(result.get("confidence", 0), 35)
            result["evidence"] = (result.get("evidence") or "") + f" | Fallback: filename username={username}"

        try:
            confidence = max(0, min(100, int(result.get("confidence", 0))))
        except Exception:
            confidence = 0

        return {
            "agent_name": agent_name,
            "confidence": confidence,
            "evidence": str(result.get("evidence", "")),
        }

    def evaluate_call(self, transcript, metadata):
        metadata = metadata or {}
        agent_info = self.extract_agent_name(transcript, metadata)
        rule_loan = self.detect_loan_type(transcript, metadata)

        prompt = f"""
        You are a QA Auditor for a loan call center.

        Evaluate the following call.

        Metadata:
          - Duration: {metadata.get('duration', 'unknown')}s
          - Hangup source: {metadata.get('hangup', 'unknown')}
          - Transfer destination: {metadata.get('transfer_ext', 'none')}
          - Agent name detected before scoring: {agent_info.get('agent_name')}
          - Agent username from filename, if any: {metadata.get('agent_username')}
          - Loan hint from filename/dialer, if any: {metadata.get('loan_hint')}
          - Rule-based loan hint: {rule_loan.get('loan_type')} with evidence: {rule_loan.get('evidence')}

        Transcript:
        {transcript[:12000]}

        Tasks:
        1. Identify the Loan Type: Mortgage, Debt, VA, or Unknown.
           - Mortgage includes mortgage, home loan, refinance/refi, FHA,
             cash-out, home equity, HELOC, conventional, purchase.
           - Debt includes debt relief, credit cards, unsecured debt,
             consolidation, settlement, collections, personal loan.
           - VA includes VA loans, veterans, military, service members,
             Veterans Affairs, or VA mortgage.
           - If both VA and Mortgage appear, choose VA when the call is about
             a VA-backed mortgage/loan.
        2. Verify whether the transfer destination matched the loan type.
        3. Include the agent name if available. Do not invent one.
        4. Score the agent 0-100. Penalize if:
           - Agent hung up first without resolution.
           - Duration < 60s without a clear outcome.
           - Improper greeting or disclosure.
           - Poor objection handling.
        5. Provide a brief summary and specific areas of improvement.

        Return ONLY strict JSON with these keys:
          - "loan_type": string
          - "agent_name": string or null
          - "agent_name_confidence": integer from 0 to 100
          - "agent_name_evidence": string
          - "score": integer from 0 to 100
          - "category": one of: referral, cold call, follow up, no evaluation
          - "summary": string
          - "areas_of_improvement": string
          - "detected_issue": string
          - "reasoning": string
        """

        response = get_openai_client().chat.completions.create(
            model=QA_MODEL,
            messages=[
                {"role": "system", "content": "You are a QA Auditor. Return only valid JSON, no markdown."},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )

        # Parse and validate model output
        try:
            result = self._parse_llm_json(response.choices[0].message.content)
        except Exception:
            return {
                "loan_type": "Unknown",
                "score": 0,
                "reasoning": "Model returned non-JSON response.",
                "agent_name": agent_info.get("agent_name"),
                "agent_name_confidence": agent_info.get("confidence", 0),
                "agent_name_evidence": agent_info.get("evidence", ""),
                "category": "no evaluation",
                "summary": "",
                "areas_of_improvement": "",
                "detected_issue": "Unknown",
                "loan_type_confidence": rule_loan.get("confidence", 0),
                "loan_type_evidence": rule_loan.get("evidence", ""),
            }

        # Normalize and validate loan_type
        allowed = {"mortgage": "Mortgage", "debt": "Debt", "va": "VA"}
        loan_type_raw = str(result.get("loan_type", "")).strip()
        loan_type_key = loan_type_raw.lower()
        loan_type = allowed.get(loan_type_key)
        if not loan_type:
            # try to map by keyword
            if "mort" in loan_type_key:
                loan_type = "Mortgage"
            elif "va" in loan_type_key or "veteran" in loan_type_key:
                loan_type = "VA"
            elif "debt" in loan_type_key or "collection" in loan_type_key:
                loan_type = "Debt"
            else:
                loan_type = "Unknown"

        if rule_loan["loan_type"] != "Unknown":
            # Prefer deterministic evidence over a weak/unknown local-model guess.
            if loan_type == "Unknown" or rule_loan["confidence"] >= 75:
                loan_type = rule_loan["loan_type"]

        # Ensure score exists and is an int
        try:
            score = int(result.get("score", 0))
        except Exception:
            score = 0
        score = max(0, min(100, score))

        reasoning = result.get("reasoning", "")
        agent_name = (
            agent_info.get("agent_name")
            or result.get("agent_name")
            or metadata.get("agent_name")
        )
        if isinstance(agent_name, str):
            agent_name = agent_name.strip() or None

        category = str(result.get("category", "no evaluation")).strip().lower()
        allowed_categories = {"referral", "cold call", "follow up", "no evaluation"}
        if category not in allowed_categories:
            category = "no evaluation"

        return {
            "loan_type": loan_type,
            "score": score,
            "reasoning": reasoning,
            "agent_name": agent_name,
            "agent_name_confidence": agent_info.get("confidence", 0),
            "agent_name_evidence": agent_info.get("evidence", ""),
            "category": category,
            "summary": result.get("summary", ""),
            "areas_of_improvement": result.get("areas_of_improvement", ""),
            "detected_issue": result.get("detected_issue", "None"),
            "loan_type_confidence": rule_loan.get("confidence", 0),
            "loan_type_evidence": rule_loan.get("evidence", ""),
        }

    def evaluate_transcript_file(self, txt_path, metadata):
        """Read a .txt transcript and evaluate it without audio transcription."""
        from pathlib import Path

        transcript = Path(txt_path).read_text(encoding="utf-8")
        return self.evaluate_call(transcript, metadata)
