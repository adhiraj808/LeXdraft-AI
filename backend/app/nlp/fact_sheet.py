"""FactSheet — the single source of truth for a case's facts.

Every value carries its provenance so nothing downstream has to guess:

  ``status``      PROVIDED  — the user wrote it; ``source_span`` quotes the prompt
                  INFERRED  — derived by spaCy/regex (no LLM key, or LLM silent)
                  MISSING   — not in the prompt; the draft must write
                              ``[TO BE CONFIRMED: <field>]``

The generator, validator and rules engine all read this object and are not
allowed to add facts of their own. The extractor fills it from the raw prompt;
nothing ever *normalises* a value (``"March 2026"`` stays ``"March 2026"``).
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

FactStatus = Literal["PROVIDED", "MISSING", "INFERRED"]

MISSING_MARKER = "[TO BE CONFIRMED: {field}]"


def missing_marker(field: str) -> str:
    """The exact placeholder the draft must contain for a missing fact."""
    return MISSING_MARKER.format(field=field)


class FactField(BaseModel):
    """One fact plus where it came from."""

    model_config = ConfigDict(str_strip_whitespace=True)

    value: Optional[str] = None
    status: FactStatus = "MISSING"
    source_span: Optional[str] = None

    def provided(self) -> bool:
        return self.status != "MISSING" and bool(self.value)


class PartyFact(BaseModel):
    """A party to the case. ``role`` is the user's wording, not a legal label."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str
    role: Optional[str] = None
    address: Optional[str] = None
    status: FactStatus = "PROVIDED"
    source_span: Optional[str] = None

    def display(self) -> str:
        if self.address:
            return f"{self.name}, {self.address}"
        return self.name


class FactSheet(BaseModel):
    """All the facts the draft is allowed to use. Nothing else is permitted."""

    model_config = ConfigDict(str_strip_whitespace=True)

    parties: List[PartyFact] = Field(default_factory=list)
    roles: Dict[str, str] = Field(default_factory=dict)
    contract_date: FactField = Field(default_factory=FactField)
    delivery_date: FactField = Field(default_factory=FactField)
    notice_dates: List[FactField] = Field(default_factory=list)
    incident_date: FactField = Field(default_factory=FactField)
    contract_value: FactField = Field(default_factory=FactField)
    damages_claimed: FactField = Field(default_factory=FactField)
    place: FactField = Field(default_factory=FactField)
    claim_type: FactField = Field(default_factory=FactField)
    statutes_cited_by_user: List[str] = Field(default_factory=list)
    relief_sought: FactField = Field(default_factory=FactField)
    has_arbitration_clause: FactField = Field(default_factory=FactField)
    raw_prompt: str = ""

    # ---- convenience -----------------------------------------------------

    def party_names(self) -> List[str]:
        return [p.name for p in self.parties if p.name]

    def get(self, field_name: str) -> Optional[FactField]:
        value = getattr(self, field_name, None)
        return value if isinstance(value, FactField) else None

    def missing_fields(self) -> List[str]:
        """Names of the top-level FactFields that are still MISSING."""
        out: List[str] = []
        for name, value in self.__dict__.items():
            if isinstance(value, FactField) and value.status == "MISSING":
                out.append(name)
        return out

    def to_prompt_block(self) -> str:
        """Render the FactSheet as the block injected into every LLM prompt.

        MISSING facts are rendered as the literal placeholder so the model
        copies it instead of inventing a value.
        """
        lines: List[str] = ["FACT SHEET (use ONLY these facts — never invent):"]

        if self.parties:
            lines.append("Parties:")
            for p in self.parties:
                role = f" ({p.role})" if p.role else ""
                addr = f", {p.address}" if p.address else ""
                lines.append(f"  - {p.name}{role}{addr}")
        else:
            lines.append(f"Parties: {missing_marker('parties')}")

        scalar_fields = (
            ("contract_date", "Contract date"),
            ("delivery_date", "Delivery date"),
            ("incident_date", "Incident date"),
            ("contract_value", "Contract value"),
            ("damages_claimed", "Damages claimed"),
            ("place", "Place"),
            ("claim_type", "Claim type"),
            ("relief_sought", "Relief sought"),
            ("has_arbitration_clause", "Arbitration clause"),
        )
        for attr, label in scalar_fields:
            field = self.get(attr)
            if field and field.provided():
                lines.append(f"{label}: {field.value}")
            else:
                lines.append(f"{label}: {missing_marker(label.lower())}")

        if self.notice_dates:
            for i, nd in enumerate(self.notice_dates, 1):
                if nd.provided():
                    lines.append(f"Notice date {i}: {nd.value}")
        else:
            lines.append(f"Notice date: {missing_marker('notice date')}")

        if self.statutes_cited_by_user:
            lines.append(
                "Statutes cited by the user: " + ", ".join(self.statutes_cited_by_user)
            )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Grounding check + no-LLM fallback construction
# ---------------------------------------------------------------------------

_WS_RE = re.compile(r"\s+")


def _normalise(text: str) -> str:
    return _WS_RE.sub(" ", (text or "").lower()).strip()


def _tokens(text: str) -> List[str]:
    return [t for t in re.split(r"[^a-z0-9]+", _normalise(text)) if len(t) > 1]


def is_grounded(value: Optional[str], raw_prompt: str, threshold: float = 0.7) -> bool:
    """True when ``value`` can be traced back to the raw prompt.

    Exact substring match, else token-overlap ratio >= threshold. Fuzzy
    matching tolerates number formatting ("5,00,000" vs "500000") without
    accepting an invented name.
    """
    if not value:
        return False
    value_norm = _normalise(value)
    prompt_norm = _normalise(raw_prompt)
    if not value_norm or not prompt_norm:
        return False
    if value_norm in prompt_norm:
        return True

    value_tokens = _tokens(value)
    if not value_tokens:
        return False
    prompt_tokens = set(_tokens(raw_prompt))
    overlap = sum(1 for t in value_tokens if t in prompt_tokens)
    return (overlap / len(value_tokens)) >= threshold


def grounded_field(value: Optional[str], raw_prompt: str) -> FactField:
    """Build a PROVIDED FactField only when the value is grounded; else MISSING.

    This is the extractor's guard-rail: an LLM answer that is not in the
    prompt is discarded, never silently trusted.
    """
    if value and is_grounded(value, raw_prompt):
        return FactField(value=value, status="PROVIDED", source_span=value)
    return FactField(status="MISSING")


def grounded_party(
    name: Optional[str],
    raw_prompt: str,
    role: Optional[str] = None,
    address: Optional[str] = None,
) -> Optional[PartyFact]:
    if not name or not is_grounded(name, raw_prompt):
        return None
    return PartyFact(
        name=name,
        role=role,
        address=address if address and is_grounded(address, raw_prompt) else None,
        status="PROVIDED",
        source_span=name,
    )


# Simple patterns for the no-key fallback. Deliberately conservative: a wrong
# INFERRED fact is worse than a MISSING one.
_MONEY_RE = re.compile(
    r"(?:Rs\.?|INR|₹)\s*[\d,]+(?:\.\d{2})?(?:\s*(?:lakhs?|crores?|thousands?))?",
    re.IGNORECASE,
)
_DATE_RE = re.compile(
    r"\b(?:\d{1,2}[\s/-])?(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|"
    r"Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)[\s,/-]+\d{2,4}\b",
    re.IGNORECASE,
)
_PLACE_RE = re.compile(r"\b(?:at|in|before)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)")
_STATUTE_RE = re.compile(
    r"\b(?:Section|Sec\.|S\.)\s*\d+[A-Za-z]?(?:\s*(?:of|r/w|read with)\s*"
    r"[A-Z][\w\s]*Act(?:\s+\d{4})?)?\b",
    re.IGNORECASE,
)


def build_from_text(raw_prompt: str, entities: Optional[Dict[str, Any]] = None) -> FactSheet:
    """Deterministic FactSheet used when no LLM key is configured (all INFERRED).

    ``entities`` is the output of ``LegalNERExtractor.extract`` when available;
    otherwise plain regexes are used. Nothing here is normalised — captured
    text is stored exactly as written in the prompt.
    """
    entities = entities or {}
    prompt = raw_prompt or ""

    persons = [p for p in (entities.get("persons") or []) if p]
    orgs = [o for o in (entities.get("organizations") or []) if o]

    parties: List[PartyFact] = []
    for p in persons[:1]:
        if is_grounded(p, prompt):
            parties.append(
                PartyFact(name=p, status="INFERRED", source_span=p)
            )
    for o in orgs[:2]:
        if is_grounded(o, prompt) and not any(x.name == o for x in parties):
            parties.append(PartyFact(name=o, status="INFERRED", source_span=o))

    money = [m for m in (entities.get("money") or []) if m]
    if not money:
        money = [m.group(0).strip() for m in _MONEY_RE.finditer(prompt)]

    dates = [d for d in (entities.get("dates") or []) if d]
    if not dates:
        dates = [d.group(0).strip() for d in _DATE_RE.finditer(prompt)]

    places = [p for p in (entities.get("locations") or []) if p]
    if not places:
        places = [m.group(1).strip() for m in _PLACE_RE.finditer(prompt)]

    statutes = [s for s in (entities.get("statutes") or []) if s]
    if not statutes:
        statutes = [m.group(0).strip() for m in _STATUTE_RE.finditer(prompt)]

    sheet = FactSheet(raw_prompt=prompt)
    sheet.parties = parties
    sheet.statutes_cited_by_user = list(dict.fromkeys(statutes))

    if money:
        sheet.contract_value = FactField(
            value=money[0], status="INFERRED", source_span=money[0]
        )
        if len(money) > 1:
            sheet.damages_claimed = FactField(
                value=money[1], status="INFERRED", source_span=money[1]
            )
    if dates:
        sheet.incident_date = FactField(
            value=dates[0], status="INFERRED", source_span=dates[0]
        )
    if places:
        sheet.place = FactField(
            value=places[0], status="INFERRED", source_span=places[0]
        )
    return sheet
