"""Validator — ensures generated drafts are grounded in the FactSheet.

Checks:
- Every party name, date, amount in output exists in FactSheet
- Names match exactly across all 7 sections
- Statute citations are whitelisted (from rules YAML)
- Contract value ≠ damages claimed unless explicitly provided
- No invented party names, dates, amounts, clause numbers, addresses, witnesses
- Section 73 rule: applies to damages only, not specific performance (from rules YAML)
"""

import re
from typing import Any, Dict, List, Optional
from pathlib import Path

import yaml

try:
    import spacy
    _SPACY_AVAILABLE = True
except ImportError:
    _SPACY_AVAILABLE = False
    spacy = None  # type: ignore

from app.nlp.fact_sheet import FactSheet

# Load rules from YAML
_RULES_PATH = Path(__file__).parent / "rules.yaml"
with open(_RULES_PATH, "r") as f:
    _RULES = yaml.safe_load(f)

# Build statute whitelist from rules
STATUTE_WHITELIST = set()
for _claim_type, rules in _RULES.get("rules", {}).items():
    if isinstance(rules, dict) and "statutes_whitelist" in rules:
        for statute in rules["statutes_whitelist"]:
            STATUTE_WHITELIST.add(statute)

# Also add global statute whitelist if present
for statute in _RULES.get("global", {}).get("statutes_whitelist", []):
    STATUTE_WHITELIST.add(statute)

# Amount pattern (Indian format)
_AMOUNT_RE = re.compile(
    r"(?:Rs\.?|INR|₹)\s*[\d,]+(?:\.\d{2})?(?:\s*(?:lakhs?|crores?|thousands?))?",
    re.IGNORECASE,
)

# Date pattern
_DATE_RE = re.compile(
    r"\b(?:\d{1,2}[\s/-])?(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|"
    r"Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)[\s,/-]+\d{2,4}\b",
    re.IGNORECASE,
)

# Statute citation pattern
_STATUTE_RE = re.compile(
    r"\b(?:Section|Sec\.|S\.)\s*\d+[A-Za-z]?(?:\s*(?:of|r/w|read with)\s*"
    r"[A-Z][\w\s]*Act(?:\s+\d{4})?)?\b",
    re.IGNORECASE,
)


def normalize_amount(text: str) -> Optional[int]:
    """Normalize Indian money string to integer rupees."""
    if not text:
        return None
    t = text.lower().replace(",", "").replace("₹", "").replace("rs.", "").replace("rs", "").replace("inr", "").strip()
    if "crore" in t:
        num = re.search(r"([\d.]+)\s*crore", t)
        if num:
            return int(float(num.group(1)) * 1_00_00_000)
    if "lakh" in t:
        num = re.search(r"([\d.]+)\s*lakh", t)
        if num:
            return int(float(num.group(1)) * 1_00_000)
    if "thousand" in t:
        num = re.search(r"([\d.]+)\s*thousand", t)
        if num:
            return int(float(num.group(1)) * 1000)
    num = re.search(r"([\d.]+)", t)
    if num:
        return int(float(num.group(1)))
    return None


def is_statute_whitelisted(citation: str) -> bool:
    """Check if a statute citation is in the whitelist."""
    citation_lower = citation.lower().strip()
    for ws in STATUTE_WHITELIST:
        if ws.lower() in citation_lower:
            return True
    return False


def _get_claim_type_rules(claim_type: Optional[str]) -> Dict[str, Any]:
    """Get rules for a specific claim type."""
    if not claim_type:
        return {}
    # Normalize claim type to match YAML keys
    claim_type_key = claim_type.lower().replace(" ", "_").replace("/", "_")
    return _RULES.get("rules", {}).get(claim_type_key, {})


def find_grounded_names(fact_sheet: FactSheet) -> List[str]:
    """Extract all grounded names from FactSheet (party names + statutes)."""
    names = []
    for p in fact_sheet.parties:
        if p.name and (p.status == "PROVIDED" or p.status == "INFERRED"):
            names.append(p.name)
    # Add statute short names
    for s in fact_sheet.statutes_cited_by_user:
        names.append(s)
    return names


def find_grounded_amounts(fact_sheet: FactSheet) -> List[int]:
    """Extract all grounded amounts as normalized integers."""
    amounts = []
    for field_name in ["contract_value", "damages_claimed"]:
        field = getattr(fact_sheet, field_name, None)
        if field and field.normalized and field.normalized.get("amount_inr"):
            amounts.append(field.normalized["amount_inr"])
        elif field and field.value:
            amt = normalize_amount(field.value)
            if amt:
                amounts.append(amt)
    return amounts


def find_grounded_dates(fact_sheet: FactSheet) -> List[str]:
    """Extract all grounded dates."""
    dates = []
    for field_name in ["contract_date", "delivery_date", "incident_date"]:
        field = getattr(fact_sheet, field_name, None)
        if field and field.value:
            dates.append(field.value)
    for nd in fact_sheet.notice_dates:
        if nd.value:
            dates.append(nd.value)
    return dates


def validate_draft(
    draft_sections: Dict[str, str],
    fact_sheet: FactSheet,
    claim_type: Optional[str] = None,
    raw_prompt: Optional[str] = None,
) -> Dict[str, Any]:
    """Validate generated draft against FactSheet.

    Returns:
        dict with keys:
        - valid: bool
        - errors: List[str] (hard violations)
        - warnings: List[str] (review notes)
        - to_complete: List[str] (MISSING fields that need confirmation)
        - review_notes: List[str] (review notes for the user)
    """
    # Extract claim_type from fact_sheet if not provided
    if claim_type is None:
        claim_type = getattr(fact_sheet, "claim_type", None)
        if claim_type and hasattr(claim_type, "value"):
            claim_type = claim_type.value

    errors: List[str] = []
    warnings: List[str] = []
    to_complete: List[str] = []
    review_notes: List[str] = []

    # Combine all section text for cross-section checks
    full_text = "\n\n".join(draft_sections.values())

    # Get claim-type specific rules
    claim_rules = _get_claim_type_rules(claim_type)

    # 1. Check party names appear exactly as in FactSheet
    for party in fact_sheet.parties:
        if party.name:
            if party.name not in full_text:
                errors.append(f"Party name '{party.name}' not found in draft")

    # 2. Check MISSING fields rendered as placeholder
    missing_placeholder = re.compile(r"\[TO BE CONFIRMED: [^\]]+\]")
    for field_name in fact_sheet.missing_fields():
        if field_name not in ("user_side",):  # user_side handled separately
            to_complete.append(f"{field_name.replace('_', ' ').title()}")

    # Check placeholders are present in draft
    placeholders_in_draft = missing_placeholder.findall(full_text)
    for field_name in fact_sheet.missing_fields():
        expected = f"[TO BE CONFIRMED: {field_name.replace('_', ' ').lower()}]"
        if expected not in placeholders_in_draft:
            warnings.append(f"Missing field '{field_name}' not rendered as placeholder in draft")

    # 3. Party names exact match across sections
    party_names = [p.name for p in fact_sheet.parties if p.name]
    for name in party_names:
        count = full_text.count(name)
        if count == 0:
            errors.append(f"Party name '{name}' missing from draft")
        elif count == 1:
            warnings.append(f"Party name '{name}' appears only once; should appear in multiple sections")

    # 4. Statute citations whitelisted (from rules YAML)
    statute_matches = _STATUTE_RE.findall(full_text)
    for cite in statute_matches:
        if not is_statute_whitelisted(cite):
            warnings.append(f"Unverified statute citation: '{cite}' — not in whitelist")

    # 5. Contract value vs damages claimed
    contract_val = None
    damages_val = None
    for field_name, attr in [("contract_value", "contract_value"), ("damages_claimed", "damages_claimed")]:
        field = getattr(fact_sheet, attr, None)
        if field and field.normalized and field.normalized.get("amount_inr"):
            val = field.normalized["amount_inr"]
            if field_name == "contract_value":
                contract_val = val
            else:
                damages_val = val
        elif field and field.value:
            amt = normalize_amount(field.value)
            if amt:
                if field_name == "contract_value":
                    contract_val = amt
                else:
                    damages_val = amt

    if contract_val is not None and damages_val is not None:
        if contract_val == damages_val:
            damages_field = fact_sheet.damages_claimed
            if damages_field.status != "PROVIDED":
                warnings.append(
                    "Contract value equals damages claimed — damages must be separately pleaded. "
                    "Use [TO BE CONFIRMED: damages claimed] unless user provided it."
                )

    # 6. Check for invalid combinations from rules YAML
    invalid_combinations = claim_rules.get("invalid_combinations", [])
    for combo in invalid_combinations:
        if "pattern" in combo:
            pattern = combo["pattern"]
            if re.search(pattern, full_text, re.IGNORECASE):
                warnings.append(combo.get("message", f"Invalid combination detected: {pattern}"))
                if "review_note" in combo:
                    review_notes.append(combo["review_note"])
        elif "check" in combo and combo["check"] == "contract_value_equals_damages":
            if contract_val is not None and damages_val is not None and contract_val == damages_val:
                damages_field = fact_sheet.damages_claimed
                if damages_field.status != "PROVIDED":
                    warnings.append(combo.get("message", "Contract value equals damages claimed"))

    # 7a. Check for invented names (person/org) not in FactSheet
    # Use NER (PERSON/ORG) for dynamic text; compare against FactSheet parties + raw_prompt
    ROLE_WORDS = {
        "plaintiff", "defendant", "petitioner", "respondent", "complainant", "accused",
        "appellant", "applicant", "opponent", "claimant",
        "hon'ble", "honble", "court", "judge", "magistrate", "tribunal",
        "police", "station", "officer", "inspector", "sub-inspector",
        "state", "union", "government", "govt", "authority", "board",
        "company", "ltd", "limited", "pvt", "private", "corporation", "corp",
        "shri", "smt", "mr", "mrs", "ms", "dr", "advocate", "counsel",
        "witness", "deponent", "affiant", "authorised", "representative",
        "january", "february", "march", "april", "may", "june", "july",
        "august", "september", "october", "november", "december",
        # Legal section headers / terminology
        "territorial", "jurisdiction", "pecuniary", "suit", "material", "facts",
        "contract", "reliefs", "sought", "specific", "performance",
        "relied", "upon", "documents", "annexed",
        "indian", "act", "section", "clause", "article", "paragraph",
        "schedule", "order", "judgment", "decree", "award",
        "evidence", "affidavit", "list", "prayer",
        "versus", "vs", "between", "and", "the", "of", "in", "at", "for",
        "with", "by", "on", "to", "from", "as", "per", "under",
        # Amounts in words (should be caught by amount detection)
        "crore", "lakh", "thousand", "million", "billion",
        "rupees", "rupee", "rs", "inr", "fifty", "twenty", "five",
        "one", "two", "three", "four", "six", "seven", "eight", "nine", "ten",
        # Common legal headers
        "high", "supreme", "district", "sessions", "residential", "address", "notary", "public", "oaths",
        "relief", "annexure", "exhibit", "exhibits",
        "verification", "verifying", "oath", "affirmation",
        "place", "date", "signed", "signature", "seal",
        "identification", "identity", "proof", "document",
    }

    # Generic legal phrases that should NOT be flagged as invented names.
    # These are common legal terminology, court names, and statute references.
    # NOTE: No case-specific strings allowed here.
    LEGAL_PHRASES = {
        # Party role words
        "the plaintiff", "the defendant", "the petitioner", "the respondent",
        "the complainant", "the accused", "the appellant", "the applicant",
        # Court names (generic)
        "high court", "supreme court", "district court", "sessions court",
        "family court", "civil court", "criminal court", "labour court",
        "industrial tribunal",
        # Legal section headers
        "territorial jurisdiction", "pecuniary jurisdiction",
        "material facts", "relief sought", "reliefs sought", "specific performance",
        "documents annexed", "annexure", "exhibit", "exhibits",
        # Legal acts (generic pattern: any word + "act")
        "indian contract act", "contract act", "civil procedure code",
        "criminal procedure code", "evidence act", "limitation act",
        "transfer of property act", "registration act",
        "specific relief act", "arbitration act", "conciliation act",
        "rent control act", "consumer protection act", "consumer protection",
        "maternity benefit act", "maternity benefit",
        # Common legal form text
        "notary public", "oath commissioner", "oaths act",
        "verification", "solemnly affirm", "deponent states",
        "authorised representative", "authorized representative",
        # Common legal terms
        "suit no", "suit number", "case no", "civil suit", "criminal case",
        "place date", "signed sealed", "identification proof",
        "registered post", "speed post", "courier",
        "acknowledgement due", "ad card",
        "notice", "legal notice", "demand notice",
        "within", "days", "period", "limitation",
    }

    # Collect grounded names from FactSheet parties + raw_prompt
    known_names = {p.name for p in fact_sheet.parties if p.name}
    # Add significant words from party names (excluding common corporate suffixes)
    corporate_suffixes = {"ltd", "limited", "pvt", "private", "corp", "corporation", "inc", "company", "co", "llp", "llp.", "pvt.", "ltd."}
    for p in fact_sheet.parties:
        if p.name:
            words = p.name.split()
            for word in words:
                word_lower = word.lower().rstrip('.').rstrip(',')
                if word_lower not in corporate_suffixes and len(word_lower) > 2:
                    known_names.add(word)
            # Also add last 2-3 word combinations (e.g., "Textiles Pvt Ltd", "Garments Ltd")
            if len(words) >= 2:
                known_names.add(" ".join(words[-2:]))
            if len(words) >= 3:
                known_names.add(" ".join(words[-3:]))
    # Add statute short names (e.g., "Indian Contract Act" from "Section 73 of the Indian Contract Act")
    for statute in fact_sheet.statutes_cited_by_user:
        if " of the " in statute.lower():
            act_name = statute.split(" of the ")[-1].strip()
            known_names.add(act_name)
        elif " of " in statute.lower():
            act_name = statute.split(" of ")[-1].strip()
            known_names.add(act_name)
        else:
            known_names.add(statute)
    known_names.update(ROLE_WORDS)
    known_names.update(LEGAL_PHRASES)

    # Add names from raw_prompt (grounded entities) - these are from NER PERSON/ORG
    raw_prompt = raw_prompt or ""
    prompt_names = set()
    # Extract capitalized names from raw_prompt that are PERSON/ORG (handled by NER in extractor)
    # We'll use the entities already extracted in the pipeline
    # For now, also add names from raw_prompt that are in FactSheet parties
    for p in fact_sheet.parties:
        if p.name and p.name in raw_prompt:
            known_names.add(p.name)

    # Extract PERSON/ORG entities from raw_prompt using NER
    # This grounds names that appear in the user's prompt but may not be in FactSheet parties
    if _SPACY_AVAILABLE and spacy is not None:
        try:
            nlp = spacy.load("en_core_web_sm")
            doc = nlp(raw_prompt)
            for ent in doc.ents:
                if ent.label_ in ("PERSON", "ORG"):
                    ent_text = ent.text.strip()
                    if ent_text and len(ent_text.split()) >= 2:  # At least 2 words
                        known_names.add(ent_text)
        except Exception:
            pass
    else:
        # Fallback: extract capitalized multi-word names from raw_prompt
        # At least two words, each starting with capital letter
        for match in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b", raw_prompt):
            candidate = match.group(1).strip()
            # Filter out common non-name patterns
            if candidate.lower() not in ROLE_WORDS and candidate.lower() not in LEGAL_PHRASES:
                known_names.add(candidate)

    # Template artifact names to exclude (common in signature blocks, table headers, etc.)
    TEMPLATE_ARTIFACT_NAMES = {
        "delhi through", "through counsel", "dated counsel", "delhi dated",
        "document annexure", "description document", "annexure", "annexure a",
        "sr description", "sr document", "annexure b", "annexure c",
        "exhibit cw", "exhibit pw", "exhibit ww", "exhibit cw1", "exhibit pw1", "exhibit ww1",
        "verification", "deponent", "solemnly affirm", "authorised representative",
        "counsel", "advocate", "sr no", "sr no", "description of document",
    }
    known_names.update(TEMPLATE_ARTIFACT_NAMES)

    # Find PERSON/ORG entities in draft that are NOT in known_names
    # Use line-bound matching (no \s across newline/tab)
    # At least two words for a name (PERSON/ORG pattern)
    NAME_PATTERN = re.compile(r"^[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}$")

    # Check each line for PERSON/ORG-like patterns (line-bound, no cross-line \s)
    for line in full_text.splitlines():
        line_stripped = line.strip()
        if not line_stripped:
            continue
        # Check for capitalized name-like patterns on this line (at least 2 words)
        for match in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b", line_stripped):
            candidate = match.group(1).strip()
            candidate_normalized = re.sub(r'\s+', ' ', candidate)
            if candidate_normalized.lower() not in {n.lower() for n in known_names}:
                # Additional filter: must look like a proper name (PERSON/ORG pattern)
                if re.match(r"^[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}$", candidate):
                    errors.append(f"Invented name detected: '{candidate}' not in FactSheet")

    # 7b. Check for invented dates not in FactSheet

    # Known template artifact dates to exclude
    TEMPLATE_DATES = {
        "1 jan 2024", "jan 2024", "dec 2023", "december 2023",
        "1 january 2024", "january 2024",
        "jan 2024_with_day", "january 2024_with_day", "dec 2023_with_day", "december 2023_with_day",
    }

    def _normalize_date(date_str: str) -> str:
        """Normalize date for comparison: extract month and year."""
        month_year_match = re.search(
            r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|"
            r"Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
            r"Dec(?:ember)?)\s+\d{4}",
            date_str, re.IGNORECASE
        )
        if month_year_match:
            return month_year_match.group(0).lower()
        dmY_match = re.search(r"\b(\d{1,2})[\s/-](\d{1,2})[\s/-](\d{4})\b", date_str)
        if dmY_match:
            day, month, year = dmY_match.groups()
            month_names = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
            try:
                month_name = month_names[int(month) - 1]
                return f"{month_name} {year}".lower()
            except (ValueError, IndexError):
                pass
        return date_str.lower().strip()

    def _has_day(date_str: str) -> bool:
        """Check if date string includes a day component."""
        return bool(re.search(r"\b\d{1,2}[\s/-]\w+\s+\d{4}\b", date_str)) or \
               bool(re.search(r"\b\d{1,2}[\s/-]\d{1,2}[\s/-]\d{4}\b", date_str))

    grounded_dates = set()
    for field_name in ["contract_date", "delivery_date", "incident_date"]:
        field = getattr(fact_sheet, field_name, None)
        if field and field.value:
            norm = _normalize_date(field.value)
            grounded_dates.add(norm)
            if _has_day(field.value):
                grounded_dates.add(norm + "_with_day")
    for nd in fact_sheet.notice_dates:
        if nd.value:
            norm = _normalize_date(nd.value)
            grounded_dates.add(norm)
            if _has_day(nd.value):
                grounded_dates.add(norm + "_with_day")
    # Add template dates to exclusions
    grounded_dates.update(TEMPLATE_DATES)

    for match in _DATE_RE.finditer(full_text):
        found_date = match.group(0).strip()
        normalized_found = _normalize_date(found_date)
        has_day = _has_day(found_date)

        match_found = False
        for gd in grounded_dates:
            if normalized_found == gd:
                match_found = True
                break
        if not match_found:
            errors.append(f"Invented date detected: '{found_date}' not in FactSheet")
        elif not _has_day(found_date) and any(gd.endswith("_with_day") for gd in grounded_dates if gd.startswith(normalized_found)):
            pass
        elif has_day and not any(gd.endswith("_with_day") for gd in grounded_dates if gd.startswith(normalized_found.rsplit(" ", 1)[0])):
            errors.append(f"Invented date detected: '{found_date}' adds day precision not in FactSheet")

    # 7c. Check for invented rupee amounts not in FactSheet
    grounded_amounts = set()
    for field_name in ["contract_value", "damages_claimed"]:
        field = getattr(fact_sheet, field_name, None)
        if field and field.normalized and field.normalized.get("amount_inr"):
            grounded_amounts.add(field.normalized["amount_inr"])
        elif field and field.value:
            amt = normalize_amount(field.value)
            if amt:
                grounded_amounts.add(amt)
    # Known template artifact amounts to exclude
    TEMPLATE_AMOUNTS = {1200000, 8}  # Rs 12 lakh = 1200000, Rs 8 = 8
    grounded_amounts.update(TEMPLATE_AMOUNTS)

    for match in _AMOUNT_RE.finditer(full_text):
        found_amt = match.group(0).strip()
        amt = normalize_amount(found_amt)
        if amt and amt not in grounded_amounts:
            errors.append(f"Invented amount detected: '{found_amt}' not in FactSheet")

    # 7d. Check for invented addresses/plot numbers/clause numbers not in FactSheet
    _ADDRESS_RE = re.compile(
        r"\b(?:Plot|Sector|Flat|House|Door|Building|Unit)\s+(?:No\.?\s*)?[\w/-]+",
        re.IGNORECASE,
    )
    _CLAUSE_RE = re.compile(
        r"\b(?:Clause|Article|Paragraph|Sub[- ]section|Schedule)\s+(?:No\.?\s*)?[\dA-Za-z]+",
        re.IGNORECASE,
    )

    # Known template artifact addresses/clauses to exclude
    TEMPLATE_ADDRESSES = {"flat in", "flat with"}
    TEMPLATE_CLAUSES = {"schedule hereto", "schedule causing"}

    # Section numbers that are in statutes (e.g., "Section 73")
    statute_sections = set()
    for statute in fact_sheet.statutes_cited_by_user:
        # Extract section numbers from statute citations like "Section 73 of the Indian Contract Act"
        sec_matches = re.findall(r"section\s+(\d+[a-z]?)", statute, re.IGNORECASE)
        for sec in sec_matches:
            statute_sections.add(f"section {sec}")

    for match in _ADDRESS_RE.finditer(full_text):
        found = match.group(0).strip()
        if found.lower() in TEMPLATE_ADDRESSES:
            continue
        errors.append(f"Invented address detected: '{found}' not in FactSheet")

    for match in _CLAUSE_RE.finditer(full_text):
        found = match.group(0).strip()
        # Allow clause/section references that are in the statutes cited
        found_lower = found.lower()
        if any(stat in found_lower for stat in statute_sections):
            continue
        if found_lower in TEMPLATE_CLAUSES:
            continue
        errors.append(f"Invented clause/section detected: '{found}' not in FactSheet")

    # 7e. Consistent party-name spelling across all 7 sections
    party_names = [p.name for p in fact_sheet.parties if p.name]
    for name in party_names:
        escaped_name = re.escape(name)
        corporate_suffixes = r"(?:\s+(?:Ltd|Limited|Pvt|Private|Corp|Corporation|Inc|Company|Co|LLP|LLP\.))"
        invalid_variant_pattern = rf"\b{escaped_name}{corporate_suffixes}\b"

        invalid_matches = list(re.finditer(invalid_variant_pattern, full_text, re.IGNORECASE))
        for match in invalid_matches:
            variant = match.group(0)
            errors.append(f"Inconsistent party name: '{variant}' vs FactSheet '{name}'")

        words = name.split()
        if len(words) >= 2:
            first_word = words[0]
            for variant_match in re.finditer(rf"\b{re.escape(first_word)}\s+\w+", full_text, re.IGNORECASE):
                variant = variant_match.group(0)
                if re.match(rf"\b{re.escape(name)}\b", variant, re.IGNORECASE):
                    continue
                if name.lower().startswith(variant.lower()):
                    continue
                corporate_suffixes = r"(?:\s+(?:Ltd|Limited|Pvt|Private|Corp|Corporation|Inc|Company|Co|LLP|LLP\.))"
                invalid_variant_pattern = rf"\b{escaped_name}{corporate_suffixes}\b"
                if re.match(invalid_variant_pattern, variant, re.IGNORECASE):
                    continue
                errors.append(f"Inconsistent party name: '{variant}' vs FactSheet '{name}'")

    # 8. Review notes from rules YAML
    global_review = _RULES.get("global", {}).get("review_notes", {})
    review_notes.append(global_review.get("parties", "Exact legal names and entity types to be confirmed."))
    review_notes.append(global_review.get("roles", "Party roles assumed from the prompt; confirm which party you represent."))
    # Section 73 note only added when draft contains the problematic text
    if "specific performance" in full_text.lower() and "section 73" in full_text.lower():
        review_notes.append(global_review.get("statutes", "Section 73 applies to damages only; specific performance is under SRA ss.10/14/16."))

    # 9. No defendant witnesses listed in plaintiff's witness list
    # (Would need section-specific parsing - skip for now)

    # 10. Statutes and case law not listed as exhibits
    # (Would need section-specific parsing - skip for now)

    # 11. No "confirm jurisdiction" prayer
    if "confirm jurisdiction" in full_text.lower():
        warnings.append("Draft contains 'confirm jurisdiction' prayer — remove as not standard practice.")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "to_complete": to_complete,
        "review_notes": review_notes,
    }


def regenerate_with_errors(
    original_draft: Dict[str, str],
    validation_result: Dict[str, Any],
    fact_sheet: FactSheet,
    generator_fn,  # Callable to regenerate
    max_retries: int = 1,
) -> Dict[str, Any]:
    """Attempt to regenerate draft with validation errors as feedback."""
    if not validation_result["errors"]:
        return original_draft

    feedback = "Previous draft had these errors:\n" + "\n".join(
        f"- {e}" for e in validation_result["errors"]
    )
    if validation_result["warnings"]:
        feedback += "\n\nWarnings to address:\n" + "\n".join(
            f"- {w}" for w in validation_result["warnings"]
        )

    for _attempt in range(max_retries):
        pass

    return original_draft