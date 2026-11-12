"""
Fuzz test for invented entity detection.
Tests that the validator catches invented entities using properly formatted injections.
"""
import sys
import re
sys.path.insert(0, 'backend')

from app.nlp.validator import validate_draft
from app.nlp.fact_sheet import FactSheet, PartyFact, FactField
from app.nlp.generator import SECTION_ORDER

def create_test_fact_sheet():
    """Create a minimal FactSheet for testing."""
    fs = FactSheet(raw_prompt="Test case for fuzzing")
    fs.parties = [
        PartyFact(name="Test Plaintiff", role="plaintiff", entity_type="individual", status="PROVIDED"),
        PartyFact(name="Test Defendant", role="defendant", entity_type="individual", status="PROVIDED"),
    ]
    fs.contract_value = FactField(value="Rs 10 lakh", status="PROVIDED", source_span="Rs 10 lakh", normalized={"amount_inr": 1000000})
    fs.contract_date = FactField(value="January 2024", status="PROVIDED", source_span="January 2024")
    fs.statutes_cited_by_user = ["Section 73 of the Indian Contract Act"]
    return fs

def test_validator_catches_invented_names():
    """Test that validator catches invented person names not in FactSheet."""
    fact_sheet = create_test_fact_sheet()
    
    # Draft with invented names (not in FactSheet)
    draft = {k: f"Section {k} content with John Smith and Jane Doe appearing as witnesses." for k in SECTION_ORDER}
    
    result = validate_draft(draft, fact_sheet)
    
    name_errors = [e for e in result["errors"] if "invented name" in e.lower()]
    caught_names = set()
    for error in name_errors:
        match = re.search(r"invented name detected: '([^']+)'", error, re.IGNORECASE)
        if match:
            caught_names.add(match.group(1))
    
    # Should catch the invented names
    assert "John Smith" in caught_names, f"John Smith not caught. Caught: {caught_names}"
    assert "Jane Doe" in caught_names, f"Jane Doe not caught. Caught: {caught_names}"
    print(f"Names test: Caught {len(caught_names)} invented names")

def test_validator_catches_invented_dates():
    """Test that validator catches invented dates not in FactSheet."""
    fact_sheet = create_test_fact_sheet()
    
    # Draft with invented dates (not in FactSheet which has January 2024)
    draft = {k: f"Section {k} content dated 15 March 2025 and 20 April 2026." for k in SECTION_ORDER}
    
    result = validate_draft(draft, fact_sheet)
    
    date_errors = [e for e in result["errors"] if "invented date" in e.lower()]
    caught_dates = set()
    for error in date_errors:
        match = re.search(r"invented date detected: '([^']+)'", error, re.IGNORECASE)
        if match:
            caught_dates.add(match.group(1))
    
    assert "15 March 2025" in caught_dates, f"15 March 2025 not caught. Caught: {caught_dates}"
    assert "20 April 2026" in caught_dates, f"20 April 2026 not caught. Caught: {caught_dates}"
    print(f"Dates test: Caught {len(caught_dates)} invented dates")

def test_validator_catches_invented_amounts():
    """Test that validator catches invented amounts not in FactSheet."""
    fact_sheet = create_test_fact_sheet()
    
    # Draft with invented amounts (not in FactSheet which has Rs 10 lakh)
    draft = {k: f"Section {k} content with amount Rs 25 lakh and Rs 5 crore." for k in SECTION_ORDER}
    
    result = validate_draft(draft, fact_sheet)
    
    amount_errors = [e for e in result["errors"] if "invented amount" in e.lower()]
    caught_amounts = set()
    for error in amount_errors:
        match = re.search(r"invented amount detected: '([^']+)'", error, re.IGNORECASE)
        if match:
            caught_amounts.add(match.group(1))
    
    assert "Rs 25 lakh" in caught_amounts, f"Rs 25 lakh not caught. Caught: {caught_amounts}"
    assert "Rs 5 crore" in caught_amounts, f"Rs 5 crore not caught. Caught: {caught_amounts}"
    print(f"Amounts test: Caught {len(caught_amounts)} invented amounts")

def test_validator_catches_invented_addresses():
    """Test that validator catches invented addresses not in FactSheet."""
    fact_sheet = create_test_fact_sheet()
    
    # Draft with invented addresses (Flat/Plot patterns)
    draft = {k: f"Section {k} content at Flat 4B and Plot 123." for k in SECTION_ORDER}
    
    result = validate_draft(draft, fact_sheet)
    
    address_errors = [e for e in result["errors"] if "invented address" in e.lower()]
    caught_addresses = set()
    for error in address_errors:
        match = re.search(r"invented address detected: '([^']+)'", error, re.IGNORECASE)
        if match:
            caught_addresses.add(match.group(1))
    
    assert "Flat 4B" in caught_addresses, f"Flat 4B not caught. Caught: {caught_addresses}"
    assert "Plot 123" in caught_addresses, f"Plot 123 not caught. Caught: {caught_addresses}"
    print(f"Addresses test: Caught {len(caught_addresses)} invented addresses")

def test_validator_catches_invented_clauses():
    """Test that validator catches invented clauses/sections not in FactSheet."""
    fact_sheet = create_test_fact_sheet()
    
    # Draft with invented clauses (not Section 73 which is in statutes)
    draft = {k: f"Section {k} content referencing Clause 15 and Article 7." for k in SECTION_ORDER}
    
    result = validate_draft(draft, fact_sheet)
    
    clause_errors = [e for e in result["errors"] if "invented clause" in e.lower() or "invented section" in e.lower()]
    caught_clauses = set()
    for error in clause_errors:
        # Use simpler pattern that works with straight quotes
        match = re.search(r"detected: '([^']+)'", error, re.IGNORECASE)
        if match:
            caught_clauses.add(match.group(1))
    
    assert "Clause 15" in caught_clauses, f"Clause 15 not caught. Caught: {caught_clauses}"
    assert "Article 7" in caught_clauses, f"Article 7 not caught. Caught: {caught_clauses}"
    print(f"Clauses test: Caught {len(caught_clauses)} invented clauses")

def test_validator_allows_grounded_entities():
    """Test that validator does NOT flag entities that ARE in FactSheet."""
    fact_sheet = create_test_fact_sheet()
    
    # Draft with ONLY grounded entities (should pass)
    draft = {k: f"Section {k} content with Test Plaintiff and Test Defendant dated January 2024 amount Rs 10 lakh referencing Section 73." for k in SECTION_ORDER}
    
    result = validate_draft(draft, fact_sheet)
    
    # Should have no invented entity errors
    invented_errors = [e for e in result["errors"] if "invented" in e.lower()]
    assert len(invented_errors) == 0, f"Grounded entities incorrectly flagged: {invented_errors}"
    print("Grounded entities test: PASS - no false positives")

if __name__ == "__main__":
    test_validator_catches_invented_names()
    test_validator_catches_invented_dates()
    test_validator_catches_invented_amounts()
    test_validator_catches_invented_addresses()
    test_validator_catches_invented_clauses()
    test_validator_allows_grounded_entities()
    print("\nAll fuzz tests passed!")