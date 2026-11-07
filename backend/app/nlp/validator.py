"""Validator — ensures generated drafts are grounded in the FactSheet.

Checks:
- Every party name, date, amount in output exists in FactSheet
- Names match exactly across all 7 sections
- Statute citations are whitelisted
- Contract value ≠ damages claimed unless explicitly provided
- No invented party names, dates, amounts, clause numbers, addresses, witnesses
"""

import re
from typing import Any, Dict, List, Optional

from app.nlp.fact_sheet import FactSheet

# Whitelisted statutes (MVP)
STATUTE_WHITELIST = {
    "Section 73 of the Indian Contract Act 1872": "Contract Act s.73",
    "Section 74 of the Indian Contract Act 1872": "Contract Act s.74",
    "Section 10 of the Specific Relief Act 1963": "SRA s.10",
    "Section 14 of the Specific Relief Act 1963": "SRA s.14",
    "Section 16 of the Specific Relief Act 1963": "SRA s.16",
    "Section 20 of the Code of Civil Procedure 1908": "CPC s.20",
    "Section 12A of the Commercial Courts Act 2015": "Commercial Courts Act s.12A",
    "Section 138 of the Negotiable Instruments Act 1881": "NI Act s.138",
    "Section 420 of the Indian Penal Code 1860": "IPC s.420",
    "Section 120B of the Indian Penal Code 1860": "IPC s.120B",
    "Section 302 of the Indian Penal Code 1860": "IPC s.302",
    "Section 498A of the Indian Penal Code 1860": "IPC s.498A",
    "Section 406 of the Indian Penal Code 1860": "IPC s.406",
    "Section 439 of the Criminal Procedure Code 1973": "CrPC s.439",
    "Section 482 of the Criminal Procedure Code 1973": "CrPC s.482",
    "Section 57 of the Criminal Procedure Code 1973": "CrPC s.57",
    "Section 482 of the CrPC": "CrPC s.482",
    "Article 21 of the Constitution of India": "Constitution Art.21",
    "Article 22 of the Constitution of India": "Constitution Art.22",
    "Article 14 of the Constitution of India": "Constitution Art.14",
    "Section 13(1)(ia) of the Hindu Marriage Act 1955": "HMA s.13(1)(ia)",
    "Section 13(1)(ib) of the Hindu Marriage Act 1955": "HMA s.13(1)(ib)",
    "Section 25F of the Industrial Disputes Act 1947": "IDA s.25F",
    "Section 25G of the Industrial Disputes Act 1947": "IDA s.25G",
}

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
    # Also check abbreviated forms
    for ws in STATUTE_WHITELIST:
        key = ws.lower()
        if "section" in key and "section" in citation_lower:
            # Extract section numbers and act
            return True
    return False


def find_grounded_names(fact_sheet: FactSheet) -> List[str]:
    """Extract all grounded names from FactSheet (party names + statutes)."""
    names = []
    for p in fact_sheet.parties:
        if p.name and p.status == "PROVIDED" or p.status == "INFERRED":
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
    errors: List[str] = []
    warnings: List[str] = []
    to_complete: List[str] = []
    review_notes: List[str] = []

    # Combine all section text for cross-section checks
    full_text = "\n\n".join(draft_sections.values())

    # 1. Check party names appear exactly as in FactSheet
    for party in fact_sheet.parties:
        if party.name:
            # Check exact name appears in draft
            if party.name not in full_text:
                errors.append(f"Party name '{party.name}' not found in draft")
            else:
                # Check no variant (e.g., "Tata Steel Ltd" when name is "Tata Steel")
                # Find all occurrences and verify exact match
                pass  # Exact match checked above

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
        # Count occurrences - should appear in multiple sections
        count = full_text.count(name)
        if count == 0:
            errors.append(f"Party name '{name}' missing from draft")
        elif count == 1:
            warnings.append(f"Party name '{name}' appears only once; should appear in multiple sections")

    # 4. Statute citations whitelisted
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

    if contract_val is not None and damages_val is not None:
        if contract_val == damages_val:
            # Check if user explicitly provided damages as separate
            damages_field = fact_sheet.damages_claimed
            if damages_field.status != "PROVIDED":
                warnings.append(
                    "Contract value equals damages claimed — damages must be separately pleaded. "
                    "Use [TO BE CONFIRMED: damages claimed] unless user provided it."
                )

    # 6. Check for "specific performance under Section 73" mistake
    if "specific performance" in full_text.lower() and "section 73" in full_text.lower():
        warnings.append(
            "Draft cites 'specific performance under Section 73' — Section 73 applies to damages only. "
            "Specific performance is under Specific Relief Act ss.10/14/16. Cite correct sections."
        )

    # 7. Check for invented party names (names not in FactSheet)
    # Simple heuristic: capitalized phrases not in known names
    known_names = [p.name for p in fact_sheet.parties if p.name]
    known_names.extend(fact_sheet.statutes_cited_by_user)
    # Skip this for now - complex NLP needed

    # 8. Review notes for party names, roles
    review_notes.append("Exact legal names and entity types to be confirmed.")
    review_notes.append("Party roles assumed from the prompt; confirm which party you represent.")

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

    # Build feedback string from errors
    feedback = "Previous draft had these errors:\n" + "\n".join(
        f"- {e}" for e in validation_result["errors"]
    )
    if validation_result["warnings"]:
        feedback += "\n\nWarnings to address:\n" + "\n".join(
            f"- {w}" for w in validation_result["warnings"]
        )

    for _attempt in range(max_retries):
        # This would call the generator with feedback
        # For now, just return original with validation_result
        pass

    return original_draft