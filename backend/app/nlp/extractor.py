"""Prompt -> structured FactSheet via LLM (or deterministic fallback).

The LLM is asked to extract ONLY the fields listed in EXTRACT_PROMPT.
No narration, no date normalisation, no completion. Missing fields
become MISSING in the FactSheet.

Grounding check: every extracted value must be traceable to the raw
prompt; otherwise it is downgraded to MISSING.
"""

import json
import logging
import threading
import time
from typing import Dict, Optional

import httpx

from app.core.config import settings
from app.nlp.fact_sheet import (
    FactSheet,
    grounded_party,
    is_grounded,
    build_from_text,
    FactField,
)

logger = logging.getLogger(__name__)
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

EXTRACT_PROMPT = """You extract structured legal case facts from the user's text.
Return ONLY a valid JSON object with these exact keys — no narration, no explanation,
no markdown fences. If a field is not explicitly stated in the text, use null.

Keys:
- petitioner_name: the complainant/plaintiff/petitioner name (or null)
- respondent_name: the accused/respondent/defendant name (or null)
- contract_date: the contract/execution date as written (or null)
- delivery_date: the promised delivery/performance date as written (or null)
- notice_dates: array of legal notice dates as written (or [])
- incident_date: the key incident/breach date as written (or null)
- contract_value: the contract amount/consideration as written (or null)
- damages_claimed: the damages amount claimed as written (or null)
- place: the place/jurisdiction/city as written (or null)
- claim_type: one of "Breach of Contract", "Cheque Bounce", "Divorce", "Termination", "Eviction", "Specific Performance", "Other" (or null)
- statutes_cited_by_user: array of statute references the user explicitly mentions (or [])
- relief_sought: what the client wants, verbatim (or null)
- has_arbitration_clause: "yes" | "no" | "unknown" (or null)

User text:
"""

_http: Optional[httpx.Client] = None
_http_lock = threading.Lock()


def _client() -> httpx.Client:
    global _http
    with _http_lock:
        if _http is None:
            _http = httpx.Client(
                timeout=httpx.Timeout(90.0, connect=10.0),
                limits=httpx.Limits(max_connections=4, max_keepalive_connections=2),
            )
        return _http


def _parse_json_object(text: str) -> Optional[Dict]:
    text = text.strip()
    # Strip markdown fences if present
    if text.startswith("```"):
        text = text[3:]
        if text.startswith("json"):
            text = text[4:]
        text = text.rstrip("`").strip()
    try:
        parsed = json.loads(text)
    except Exception:
        # Try to find a JSON object inside
        import re

        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(0))
            except Exception:
                return None
        else:
            return None
    return parsed if isinstance(parsed, dict) else None


def _llm_extract(prompt: str) -> Optional[Dict]:
    """Call the LLM to extract fields. Returns dict or None on failure."""
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
        "temperature": 0.0,
        "max_tokens": 2000,
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
                data = _parse_json_object(
                    msg.get("content") or ""
                ) or _parse_json_object(msg.get("reasoning") or "")
                if data:
                    return data
                logger.warning("Groq extraction returned unparseable JSON")
                return None
            if resp.status_code in (429, 500, 502, 503) and attempt < 3:
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
            logger.warning(f"Groq extraction status {resp.status_code}, failing.")
            return None
        except Exception as e:
            if attempt < 3:
                time.sleep(delays[attempt])
                continue
            logger.warning(f"Groq extraction failed repeatedly ({type(e).__name__}), failing.")
            return None
    return None


def _build_fact_sheet(raw_prompt: str, llm_data: Optional[Dict], entities: Optional[Dict] = None) -> FactSheet:
    """Build a grounded FactSheet from LLM output + raw prompt + NER entities."""
    # Start from deterministic fallback (all INFERRED)
    sheet = build_from_text(raw_prompt, entities)

    if not llm_data:
        return sheet

    # Override with LLM-provided values IF they are grounded in the prompt
    # Petitioner / Respondent
    pet = llm_data.get("petitioner_name")
    if pet and is_grounded(pet, raw_prompt):
        p = grounded_party(pet, raw_prompt)
        if p:
            sheet.parties = [p] + [x for x in sheet.parties if x.name != p.name]

    resp = llm_data.get("respondent_name")
    if resp and is_grounded(resp, raw_prompt):
        r = grounded_party(resp, raw_prompt)
        if r:
            # Add as second party if not duplicate
            if not any(x.name == r.name for x in sheet.parties):
                sheet.parties.append(r)

    # Scalar fields — grounded override
    scalar_map = {
        "contract_date": "contract_date",
        "delivery_date": "delivery_date",
        "incident_date": "incident_date",
        "contract_value": "contract_value",
        "damages_claimed": "damages_claimed",
        "place": "place",
        "claim_type": "claim_type",
        "relief_sought": "relief_sought",
        "has_arbitration_clause": "has_arbitration_clause",
    }
    for llm_key, sheet_attr in scalar_map.items():
        val = llm_data.get(llm_key)
        if val and is_grounded(val, raw_prompt):
            setattr(
                sheet,
                sheet_attr,
                FactField(value=val, status="PROVIDED", source_span=val),
            )

    # Array fields
    notice_dates = llm_data.get("notice_dates") or []
    if notice_dates:
        grounded_notices = [
            FactField(value=d, status="PROVIDED", source_span=d)
            for d in notice_dates
            if d and is_grounded(d, raw_prompt)
        ]
        if grounded_notices:
            sheet.notice_dates = grounded_notices

    statutes = llm_data.get("statutes_cited_by_user") or []
    if statutes:
        grounded_statutes = [
            s for s in statutes if s and is_grounded(s, raw_prompt)
        ]
        if grounded_statutes:
            sheet.statutes_cited_by_user = list(
                dict.fromkeys(sheet.statutes_cited_by_user + grounded_statutes)
            )

    return sheet


def extract_case_fields(
    prompt: str, entities: Optional[Dict] = None
) -> Optional[FactSheet]:
    """Extract a FactSheet from a free prompt.

    Returns a FactSheet on success (never None — falls back to deterministic).
    """
    llm_data = _llm_extract(prompt)
    return _build_fact_sheet(prompt, llm_data, entities)