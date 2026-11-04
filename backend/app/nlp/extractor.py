"""Prompt -> structured case fields via Groq LLM."""

import json
import logging
import re
import threading
import time
from typing import Dict, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

EXTRACT_PROMPT = """You convert a free-form legal case description into structured JSON.
Extract these fields from the user's text:
- title: short case title like "Complainant vs Respondent"
- jurisdiction: place/city mentioned (or empty string)
- petitioner_name: complainant/petitioner/plaintiff name (or empty string)
- respondent_name: accused/respondent/defendant name (or empty string)
- incident_date: date of the key incident in YYYY-MM-DD if mentioned (or empty string)
- case_description: a clean 4-8 sentence formal narration of the facts in English legal style, expanding abbreviations like "5 lakh" to "Rs. 5,00,000" and "420" to "Section 420 IPC" where contextually clear
- sections_alleged: comma-separated statutes mentioned or implied (or empty string)
- relief_sought: what the client wants (or empty string)

Respond with ONLY a valid JSON object, no markdown, no explanation.
User text:
"""

_http: Optional[httpx.Client] = None
_http_lock = threading.Lock()


def _client() -> httpx.Client:
    """One pooled client for all extraction calls (keep-alive instead of a new TLS handshake each time)."""
    global _http
    with _http_lock:
        if _http is None:
            _http = httpx.Client(
                timeout=httpx.Timeout(90.0, connect=10.0),
                limits=httpx.Limits(max_connections=4, max_keepalive_connections=2),
            )
        return _http


def _parse_json_object(text: str) -> Optional[Dict]:
    """Parse a JSON object from model output, tolerating markdown fences and surrounding prose."""
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    candidates = [text]
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        candidates.append(match.group(0))
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except Exception:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def extract_case_fields(prompt: str) -> Optional[Dict]:
    """Extract structured fields from a free prompt. None on any failure.

    Blocking (network + retry sleeps): call it with ``asyncio.to_thread``.
    """
    if not settings.GROQ_API_KEY:
        return None
    payload = {
        "model": settings.GROQ_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You extract structured legal case data. Output only JSON.",
            },
            {"role": "user", "content": EXTRACT_PROMPT + prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 1500,
    }
    delays = [3, 8, 20]
    for attempt in range(4):
        try:
            resp = _client().post(
                GROQ_API_URL,
                headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
                json=payload,
            )
            if resp.status_code == 200:
                msg = resp.json()["choices"][0]["message"]
                # Some reasoning models (e.g. gpt-oss) may put the answer in "reasoning".
                # That is acceptable HERE only because the text must parse as the expected JSON.
                data = _parse_json_object(
                    msg.get("content") or ""
                ) or _parse_json_object(msg.get("reasoning") or "")
                if data and data.get("case_description"):
                    return data
                logger.warning(
                    "Groq extraction returned unparseable JSON, falling back."
                )
                return None
            if resp.status_code in (429, 500, 502, 503) and attempt < 3:
                # On 429 (rate limit), fail fast since daily limit won't recover quickly
                if resp.status_code == 429:
                    logger.warning("Groq extraction rate limited, failing fast")
                    return None
                wait = resp.headers.get("retry-after")
                wait_s = (
                    float(wait)
                    if wait and str(wait).replace(".", "", 1).isdigit()
                    else delays[attempt]
                )
                wait_s = min(wait_s, 30.0)
                logger.info(
                    f"Groq extraction status {resp.status_code}, retrying in {wait_s}s..."
                )
                time.sleep(wait_s)
                continue
            logger.warning(f"Groq extraction status {resp.status_code}, falling back.")
            return None
        except Exception as e:
            if attempt < 3:
                time.sleep(delays[attempt])
                continue
            logger.warning(
                f"Groq extraction failed repeatedly ({type(e).__name__}), falling back."
            )
            return None
    return None
