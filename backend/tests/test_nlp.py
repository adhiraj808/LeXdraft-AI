"""Tests for the NLP pipeline components."""

import pytest
import spacy

from app.nlp.preprocessor import LegalTextPreprocessor
from app.nlp.ner import LegalNERExtractor
from app.nlp.classifier import CaseClassifier
from app.nlp.fact_sheet import (
    is_grounded,
    build_from_text,
    missing_marker,
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
    """Phase 1 tests for FactSheet grounding and deterministic fallback."""

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
        # Contract date stays as written (no normalization)
        assert sheet.contract_date.value == "March 2026"
        assert sheet.contract_date.status == "INFERRED"
        # Contract value present
        assert sheet.contract_value.value is not None
        assert "50 crore" in sheet.contract_value.value or "50 crore" in sheet.contract_value.value
        assert sheet.contract_value.status == "INFERRED"
        # Delivery date not mentioned -> MISSING
        assert sheet.delivery_date.status == "MISSING"
        assert sheet.delivery_date.value is None
        # Incident date MISSING (only contract date in prompt)
        assert sheet.incident_date.status == "MISSING"

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
