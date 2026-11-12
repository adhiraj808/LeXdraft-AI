"""
Legal vocabulary allowlist for static template text.

This file contains known case-specific proper nouns that MUST NOT appear in templates.
The CI lint flags any occurrence of these specific names/places/organizations.

Also checks for digits outside allowed legal patterns (section numbers, years, exhibit numbers).
"""

import re

# Known case-specific proper nouns that must NEVER appear in templates
# These are specific to individual cases and should come from FactSheet
# Use word-boundary patterns for exact matching
CASE_SPECIFIC_PROPER_NOUNS = [
    # Specific party names from test cases
    r"\btata steel\b",
    r"\bindira car manufacturers\b",
    r"\bmahindra car manufacturers\b",
    r"\bramesh kumar\b",
    r"\bsuresh sharma\b",
    r"\bpriya\b",
    r"\brahul\b",
    r"\bamit\b",
    r"\bvikram\b",
    r"\bsunita\b",
    r"\brajesh\b",
    r"\bkavita\b",
    r"\bsharma\b",
    r"\bkumar\b",
    r"\babc ltd\b",
    r"\bxyz pvt ltd\b",
    r"\bpqr traders\b",
    r"\babc textiles pvt ltd\b",
    r"\bxyz garments ltd\b",
    r"\brajesh traders\b",
    r"\bsuresh enterprises\b",
    r"\breliance industries\b",
    r"\badani power\b",
    r"\binfosys\b",
    r"\bwipro\b",
    r"\bstate bank of india\b",
    r"\bhd hdfc bank\b",
    r"\bvikram singh\b",
    r"\bsamsung\b",
    r"\babc developers\b",
    r"\btechcorp\b",
    r"\bamit patel\b",
    r"\bneha shah\b",
    r"\bamit\b",
    r"\bsumit\b",
    r"\bvikas\b",
    
    # Specific locations from test cases
    r"\bconnaught place\b",
    r"\bjamshedpur\b",
    r"\bmumbai\b",
    # r"\bdelhi\b",  # Used as default location in template
    r"\bbangalore\b",
    r"\bbengaluru\b",
    r"\bchennai\b",
    r"\bkolkata\b",
    r"\bpune\b",
    r"\bhyderabad\b",
    r"\bahmedabad\b",
    r"\bsurat\b",
    r"\bjaipur\b",
    r"\blucknow\b",
    r"\bgurgaon\b",
    r"\bnoida\b",
    r"\bfaridabad\b",
    r"\bghaziabad\b",
    r"\bsonipat\b",
    r"\bbahadurgarh\b",
    r"\bballabhgarh\b",
    r"\bpatna\b",
    r"\bkanpur\b",
    r"\bagra\b",
    r"\bmeerut\b",
    r"\bkochi\b",
    r"\bnagpur\b",
]

# Digits that are allowed in templates (legal patterns)
ALLOWED_DIGIT_PATTERNS = [
    r'^\s*\d+[\.\)]\s',  # "1. " or "1) " at start of line (numbered paragraphs)
    r'EX\.\s*[A-Z]+-\d+/\d+',  # "EX. CW-1/1"
    r'[A-Z]+-\d+/\d+',  # "CW-1/1"
    r'§\s*\d+',  # "§ 73"
    r'Order\s+\d+',  # "Order 1"
    r'Rule\s+\d+',  # "Rule 1"
    r'\d{4}',  # years like 2024
    r'\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}',  # dates like 15/03/2026
    r'\d+\s*(?:crore|lakh|thousand|million|billion)',  # amounts like "50 crore"
    r'Rs\.?\s*\d',  # "Rs. 50"
    r'₹\s*\d',  # "₹ 50"
    r'Article\s+\d+',  # "Article 12"
    r'Section\s+\d+',  # "Section 12"
]


def check_text(text: str) -> list:
    """
    Check text for case-specific proper nouns and disallowed digits.
    Returns list of (line_num, word, issue_type) tuples.
    """
    issues = []
    lines = text.splitlines()
    for i, line in enumerate(lines, 1):
        line_lower = line.lower()
        
        # Check for case-specific proper nouns using word-boundary patterns
        for pattern in CASE_SPECIFIC_PROPER_NOUNS:
            if re.search(pattern, line_lower):
                match = re.search(pattern, line_lower)
                issues.append((i, match.group(0), "case_specific_proper_noun"))
        
        # Check for digits outside allowed patterns
        if re.search(r'\d', line):
            is_allowed = False
            for pattern in ALLOWED_DIGIT_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    is_allowed = True
                    break
            if not is_allowed:
                issues.append((i, line.strip()[:50], "disallowed_digit"))
    
    return issues


def is_allowed_word(word: str) -> bool:
    """Check if a word is not a case-specific proper noun."""
    word_lower = word.lower().strip(".,;:!?()[]{}\"'")
    for pattern in CASE_SPECIFIC_PROPER_NOUNS:
        if re.fullmatch(pattern, word_lower):
            return False
    return True