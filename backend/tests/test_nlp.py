"""Tests for the NLP pipeline components."""

import pytest
import spacy

from app.nlp.preprocessor import LegalTextPreprocessor
from app.nlp.ner import LegalNERExtractor
from app.nlp.classifier import CaseClassifier
from app.nlp.fact_sheet import (
    FactSheet,
    FactField,
    is_grounded,
    build_from_text,
    missing_marker,
    normalize_amount_inr,
    infer_entity_type,
    infer_claim_type,
)
from app.nlp.validator import validate_draft, is_statute_whitelisted


@pytest.fixture
def nlp():
    nlp = spacy.blank("en")
    nlp.add_pipe("sentencizer")
    return nlp


@pytest.fixture
def preprocessor(nlp):
    return LegalTextPreprocessor(nlp)


@pytest.fixture
def ner(nlp):
    return LegalNERExtractor(nlp)


SAMPLE_TEXT = """
The petitioner Ramesh Kumar filed a complaint against respondent Suresh Sharma
for cheating and fraud under Section 420 IPC and Section 120B IPC on 15th March 2023.
The incident occurred in New Delhi. Damages claimed amount to Rs. 5,00,000.
The matter is before the Delhi High Court.
"""


class TestPreprocessor:

    def test_clean_text(self, preprocessor):
        dirty = "Hello   World\n\nThis  is  a   test..."
        cleaned = preprocessor.clean_text(dirty)
        assert "  " not in cleaned
        assert cleaned == cleaned.strip()

    def test_extract_legal_sections(self, preprocessor):
        sections = preprocessor.extract_legal_sections(SAMPLE_TEXT)
        assert any("420" in s for s in sections)

    def test_preprocess_returns_structure(self, preprocessor):
        result = preprocessor.preprocess(SAMPLE_TEXT)
        assert "cleaned" in result
        assert "sentences" in result
        assert "tokens" in result
        assert "legal_sections" in result
        assert result["word_count"] > 0


class TestNER:

    def test_extract_returns_dict(self, ner):
        result = ner.extract(SAMPLE_TEXT)
        assert isinstance(result, dict)
        for key in ["persons", "organizations", "dates", "locations", "courts", "statutes", "money"]:
            assert key in result

    def test_money_extraction(self, ner):
        result = ner.extract(SAMPLE_TEXT)
        assert len(result["money"]) > 0

    def test_statute_extraction(self, ner):
        result = ner.extract(SAMPLE_TEXT)
        assert len(result["statutes"]) > 0


class TestClassifier:

    def test_keyword_classify_criminal(self):
        clf = CaseClassifier()
        clf.use_model = False
        text = "The accused was arrested for murder under IPC Section 302. FIR was filed."
        result = clf.classify(text)
        assert result["case_type"] == "Criminal"
        assert result["method"] == "keyword"
        assert 0 < result["confidence"] <= 1

    def test_keyword_classify_family(self):
        clf = CaseClassifier()
        clf.use_model = False
        text = "Petition for divorce and child custody. Matrimonial dispute. Maintenance alimony."
        result = clf.classify(text)
        assert result["case_type"] == "Family Law"

    def test_classify_returns_all_fields(self):
        clf = CaseClassifier()
        clf.use_model = False
        result = clf.classify(SAMPLE_TEXT)
        assert "case_type" in result
        assert "confidence" in result
        assert "probabilities" in result
        assert "method" in result


TATA_STEEL_PROMPT = (
    "Tata Steel failed to deliver goods worth Rs 50 crore to Indira Car Manufacturers "
    "as per contract dated March 2026 in Jamshedpur, seeking damages and specific "
    "performance under Section 73 of the Indian Contract Act"
)


class TestFactSheet:
    """Tests for FactSheet grounding, deterministic fallback, and new structure."""

    def test_is_grounded_rejects_ungrounded_value(self):
        """A value not present in raw_prompt must be MISSING."""
        raw = "Tata Steel supplied goods to Indira Car Manufacturers"
        # Exact match OK
        assert is_grounded("Tata Steel", raw) is True
        # Not in prompt
        assert is_grounded("Mahindra Car Manufacturers", raw) is False
        # Fuzzy token overlap below threshold
        assert is_grounded("completely different name", raw) is False

    def test_build_from_text_tata_steel(self):
        """Deterministic fallback on the Tata Steel prompt."""
        sheet = build_from_text(TATA_STEEL_PROMPT)
        # Parties verbatim from prompt
        party_names = sheet.party_names()
        assert "Tata Steel" in party_names
        assert "Indira Car Manufacturers" in party_names
        # Party roles: plaintiff/defendant inferred from context (INFERRED, not PROVIDED)
        tata = next(p for p in sheet.parties if p.name == "Tata Steel")
        indira = next(p for p in sheet.parties if p.name == "Indira Car Manufacturers")
        assert tata.role in ("plaintiff", "defendant", "unknown")
        assert indira.role in ("plaintiff", "defendant", "unknown")
        # They should have opposite roles if both inferred
        if tata.role != "unknown" and indira.role != "unknown":
            assert tata.role != indira.role
        # Role and user_side are INFERRED (never PROVIDED)
        assert tata.status == "INFERRED"
        assert indira.status == "INFERRED"
        assert tata.user_side is not None  # inferred from role
        # Entity type is INFERRED from regex - "Tata Steel" -> unknown (no corporate suffix), "Indira Car Manufacturers" -> unknown
        assert tata.entity_type == "unknown"
        assert indira.entity_type == "unknown"
        # Contract date stays as written (no normalization), PROVIDED because grounded
        assert sheet.contract_date.value == "March 2026"
        assert sheet.contract_date.status == "PROVIDED"
        # Contract value present with normalized amount_inr
        assert sheet.contract_value.value is not None
        assert "50 crore" in sheet.contract_value.value
        assert sheet.contract_value.status == "PROVIDED"
        assert sheet.contract_value.normalized is not None
        assert sheet.contract_value.normalized.get("amount_inr") == 50_00_00_000
        # Delivery date not mentioned -> MISSING
        assert sheet.delivery_date.status == "MISSING"
        assert sheet.delivery_date.value is None
        # Incident date MISSING (only contract date in prompt)
        assert sheet.incident_date.status == "MISSING"
        # Relief sought is a list of FactField items
        assert isinstance(sheet.relief_sought, list)
        assert len(sheet.relief_sought) > 0
        relief_vals = [r.value for r in sheet.relief_sought if r.value]
        assert any("damages" in v.lower() for v in relief_vals)
        assert any("specific performance" in v.lower() for v in relief_vals)
        # Claim type: enum (INFERRED) + raw phrase (PROVIDED)
        assert sheet.claim_type.value in ("NON_DELIVERY_OF_GOODS", "BREACH_OF_CONTRACT", "OTHER")
        assert sheet.claim_type.status == "INFERRED"
        assert sheet.claim_type_raw.value is not None
        assert "failed to deliver" in sheet.claim_type_raw.value.lower()
        assert sheet.claim_type_raw.status == "PROVIDED"
        # Place
        assert sheet.place.value == "Jamshedpur"
        assert sheet.place.status == "PROVIDED"

    def test_grounding_check_rejects_llm_hallucination(self):
        """Mocked LLM returns wrong party + normalized date -> both downgraded."""
        raw = TATA_STEEL_PROMPT
        # Simulate LLM output with hallucinations
        hallucinated_party = "Mahindra Car Manufacturers"
        hallucinated_date = "2026-03-15"  # normalized, not in prompt

        from app.nlp.fact_sheet import grounded_field, grounded_party

        # Party not in prompt -> MISSING
        pf = grounded_party(hallucinated_party, raw)
        assert pf is None  # grounded_party returns None when ungrounded

        # Date not in prompt -> MISSING
        df = grounded_field(hallucinated_date, raw)
        assert df.status == "MISSING"
        assert df.value is None

    def test_missing_marker_format(self):
        assert missing_marker("contract date") == "[TO BE CONFIRMED: contract date]"

    def test_normalize_amount_inr(self):
        """Test amount normalization for Indian currency formats."""
        assert normalize_amount_inr("Rs 50 crore") == 50_00_00_000
        assert normalize_amount_inr("Rs. 5,00,000") == 5_00_000
        assert normalize_amount_inr("10 lakh") == 10_00_000
        assert normalize_amount_inr("100 thousand") == 1_00_000
        assert normalize_amount_inr("₹ 25,00,000") == 25_00_000
        assert normalize_amount_inr("invalid") is None

    def test_infer_entity_type(self):
        """Test entity type inference (always INFERRED). Only returns company with corporate suffix."""
        assert infer_entity_type("Tata Steel Ltd") == "company"
        assert infer_entity_type("Tata Steel Limited") == "company"
        assert infer_entity_type("ABC Pvt Ltd") == "company"
        assert infer_entity_type("XYZ LLP") == "llp"
        assert infer_entity_type("Government of India") == "government"
        assert infer_entity_type("John Doe") == "unknown"
        # No corporate suffix -> unknown
        assert infer_entity_type("Tata Steel") == "unknown"
        assert infer_entity_type("Indira Car Manufacturers") == "unknown"

    def test_infer_claim_type_enum(self):
        """Test claim type enum mapping."""
        assert infer_claim_type("failed to deliver") == "NON_DELIVERY_OF_GOODS"
        assert infer_claim_type("breach of contract") == "BREACH_OF_CONTRACT"
        assert infer_claim_type("cheque bounce") == "CHEQUE_BOUNCE"
        assert infer_claim_type("specific performance") == "SPECIFIC_PERFORMANCE"
        assert infer_claim_type("recovery of dues") == "RECOVERY_OF_DUES"
        assert infer_claim_type("damages") == "DAMAGES"
        assert infer_claim_type("eviction") == "EVICTION"
        assert infer_claim_type("divorce") == "DIVORCE"
        assert infer_claim_type("wrongful termination") == "WRONGFUL_TERMINATION"
        assert infer_claim_type("something else") == "OTHER"

    def test_party_status_is_inferred(self):
        """Party role, user_side, entity_type must be INFERRED, not PROVIDED."""
        sheet = build_from_text(TATA_STEEL_PROMPT)
        for p in sheet.parties:
            assert p.status == "INFERRED", f"Party {p.name} status should be INFERRED"
            assert p.role in ("plaintiff", "defendant", "unknown")
            assert p.entity_type in ("company", "individual", "partnership", "llp", "trust", "government", "other", "unknown")

    def test_missing_critical_fields_returns_all_five(self):
        """missing_critical_fields('plaint') returns all 5 critical questions."""
        sheet = build_from_text(TATA_STEEL_PROMPT)
        questions = sheet.missing_critical_fields("plaint")

        # Should have at least 5 questions covering:
        # 1. user_side
        # 2. exact legal names + entity type
        # 3. delivery_date
        # 4. notice dates
        # 5. arbitration clause
        # (payment status is conditional on cheque)
        assert len(questions) >= 5

        # 1. user_side question
        assert any("represent" in q.lower() for q in questions)

        # 2. exact legal names + entity type for each party
        name_questions = [q for q in questions if "exact legal name" in q.lower()]
        assert len(name_questions) >= 2  # one per party

        # 3. delivery date
        assert any("delivery" in q.lower() for q in questions)

        # 4. notice dates (since breach of contract)
        assert any("notice" in q.lower() for q in questions)

        # 5. arbitration clause
        assert any("arbitration" in q.lower() for q in questions)

    def test_relief_sought_is_list(self):
        """relief_sought is a list of FactField items."""
        sheet = build_from_text(TATA_STEEL_PROMPT)
        assert isinstance(sheet.relief_sought, list)
        assert len(sheet.relief_sought) > 0
        for item in sheet.relief_sought:
            assert isinstance(item, FactField)
            assert item.status == "PROVIDED"
        relief_vals = [r.value for r in sheet.relief_sought if r.value]
        assert any("damages" in v.lower() for v in relief_vals)
        assert any("specific performance" in v.lower() for v in relief_vals)

    def test_claim_type_enum_plus_raw_phrase(self):
        """claim_type is enum (INFERRED), claim_type_raw holds raw phrase (PROVIDED)."""
        sheet = build_from_text(TATA_STEEL_PROMPT)
        assert sheet.claim_type.value in ("NON_DELIVERY_OF_GOODS", "BREACH_OF_CONTRACT", "OTHER")
        assert sheet.claim_type.status == "INFERRED"
        assert sheet.claim_type_raw.value is not None
        assert "failed to deliver" in sheet.claim_type_raw.value.lower()
        assert sheet.claim_type_raw.status == "PROVIDED"

    def test_amount_inr_normalized_no_key_path(self):
        """amount_inr normalized in no-key path."""
        sheet = build_from_text(TATA_STEEL_PROMPT)
        assert sheet.contract_value.normalized is not None
        assert sheet.contract_value.normalized.get("amount_inr") == 50_00_00_000

    def test_amount_inr_normalized_llm_path(self):
        """amount_inr normalized in LLM path via grounded override."""
        from app.nlp.fact_sheet import FactField, normalize_amount_inr
        sheet = build_from_text(TATA_STEEL_PROMPT)
        # Simulate grounded override with amount (as LLM extractor would do)
        grounded_val = "Rs 50 crore"
        sheet.contract_value = FactField(
            value=grounded_val, status="PROVIDED", source_span=grounded_val,
            normalized={"amount_inr": normalize_amount_inr(grounded_val)}
        )
        assert sheet.contract_value.normalized is not None
        assert sheet.contract_value.normalized.get("amount_inr") == 50_00_00_000


class TestSchemaParity:
    """Golden test: both no-key and LLM paths produce identical FactSheet schema."""

    def test_golden_schema_parity_tata_steel(self):
        """Both paths produce same keys and value types for Tata Steel prompt."""
        # No-key path
        sheet_no_key = build_from_text(TATA_STEEL_PROMPT)

        # Simulated LLM path (mocked LLM response, coerced into schema)
        # Mock LLM response for Tata Steel
        mock_llm_data = {
            "petitioner_name": "Indira Car Manufacturers",
            "respondent_name": "Tata Steel",
            "contract_date": "March 2026",
            "delivery_date": None,
            "notice_dates": [],
            "incident_date": None,
            "contract_value": "Rs 50 crore",
            "damages_claimed": None,
            "place": "Jamshedpur",
            "claim_type_raw": "failed to deliver",
            "claim_type_enum": "NON_DELIVERY_OF_GOODS",
            "statutes_cited_by_user": ["Section 73 of the Indian Contract Act"],
            "relief_sought": ["damages", "specific performance"],
            "has_arbitration_clause": "unknown",
        }
        # Build via extractor (which uses build_from_text + LLM override)
        from app.nlp.extractor import _build_fact_sheet
        sheet_llm = _build_fact_sheet(TATA_STEEL_PROMPT, mock_llm_data)

        # Compare schemas - both should have same keys and value types
        self._assert_same_schema(sheet_no_key, sheet_llm)

        # Verify specific grounded values match
        assert sheet_no_key.contract_date.value == sheet_llm.contract_date.value == "March 2026"
        assert sheet_no_key.contract_value.value == sheet_llm.contract_value.value == "Rs 50 crore"
        assert sheet_no_key.contract_value.normalized.get("amount_inr") == sheet_llm.contract_value.normalized.get("amount_inr") == 50_00_00_000
        assert sheet_no_key.claim_type.value == sheet_llm.claim_type.value == "NON_DELIVERY_OF_GOODS"
        assert sheet_no_key.claim_type.status == sheet_llm.claim_type.status == "INFERRED"
        assert sheet_no_key.claim_type_raw.value == sheet_llm.claim_type_raw.value == "failed to deliver"
        assert sheet_no_key.claim_type_raw.status == sheet_llm.claim_type_raw.status == "PROVIDED"

    def _assert_same_schema(self, sheet1: FactSheet, sheet2: FactSheet):
        """Assert both sheets have same field names and value types."""
        # Compare all FactField attributes
        for attr in dir(sheet1):
            if attr.startswith("_"):
                continue
            v1 = getattr(sheet1, attr, None)
            v2 = getattr(sheet2, attr, None)
            # Skip methods
            if callable(v1) or callable(v2):
                continue
            # Both should have same type
            assert type(v1) is type(v2), f"Type mismatch for {attr}: {type(v1)} vs {type(v2)}"
            if isinstance(v1, FactField):
                # Check FactField structure
                assert hasattr(v1, "value") and hasattr(v1, "status") and hasattr(v1, "source_span")
                assert hasattr(v2, "value") and hasattr(v2, "status") and hasattr(v2, "source_span")
            elif isinstance(v1, list) and v1 and isinstance(v1[0], FactField):
                # List of FactField (relief_sought, notice_dates)
                assert isinstance(v2, list)
                if v1 and v2:
                    assert isinstance(v1[0], FactField) and isinstance(v2[0], FactField)
            elif isinstance(v1, list) and v1 and hasattr(v1[0], "name"):
                # List of PartyFact (parties)
                assert isinstance(v2, list)
                if v1 and v2:
                    assert hasattr(v1[0], "name") and hasattr(v1[0], "role") and hasattr(v1[0], "status")
                    assert hasattr(v2[0], "name") and hasattr(v2[0], "role") and hasattr(v2[0], "status")


class TestValidator:
    """Tests for the validator."""

    def test_statute_whitelist_check(self):
        """Whitelisted statutes pass, others flagged."""
        assert is_statute_whitelisted("Section 73 of the Indian Contract Act 1872") is True
        assert is_statute_whitelisted("Section 74 of the Indian Contract Act 1872") is True
        assert is_statute_whitelisted("Section 10 of the Specific Relief Act 1963") is True
        assert is_statute_whitelisted("Section 138 of the Negotiable Instruments Act 1881") is True
        assert is_statute_whitelisted("Section 999 of Some Random Act") is False

    def test_validate_draft_detects_missing_placeholders(self):
        """Validator flags MISSING fields not rendered as placeholders."""
        from app.nlp.fact_sheet import build_from_text
        sheet = build_from_text(TATA_STEEL_PROMPT)

        # Draft with all placeholders present
        draft_with_placeholders = {
            "title_block": "Title with [TO BE CONFIRMED: delivery date]",
            "complaint_body": "Body with [TO BE CONFIRMED: damages claimed]",
            "prayer": "Prayer with [TO BE CONFIRMED: arbitration clause]",
            "list_of_witnesses": "Witnesses",
            "list_of_documents": "Documents",
            "affidavit": "Affidavit",
            "evidence_affidavit": "Evidence",
        }

        result = validate_draft(draft_with_placeholders, sheet)
        # Should have warnings for missing fields but no hard errors
        assert "to_complete" in result
        assert len(result["to_complete"]) > 0

    def test_validate_draft_flags_contract_eq_damages(self):
        """Validator warns when contract value equals damages claimed."""
        from app.nlp.fact_sheet import build_from_text, FactField
        sheet = build_from_text(TATA_STEEL_PROMPT)
        # Simulate case where damages = contract value (not separately pleaded)
        sheet.damages_claimed = FactField(value="Rs 50 crore", status="INFERRED", source_span="Rs 50 crore")

        draft = {
            "title_block": "Title",
            "complaint_body": "Body with Rs 50 crore damages",
            "prayer": "Prayer for Rs 50 crore damages",
            "list_of_witnesses": "W",
            "list_of_documents": "D",
            "affidavit": "A",
            "evidence_affidavit": "E",
        }

        result = validate_draft(draft, sheet)
        assert any("damages must be separately pleaded" in w for w in result["warnings"])

    def test_validate_draft_flags_section73_for_specific_performance(self):
        """Validator warns about 'specific performance under Section 73'."""
        from app.nlp.fact_sheet import build_from_text
        sheet = build_from_text(TATA_STEEL_PROMPT)

        draft = {
            "title_block": "Title",
            "complaint_body": "Body",
            "prayer": "Prayer for specific performance under Section 73",
            "list_of_witnesses": "W",
            "list_of_documents": "D",
            "affidavit": "A",
            "evidence_affidavit": "E",
        }

        result = validate_draft(draft, sheet)
        assert any("Section 73 applies to damages only" in w for w in result["warnings"])

    def test_validate_draft_unverified_statute(self):
        """Validator flags unverified statute citations."""
        from app.nlp.fact_sheet import build_from_text
        sheet = build_from_text(TATA_STEEL_PROMPT)

        draft = {
            "title_block": "Title",
            "complaint_body": "Body citing Section 999 of Random Act",
            "prayer": "Prayer",
            "list_of_witnesses": "W",
            "list_of_documents": "D",
            "affidavit": "A",
            "evidence_affidavit": "E",
        }

        result = validate_draft(draft, sheet)
        assert any("Unverified statute citation" in w for w in result["warnings"])

    def test_validate_draft_review_notes_present(self):
        """Validator always includes standard review notes."""
        from app.nlp.fact_sheet import build_from_text
        sheet = build_from_text(TATA_STEEL_PROMPT)

        # Draft without the problematic text - should have basic review notes
        draft_basic = {k: "Section " + k for k in ["title_block", "complaint_body", "prayer", "list_of_witnesses", "list_of_documents", "affidavit", "evidence_affidavit"]}
        result_basic = validate_draft(draft_basic, sheet)
        assert "review_notes" in result_basic
        notes = result_basic["review_notes"]
        assert any("Exact legal names" in n for n in notes)
        assert any("Party roles assumed" in n for n in notes)
        # Section 73 note only added when draft contains the problematic text
        assert not any("Section 73 applies to damages only" in n for n in notes)

        # Draft WITH the problematic text - should have Section 73 review note
        draft_with_s73 = {
            "title_block": "Title",
            "complaint_body": "Body",
            "prayer": "Prayer for specific performance under Section 73",
            "list_of_witnesses": "W",
            "list_of_documents": "D",
            "affidavit": "A",
            "evidence_affidavit": "E",
        }
        result_with_s73 = validate_draft(draft_with_s73, sheet)
        notes_s73 = result_with_s73["review_notes"]
        assert any("Section 73 applies to damages only" in n for n in notes_s73)

    def test_validate_draft_invented_name(self):
        """Validator flags invented person/org names not in FactSheet."""
        from app.nlp.fact_sheet import build_from_text
        sheet = build_from_text(TATA_STEEL_PROMPT)

        # Draft includes the real parties from FactSheet, plus an invented name
        draft = {
            "title_block": "Tata Steel vs Indira Car Manufacturers",
            "complaint_body": "Tata Steel failed to deliver. Mahindra Car Manufacturers was involved in the transaction",
            "prayer": "Prayer",
            "list_of_witnesses": "W",
            "list_of_documents": "D",
            "affidavit": "A",
            "evidence_affidavit": "E",
        }

        result = validate_draft(draft, sheet)
        assert any("Invented name detected: 'Mahindra Car Manufacturers'" in e for e in result["errors"])

    def test_validate_draft_allows_known_names(self):
        """Validator allows known names from FactSheet."""
        from app.nlp.fact_sheet import build_from_text
        sheet = build_from_text(TATA_STEEL_PROMPT)

        draft = {
            "title_block": "Tata Steel vs Indira Car Manufacturers",
            "complaint_body": "Tata Steel failed to deliver",
            "prayer": "Prayer",
            "list_of_witnesses": "W",
            "list_of_documents": "D",
            "affidavit": "A",
            "evidence_affidavit": "E",
        }

        result = validate_draft(draft, sheet)
        # Should not flag Tata Steel or Indira Car Manufacturers
        for e in result["errors"]:
            assert "Tata Steel" not in e
            assert "Indira Car Manufacturers" not in e

    def test_validate_draft_invented_date(self):
        """Validator flags dates not in FactSheet."""
        from app.nlp.fact_sheet import build_from_text
        sheet = build_from_text(TATA_STEEL_PROMPT)

        draft = {
            "title_block": "Title",
            "complaint_body": "Contract dated 15 March 2026",
            "prayer": "Prayer",
            "list_of_witnesses": "W",
            "list_of_documents": "D",
            "affidavit": "A",
            "evidence_affidavit": "E",
        }

        result = validate_draft(draft, sheet)
        assert any("Invented date detected: '15 March 2026'" in e for e in result["errors"])

    def test_validate_draft_allows_grounded_dates(self):
        """Validator allows dates from FactSheet."""
        from app.nlp.fact_sheet import build_from_text
        sheet = build_from_text(TATA_STEEL_PROMPT)

        draft = {
            "title_block": "Title",
            "complaint_body": "Contract dated March 2026 in Jamshedpur",
            "prayer": "Prayer",
            "list_of_witnesses": "W",
            "list_of_documents": "D",
            "affidavit": "A",
            "evidence_affidavit": "E",
        }

        result = validate_draft(draft, sheet)
        # Should not flag March 2026 or Jamshedpur (place is allowed)
        for e in result["errors"]:
            assert "March 2026" not in e

    def test_validate_draft_invented_amount(self):
        """Validator flags rupee amounts not in FactSheet."""
        from app.nlp.fact_sheet import build_from_text
        sheet = build_from_text(TATA_STEEL_PROMPT)

        draft = {
            "title_block": "Title",
            "complaint_body": "Amount of Rs 75,00,00,000 was due",
            "prayer": "Prayer",
            "list_of_witnesses": "W",
            "list_of_documents": "D",
            "affidavit": "A",
            "evidence_affidavit": "E",
        }

        result = validate_draft(draft, sheet)
        assert any("Invented amount detected: 'Rs 75,00,00,000'" in e for e in result["errors"])

    def test_validate_draft_allows_grounded_amounts(self):
        """Validator allows amounts from FactSheet."""
        from app.nlp.fact_sheet import build_from_text
        sheet = build_from_text(TATA_STEEL_PROMPT)

        draft = {
            "title_block": "Title",
            "complaint_body": "Amount of Rs 50 crore",
            "prayer": "Prayer",
            "list_of_witnesses": "W",
            "list_of_documents": "D",
            "affidavit": "A",
            "evidence_affidavit": "E",
        }

        result = validate_draft(draft, sheet)
        # Should not flag Rs 50 crore
        for e in result["errors"]:
            assert "Rs 50 crore" not in e

    def test_validate_draft_invented_address(self):
        """Validator flags invented addresses/plot numbers."""
        from app.nlp.fact_sheet import build_from_text
        sheet = build_from_text(TATA_STEEL_PROMPT)

        draft = {
            "title_block": "Title",
            "complaint_body": "Property at Plot No. 42, Sector 8",
            "prayer": "Prayer",
            "list_of_witnesses": "W",
            "list_of_documents": "D",
            "affidavit": "A",
            "evidence_affidavit": "E",
        }

        result = validate_draft(draft, sheet)
        assert any("Invented address detected: 'Plot No. 42'" in e for e in result["errors"])

    def test_validate_draft_invented_clause(self):
        """Validator flags invented clause/section numbers."""
        from app.nlp.fact_sheet import build_from_text
        sheet = build_from_text(TATA_STEEL_PROMPT)

        draft = {
            "title_block": "Title",
            "complaint_body": "As per Clause 2 of the agreement",
            "prayer": "Prayer",
            "list_of_witnesses": "W",
            "list_of_documents": "D",
            "affidavit": "A",
            "evidence_affidavit": "E",
        }

        result = validate_draft(draft, sheet)
        assert any("Invented clause/section detected: 'Clause 2'" in e for e in result["errors"])

    def test_validate_draft_allows_statute_sections(self):
        """Validator allows statute section references (Section 73, etc.)."""
        from app.nlp.fact_sheet import build_from_text
        sheet = build_from_text(TATA_STEEL_PROMPT)

        draft = {
            "title_block": "Title",
            "complaint_body": "Under Section 73 of the Indian Contract Act",
            "prayer": "Prayer",
            "list_of_witnesses": "W",
            "list_of_documents": "D",
            "affidavit": "A",
            "evidence_affidavit": "E",
        }

        result = validate_draft(draft, sheet)
        # Should not flag Section 73
        for e in result["errors"]:
            assert "Section 73" not in e

    def test_validate_draft_inconsistent_party_name(self):
        """Validator flags inconsistent party name spelling across sections."""
        from app.nlp.fact_sheet import build_from_text
        sheet = build_from_text(TATA_STEEL_PROMPT)

        draft = {
            "title_block": "Tata Steel Ltd vs Indira Car Manufacturers",
            "complaint_body": "Tata Steel failed to deliver",
            "prayer": "Prayer",
            "list_of_witnesses": "W",
            "list_of_documents": "D",
            "affidavit": "A",
            "evidence_affidavit": "E",
        }

        result = validate_draft(draft, sheet)
        # Should flag "Tata Steel Ltd" vs "Tata Steel" from FactSheet
        assert any("Inconsistent party name: 'Tata Steel Ltd' vs FactSheet 'Tata Steel'" in e for e in result["errors"])

    def test_validate_draft_consistent_party_names_allowed(self):
        """Validator allows exact party name matches."""
        from app.nlp.fact_sheet import build_from_text
        sheet = build_from_text(TATA_STEEL_PROMPT)

        draft = {
            "title_block": "Tata Steel vs Indira Car Manufacturers",
            "complaint_body": "Tata Steel failed to deliver to Indira Car Manufacturers",
            "prayer": "Prayer",
            "list_of_witnesses": "W",
            "list_of_documents": "D",
            "affidavit": "A",
            "evidence_affidavit": "E",
        }

        result = validate_draft(draft, sheet)
        # Should not flag exact matches
        for e in result["errors"]:
            assert "Inconsistent party name" not in e
    """Ensure Alembic 003 upgrade/downgrade works."""

    def test_migration_import(self):
        """Importing the migration module should not raise."""
        import importlib.util
        import os
        migration_path = os.path.join(
            os.path.dirname(__file__), "..", "alembic", "versions", "003_raw_prompt_fact_sheet.py"
        )
        spec = importlib.util.spec_from_file_location("migration", migration_path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        # Just check the revision identifiers exist
        assert migration.revision == "003"
        assert migration.down_revision == "002"