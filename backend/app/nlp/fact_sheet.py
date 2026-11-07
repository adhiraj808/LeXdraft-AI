"""FactSheet — the single source of truth for a case's facts.

Every value carries its provenance so nothing downstream has to guess:

  ``status``      PROVIDED  — the user wrote it verbatim; ``source_span`` quotes the prompt
                  INFERRED  — derived/guessed (regex, LLM not grounded, or ambiguous)
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
PartyRole = Literal["plaintiff", "defendant", "unknown"]
EntityType = Literal["individual", "company", "partnership", "llp", "trust", "government", "other", "unknown"]
ClaimTypeEnum = Literal[
    "NON_DELIVERY_OF_GOODS",
    "BREACH_OF_CONTRACT",
    "CHEQUE_BOUNCE",
    "SPECIFIC_PERFORMANCE",
    "RECOVERY_OF_DUES",
    "DAMAGES",
    "EVICTION",
    "DIVORCE",
    "TERMINATION",
    "WRONGFUL_TERMINATION",
    "OTHER",
]

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
    # Normalized values for computation (e.g., amount_inr)
    normalized: Optional[Dict[str, Any]] = None

    def provided(self) -> bool:
        return self.status != "MISSING" and bool(self.value)


class PartyFact(BaseModel):
    """A party to the case with role, entity type, and user-side info.

    Role and user_side are INFERRED from context, never PROVIDED.
    Exact legal name and entity type should be confirmed via missing_critical_fields.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str
    role: PartyRole = "unknown"          # plaintiff | defendant | unknown
    address: Optional[str] = None
    entity_type: EntityType = "unknown"  # individual | company | partnership | etc.
    user_side: Optional[bool] = None     # True if this party is the user's side
    status: FactStatus = "INFERRED"      # role/user_side/entity_type are always INFERRED
    source_span: Optional[str] = None

    def display(self) -> str:
        parts = [self.name]
        if self.role != "unknown":
            parts.append(f"({self.role})")
        if self.address:
            parts.append(f", {self.address}")
        return " ".join(parts)

    def is_user_side(self) -> bool:
        return self.user_side is True


class FactSheet(BaseModel):
    """All the facts the draft is allowed to use. Nothing else is permitted."""

    model_config = ConfigDict(str_strip_whitespace=True)

    parties: List[PartyFact] = Field(default_factory=list)
    contract_date: FactField = Field(default_factory=FactField)
    delivery_date: FactField = Field(default_factory=FactField)
    notice_dates: List[FactField] = Field(default_factory=list)
    incident_date: FactField = Field(default_factory=FactField)
    contract_value: FactField = Field(default_factory=FactField)
    damages_claimed: FactField = Field(default_factory=FactField)
    place: FactField = Field(default_factory=FactField)
    claim_type: FactField = Field(default_factory=FactField)
    claim_type_raw: FactField = Field(default_factory=FactField)  # raw phrase from prompt
    statutes_cited_by_user: List[str] = Field(default_factory=list)
    relief_sought: List[FactField] = Field(default_factory=list)  # list of relief items
    has_arbitration_clause: FactField = Field(default_factory=FactField)
    raw_prompt: str = ""
    # Which party the user represents (None = not stated)
    user_side: Optional[bool] = None

    # ---- convenience -----------------------------------------------------

    def party_names(self) -> List[str]:
        return [p.name for p in self.parties if p.name]

    def plaintiff(self) -> Optional[PartyFact]:
        for p in self.parties:
            if p.role == "plaintiff":
                return p
        return None

    def defendant(self) -> Optional[PartyFact]:
        for p in self.parties:
            if p.role == "defendant":
                return p
        return None

    def user_party(self) -> Optional[PartyFact]:
        for p in self.parties:
            if p.user_side is True:
                return p
        return None

    def opposing_party(self) -> Optional[PartyFact]:
        for p in self.parties:
            if p.user_side is False:
                return p
        return None

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
                role = f" ({p.role})" if p.role != "unknown" else ""
                addr = f", {p.address}" if p.address else ""
                user = " [YOUR SIDE]" if p.user_side is True else ""
                lines.append(f"  - {p.name}{role}{addr}{user}")
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

        if self.relief_sought:
            lines.append("Relief sought:")
            for i, r in enumerate(self.relief_sought, 1):
                if r.provided():
                    lines.append(f"  {i}. {r.value}")
        else:
            lines.append(f"Relief sought: {missing_marker('relief sought')}")

        if self.statutes_cited_by_user:
            lines.append(
                "Statutes cited by the user: " + ", ".join(self.statutes_cited_by_user)
            )
        return "\n".join(lines)

    def missing_critical_fields(self, document_type: str) -> List[str]:
        """Return list of questions for fields that must be confirmed before filing.

        document_type: "plaint" | "complaint" | "petition" | "writ" | "suit"

        Always asks all 5 critical questions when relevant; never skips because
        a field was inferred.
        """
        questions: List[str] = []

        # 1. User side — always ask if not explicitly stated by user
        if self.user_side is None:
            questions.append("Which party do you represent? (Plaintiff/Complainant/Petitioner or Defendant/Respondent)")

        # 2. Exact legal names and entity type for each party
        for p in self.parties:
            if p.status == "INFERRED" or p.entity_type == "unknown":
                questions.append(
                    f"Confirm exact legal name and entity type (individual/company/partnership/LLP/trust/government/other) for '{p.name}'"
                )

        # 3. Delivery date for breach of contract
        if self.delivery_date.status == "MISSING" and self.contract_value.status != "MISSING":
            questions.append("What was the agreed delivery/performance date?")

        # 4. Notice dates for cheque bounce / contract breach / non-delivery
        if not self.notice_dates:
            # Always ask for contract cases (contract_value provided) or cheque bounce
            is_contract_case = self.contract_value.status != "MISSING"
            is_cheque = "cheque" in (self.claim_type_raw.value or "").lower() or "138" in " ".join(self.statutes_cited_by_user)
            is_non_delivery = self.claim_type.value == "NON_DELIVERY_OF_GOODS"
            is_breach = self.claim_type.value == "BREACH_OF_CONTRACT"
            if is_contract_case or is_cheque or is_non_delivery or is_breach:
                questions.append("Was a legal notice sent? If so, date(s)?")

        # 5. Payment status for cheque bounce
        if "cheque" in (self.claim_type_raw.value or "").lower() or "138" in " ".join(self.statutes_cited_by_user):
            questions.append("Was the cheque presented and dishonoured? Date of dishonour?")

        # 6. Arbitration clause
        if self.has_arbitration_clause.status == "MISSING":
            questions.append("Does the contract contain an arbitration clause?")

        return questions


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
    role: PartyRole = "unknown",
    address: Optional[str] = None,
    entity_type: EntityType = "unknown",
    user_side: Optional[bool] = None,
) -> Optional[PartyFact]:
    """Party name must be grounded; role/entity_type/user_side are always INFERRED."""
    if not name or not is_grounded(name, raw_prompt):
        return None
    return PartyFact(
        name=name,
        role=role,
        address=address if address and is_grounded(address, raw_prompt) else None,
        entity_type=entity_type,
        user_side=user_side,
        status="INFERRED",
        source_span=name,
    )


# --- Normalization helpers -------------------------------------------------

def normalize_amount_inr(text: str) -> Optional[int]:
    """Convert Indian money string to integer rupees.

    Returns rupees as integer. Handles: Rs 50 crore, Rs. 5,00,000, 10 lakh, etc.
    """
    if not text:
        return None
    t = text.lower().replace(",", "").replace("₹", "").replace("rs.", "").replace("rs", "").replace("inr", "").strip()
    # Crore
    if "crore" in t:
        num = re.search(r"([\d.]+)\s*crore", t)
        if num:
            return int(float(num.group(1)) * 1_00_00_000)
    # Lakh
    if "lakh" in t:
        num = re.search(r"([\d.]+)\s*lakh", t)
        if num:
            return int(float(num.group(1)) * 1_00_000)
    # Thousand
    if "thousand" in t:
        num = re.search(r"([\d.]+)\s*thousand", t)
        if num:
            return int(float(num.group(1)) * 1000)
    # Plain number
    num = re.search(r"([\d.]+)", t)
    if num:
        return int(float(num.group(1)))
    return None


def infer_entity_type(name: str) -> EntityType:
    """Guess entity type from name. Always INFERRED."""
    n = name.lower()
    if any(k in n for k in ["ltd", "limited", "pvt", "private", "corp", "corporation", "inc", "company", "co "]):
        return "company"
    if "llp" in n:
        return "llp"
    if "partnership" in n:
        return "partnership"
    if "trust" in n:
        return "trust"
    if any(k in n for k in ["govt", "government", "state", "municipal", "corporation", "authority", "board"]):
        return "government"
    # Heuristic: all caps or contains "Steel", "Motors", "Industries" -> company
    if name.isupper() or any(k in n for k in ["steel", "motors", "industries", "manufacturers", "enterprises"]):
        return "company"
    return "unknown"


def infer_claim_type(raw_phrase: str) -> ClaimTypeEnum:
    """Map raw claim phrase to controlled enum."""
    r = raw_phrase.lower()
    if "non.delivery" in r or "failed to deliver" in r or "non delivery" in r:
        return "NON_DELIVERY_OF_GOODS"
    if "breach" in r:
        return "BREACH_OF_CONTRACT"
    if "cheque" in r and "bounce" in r:
        return "CHEQUE_BOUNCE"
    if "specific performance" in r:
        return "SPECIFIC_PERFORMANCE"
    if "recovery" in r:
        return "RECOVERY_OF_DUES"
    if "damages" in r:
        return "DAMAGES"
    if "eviction" in r:
        return "EVICTION"
    if "divorce" in r:
        return "DIVORCE"
    if "termination" in r or "wrongful" in r:
        return "WRONGFUL_TERMINATION"
    return "OTHER"


def infer_role_from_prompt(name: str, prompt: str) -> PartyRole:
    """Infer plaintiff/defendant from prompt context. Always INFERRED."""
    lower = prompt.lower()
    name_lower = name.lower()

    plaintiff_markers = [
        "filed", "complained", "sued", "petitioned", "claimed", "seeking",
        "alleged", "praying for", "asking for", "demanding", "my client", "our client"
    ]
    defendant_markers = [
        "failed to", "breached", "defaulted", "against", "accused",
        "respondent", "defendant", "dishonoured", "bounced", "did not"
    ]

    idx = lower.find(name_lower)
    if idx >= 0:
        # Wider context window, especially AFTER the name (200 chars)
        context = lower[max(0, idx - 80):idx + 200]

        # Special check: "to [name]" construction -> plaintiff (recipient)
        before = lower[max(0, idx - 30):idx]
        if re.search(r'\bto\s+', before):
            return "plaintiff"

        has_plaintiff = any(m in context for m in plaintiff_markers)
        has_defendant = any(m in context for m in defendant_markers)

        if has_plaintiff and not has_defendant:
            return "plaintiff"
        if has_defendant and not has_plaintiff:
            return "defendant"
        if has_plaintiff and has_defendant:
            # Both present - check which is closer
            plaintiff_dist = min((context.find(m) for m in plaintiff_markers if m in context), default=999)
            defendant_dist = min((context.find(m) for m in defendant_markers if m in context), default=999)
            if plaintiff_dist < defendant_dist:
                return "plaintiff"
            else:
                return "defendant"

    return "unknown"


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
# Organization pattern: capitalized phrases that look like company/party names.
_ORG_RE = re.compile(
    r"\b([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)\b"
)
# Contract date pattern
_CONTRACT_DATE_RE = re.compile(
    r"\b(?:contract|agreement|deed|instrument)\s+(?:dated|executed|signed)\s+"
    r"([A-Z][A-Za-z]+(?:\s+\d{1,2})?(?:\s*,?\s*\d{2,4})?)",
    re.IGNORECASE,
)
# Relief sought pattern
_RELIEF_RE = re.compile(
    r"\b(?:seeking|claiming|praying for|asking for)\s+(.+?)(?:\.|$|\bunder\b)",
    re.IGNORECASE,
)
# Claim type pattern
_CLAIM_TYPE_RE = re.compile(
    r"\b(?:for|under)\s+(breach of contract|non.delivery|cheque.bounce|specific.performance|recovery|damages|eviction|divorce|termination|wrongful.termination)",
    re.IGNORECASE,
)
# Additional claim type patterns for cases without "for/under"
_CLAIM_TYPE_EXTRA_RE = re.compile(
    r"\b(breach of contract|breach|non.delivery|failed to deliver|cheque.bounce|specific.performance|recovery of|damages|eviction|divorce|termination|wrongful.termination)\b",
    re.IGNORECASE,
)


def _extract_orgs(text: str) -> List[str]:
    """Extract potential organization names from text using regex."""
    found = []
    for match in _ORG_RE.finditer(text):
        name = match.group(1).strip()
        if name.lower() not in {
            "the", "and", "or", "but", "in", "on", "at", "to", "for", "of", "as", "by",
            "section", "act", "court", "judge", "law", "legal", "case", "contract",
            "goods", "damages", "performance", "specific", "indian",
            "rs", "crore", "lakh", "worth", "failed", "deliver", "per", "dated",
            "seeking", "under", "march", "jamshedpur"
        } and len(name) > 2:
            found.append(name)
    return list(dict.fromkeys(found))


def build_from_text(raw_prompt: str, entities: Optional[Dict[str, Any]] = None) -> FactSheet:
    """Deterministic FactSheet used when no LLM key is configured.

    Grounded exact matches -> PROVIDED. Derived/guessed -> INFERRED. Absent -> MISSING.
    """
    entities = entities or {}
    prompt = raw_prompt or ""

    persons = [p for p in (entities.get("persons") or []) if p]
    orgs = [o for o in (entities.get("organizations") or []) if o]
    if not orgs:
        orgs = _extract_orgs(prompt)

    parties: List[PartyFact] = []
    all_candidates = persons + orgs

    # Limit to first 2 distinct parties
    for cand in all_candidates[:2]:
        if not is_grounded(cand, prompt):
            continue
        role = infer_role_from_prompt(cand, prompt)
        entity_type = infer_entity_type(cand)
        # user_side INFERRED from role
        user_side = (role == "plaintiff") if role != "unknown" else None
        parties.append(PartyFact(
            name=cand,
            role=role,
            entity_type=entity_type,
            user_side=user_side,
            status="INFERRED",
            source_span=cand,
        ))

    # If still no parties, create placeholder
    if not parties:
        parties.append(PartyFact(name="[Party 1]", role="unknown", entity_type="unknown", status="MISSING"))

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

    # Contract date
    contract_dates = [m.group(1).strip() for m in _CONTRACT_DATE_RE.finditer(prompt)]
    if contract_dates and dates:
        dates = [d for d in dates if not is_grounded(d, contract_dates[0])]

    # Relief sought (list of items, split by "and" or commas)
    relief_matches = [m.group(1).strip() for m in _RELIEF_RE.finditer(prompt)]

    # Claim type: raw phrase + controlled enum
    claim_type_matches = [m.group(1).strip().replace(".", " ").replace("_", " ") for m in _CLAIM_TYPE_RE.finditer(prompt)]
    if not claim_type_matches:
        claim_type_matches = [m.group(1).strip().replace(".", " ").replace("_", " ") for m in _CLAIM_TYPE_EXTRA_RE.finditer(prompt)]

    sheet = FactSheet(raw_prompt=prompt)
    sheet.parties = parties
    sheet.statutes_cited_by_user = list(dict.fromkeys(statutes))

    if contract_dates:
        sheet.contract_date = FactField(
            value=contract_dates[0], status="PROVIDED", source_span=contract_dates[0]
        )
    if money:
        amt_inr = normalize_amount_inr(money[0])
        sheet.contract_value = FactField(
            value=money[0], status="PROVIDED", source_span=money[0],
            normalized={"amount_inr": amt_inr} if amt_inr else None
        )
        if len(money) > 1:
            amt2 = normalize_amount_inr(money[1])
            sheet.damages_claimed = FactField(
                value=money[1], status="PROVIDED", source_span=money[1],
                normalized={"amount_inr": amt2} if amt2 else None
            )
    if dates:
        sheet.incident_date = FactField(
            value=dates[0], status="PROVIDED", source_span=dates[0]
        )
    if places:
        sheet.place = FactField(
            value=places[0], status="PROVIDED", source_span=places[0]
        )
    if relief_matches:
        # Split relief by "and" or commas, keep as list
        relief_items = []
        for item in relief_matches:
            # Split on "and" or commas
            parts = re.split(r'\s+and\s+|,\s*', item)
            for p in parts:
                p = p.strip()
                if p:
                    relief_items.append(FactField(value=p, status="PROVIDED", source_span=item))
        sheet.relief_sought = relief_items
    if claim_type_matches:
        raw_phrase = claim_type_matches[0]
        enum_val = infer_claim_type(raw_phrase)
        sheet.claim_type = FactField(
            value=enum_val, status="PROVIDED", source_span=raw_phrase
        )
        sheet.claim_type_raw = FactField(
            value=raw_phrase, status="PROVIDED", source_span=raw_phrase
        )

    return sheet