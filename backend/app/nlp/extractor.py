"""Prompt -> structured case fields via Groq LLM."""
import json
import logging
import re
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


def extract_case_fields(prompt: str) -> Optional[Dict]:
    """Extract structured fields from a free prompt. None on any failure."""
    if not settings.GROQ_API_KEY:
        return None
    payload = {
        "model": settings.GROQ_MODEL,
        "messages": [
            {"role": "system", "content": "You extract structured legal case data. Output only JSON."},
            {"role": "user", "content": EXTRACT_PROMPT + prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 1500,
    }
    delays = [3, 8, 20]
    for attempt in range(4):
        try:
            with httpx.Client(timeout=90.0) as client:
                resp = client.post(
                    GROQ_API_URL,
                    headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
                    json=payload,
                )
            if resp.status_code == 200:
                text = resp.json()["choices"][0]["message"]["content"].strip()
                # Strip markdown fences (```json ... ```) if present.
                text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
                text = re.sub(r"\s*```$", "", text)
                data = None
                try:
                    parsed = json.loads(text)
                    if isinstance(parsed, dict):
                        data = parsed
                except Exception:
                    m = re.search(r"\{.*\}", text, re.DOTALL)
                    if m:
                        try:
                            parsed = json.loads(m.group(0))
                            if isinstance(parsed, dict):
                                data = parsed
                        except Exception:
                            data = None
                if data and data.get("case_description"):
                    return data
                logger.warning("Groq extraction returned unparseable JSON, falling back.")
                return None
            if resp.status_code in (429, 500, 502, 503) and attempt < 3:
                wait = resp.headers.get("retry-after")
                wait_s = float(wait) if wait and str(wait).replace(".", "", 1).isdigit() else delays[attempt]
                logger.info(f"Groq extraction status {resp.status_code}, retrying in {wait_s}s...")
                time.sleep(wait_s)
                continue
            logger.warning(f"Groq extraction status {resp.status_code}, falling back.")
            return None
        except Exception:
            if attempt < 3:
                time.sleep(delays[attempt])
                continue
            logger.warning("Groq extraction failed repeatedly, falling back.")
            return None
    return None
