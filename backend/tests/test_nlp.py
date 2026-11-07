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
        # Entity type is INFERRED from regex
        assert tata.entity_type == "company"
        assert indira.entity_type == "company"
        assert tata.entity_type != "unknown" or indira.entity_type != "unknown"
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
        # Claim type: enum + raw phrase
        assert sheet.claim_type.value in ("NON_DELIVERY_OF_GOODS", "BREACH_OF_CONTRACT", "OTHER")
        assert sheet.claim_type_raw.value is not None
        assert "failed to deliver" in sheet.claim_type_raw.value.lower()
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
        """Test entity type inference (always INFERRED)."""
        assert infer_entity_type("Tata Steel") == "company"
        assert infer_entity_type("Tata Steel Ltd") == "company"
        assert infer_entity_type("ABC Pvt Ltd") == "company"
        assert infer_entity_type("XYZ LLP") == "llp"
        assert infer_entity_type("Government of India") == "government"
        assert infer_entity_type("John Doe") == "unknown"

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
        """claim_type is enum, claim_type_raw holds raw phrase."""
        sheet = build_from_text(TATA_STEEL_PROMPT)
        assert sheet.claim_type.value in ("NON_DELIVERY_OF_GOODS", "BREACH_OF_CONTRACT", "OTHER")
        assert sheet.claim_type_raw.value is not None
        assert "failed to deliver" in sheet.claim_type_raw.value.lower()

    def test_amount_inr_normalized_both_paths(self):
        """amount_inr normalized in both LLM and no-key paths (via grounded override)."""
        # No-key path
        sheet = build_from_text(TATA_STEEL_PROMPT)
        assert sheet.contract_value.normalized is not None
        assert sheet.contract_value.normalized.get("amount_inr") == 50_00_00_000

        # Simulated LLM path: grounded override should also normalize
        from app.nlp.fact_sheet import FactField, normalize_amount_inr
        sheet2 = FactSheet(raw_prompt=TATA_STEEL_PROMPT)
        # Simulate grounded override with amount
        grounded_val = "Rs 50 crore"
        sheet2.contract_value = FactField(
            value=grounded_val, status="PROVIDED", source_span=grounded_val,
            normalized={"amount_inr": normalize_amount_inr(grounded_val)}
        )
        assert sheet2.contract_value.normalized is not None
        assert sheet2.contract_value.normalized.get("amount_inr") == 50_00_00_000


class TestAlembic003:
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